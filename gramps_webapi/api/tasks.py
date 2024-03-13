#
# Gramps Web API - A RESTful API for the Gramps genealogy program
#
# Copyright (C) 2021-2023      David Straub
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Execute tasks."""

import os
import uuid
from gettext import gettext as _
from http import HTTPStatus
from typing import Any, Callable, Dict, Optional, Union

from celery import shared_task
from celery.result import AsyncResult
from flask import current_app

from ..auth import get_owner_emails
from .check import check_database
from .emails import email_confirm_email, email_new_user, email_reset_pw
from .export import prepare_options, run_export
from .media import get_media_handler
from .media_importer import MediaImporter
from .report import run_report
from .resources.util import dry_run_import, run_import
from .util import (
    check_quota_people,
    get_config,
    get_db_outside_request,
    get_search_indexer,
    send_email,
    update_usage_people,
    upgrade_gramps_database,
)


def run_task(task: Callable, **kwargs) -> Union[AsyncResult, Any]:
    """Send a task to the task queue or run immediately if no queue set up."""
    if not current_app.config["CELERY_CONFIG"]:
        with current_app.app_context():
            return task(**kwargs)
    return task.delay(**kwargs)


def make_task_response(task: AsyncResult):
    """Make a 202 response with the location of the task status endpoint."""
    url = f"/api/tasks/{task.id}"
    payload = {"task": {"href": url, "id": task.id}}
    return payload, HTTPStatus.ACCEPTED


def clip_progress(x: float) -> float:
    """Clip the progress to [0, 1), else return -1."""
    if x < 0 or x >= 1:
        return -1
    return x


@shared_task()
def send_email_reset_password(email: str, token: str):
    """Send an email for password reset."""
    base_url = get_config("BASE_URL").rstrip("/")
    body = email_reset_pw(base_url=base_url, token=token)
    subject = _("Reset your Gramps password")
    send_email(subject=subject, body=body, to=[email])


@shared_task()
def send_email_confirm_email(email: str, token: str):
    """Send an email to confirm an e-mail address."""
    base_url = get_config("BASE_URL").rstrip("/")
    body = email_confirm_email(base_url=base_url, token=token)
    subject = _("Confirm your e-mail address")
    send_email(subject=subject, body=body, to=[email])


@shared_task()
def send_email_new_user(
    username: str, fullname: str, email: str, tree: str, include_admins: bool
):
    """Send an email to owners to notify of a new registered user."""
    base_url = get_config("BASE_URL").rstrip("/")
    body = email_new_user(
        base_url=base_url, username=username, fullname=fullname, email=email
    )
    subject = _("New registered user")
    emails = get_owner_emails(tree=tree, include_admins=include_admins)
    if emails:
        send_email(subject=subject, body=body, to=emails)


def _search_reindex_full(tree, progress_cb: Optional[Callable] = None) -> None:
    """Rebuild the search index."""
    indexer = get_search_indexer(tree)
    db = get_db_outside_request(tree=tree, view_private=True, readonly=True)
    try:
        indexer.reindex_full(db, progress_cb=progress_cb)
    finally:
        db.close()


def progress_callback_count(self, title: str = "", message: str = "") -> Callable:
    def callback(current: int, total: int) -> None:
        if total == 0:
            return
        self.update_state(
            state="PROGRESS",
            meta={
                "current": current,
                "total": total,
                "progress": clip_progress(current / total),
                "title": title,
                "message": message,
            },
        )

    return callback


@shared_task(bind=True)
def search_reindex_full(self, tree) -> None:
    """Rebuild the search index."""
    return _search_reindex_full(
        tree,
        progress_cb=progress_callback_count(self, title="Updating search index..."),
    )


def _search_reindex_incremental(tree, progress_cb: Optional[Callable] = None) -> None:
    """Run an incremental reindex of the search index."""
    indexer = get_search_indexer(tree)
    db = get_db_outside_request(tree=tree, view_private=True, readonly=True)
    try:
        indexer.reindex_incremental(db, progress_cb=progress_cb)
    finally:
        db.close()


@shared_task(bind=True)
def search_reindex_incremental(self, tree) -> None:
    """Run an incremental reindex of the search index."""
    return _search_reindex_incremental(
        tree,
        progress_cb=progress_callback_count(self, title="Updating search index..."),
    )


@shared_task(bind=True)
def import_file(self, tree: str, file_name: str, extension: str, delete: bool = True):
    """Import a file."""
    object_counts = dry_run_import(file_name=file_name)
    if object_counts is None:
        raise ValueError(f"Failed importing '{extension}:{file_name}' file")
    check_quota_people(to_add=object_counts["people"], tree=tree)
    db_handle = get_db_outside_request(tree=tree, view_private=True, readonly=True)
    run_import(
        db_handle=db_handle,
        file_name=file_name,
        extension=extension.lower(),
        delete=delete,
        task=self,
    )
    update_usage_people(tree=tree)
    _search_reindex_incremental(
        tree,
        progress_cb=progress_callback_count(self, title="Updating search index..."),
    )


@shared_task(bind=True)
def export_db(
    self, tree: str, extension: str, options: Dict, view_private: bool
) -> Dict[str, str]:
    """Export a database."""
    db_handle = get_db_outside_request(
        tree=tree, view_private=view_private, readonly=True
    )
    prepared_options = prepare_options(db_handle, options)
    file_name, file_type = run_export(db_handle, extension, prepared_options, task=self)
    extension = file_type.lstrip(".")
    return {
        "file_name": file_name,
        "file_type": file_type,
        "url": f"/api/exporters/{extension}/file/processed/{file_name}",
    }


@shared_task()
def generate_report(
    tree: str,
    report_id: str,
    options: Dict,
    view_private: bool,
    locale: Optional[str] = None,
) -> Dict[str, str]:
    """Generate a Gramps report."""
    db_handle = get_db_outside_request(
        tree=tree, view_private=view_private, readonly=True
    )
    file_name, file_type = run_report(
        db_handle=db_handle,
        report_id=report_id,
        report_options=options,
        language=locale,
    )
    return {
        "file_name": file_name,
        "file_type": file_type,
        "url": f"/api/reports/{report_id}/file/processed/{file_name}",
    }


@shared_task(bind=True)
def export_media(self, tree: str, view_private: bool) -> Dict[str, Union[str, int]]:
    """Export media files."""
    db_handle = get_db_outside_request(
        tree=tree, view_private=view_private, readonly=True
    )
    media_handler = get_media_handler(db_handle, tree=tree)
    export_path = current_app.config["EXPORT_DIR"]
    os.makedirs(export_path, exist_ok=True)
    file_name = f"{uuid.uuid4()}.zip"
    zip_filename = os.path.join(export_path, file_name)
    media_handler.create_file_archive(
        db_handle=db_handle,
        zip_filename=zip_filename,
        include_private=view_private,
        progress_cb=progress_callback_count(self),
    )
    file_size = os.path.getsize(zip_filename)
    return {
        "file_name": file_name,
        "url": f"/api/media/archive/{file_name}",
        "file_size": file_size,
    }


@shared_task(bind=True)
def import_media_archive(self, tree: str, file_name: str, delete: bool = True):
    """Import a media archive."""
    db_handle = get_db_outside_request(tree=tree, view_private=True, readonly=True)
    importer = MediaImporter(
        tree=tree,
        db_handle=db_handle,
        file_name=file_name,
        delete=delete,
    )
    result = importer(progress_cb=progress_callback_count(self))
    return result


@shared_task()
def media_ocr(
    tree: str, handle: str, view_private: bool, lang: str, output_format: str = "string"
):
    """Perform text recognition (OCR) on a media object."""
    db_handle = get_db_outside_request(
        tree=tree, view_private=view_private, readonly=True
    )
    handler = get_media_handler(db_handle, tree).get_file_handler(
        handle, db_handle=db_handle
    )
    return handler.get_ocr(lang=lang, output_format=output_format)


@shared_task(bind=True)
def check_repair_database(self, tree: str):
    """Check and repair a Gramps database (tree)"""
    db_handle = get_db_outside_request(tree=tree, view_private=True, readonly=False)
    return check_database(db_handle, progress_cb=progress_callback_count(self))


@shared_task(bind=True)
def upgrade_database_schema(self, tree: str):
    """Upgrade a Gramps database (tree) schema."""
    return upgrade_gramps_database(tree=tree, task=self)
