#
# Gramps Web API - A RESTful API for the Gramps genealogy program
#
# Copyright (C) 2021      David Straub
# Copyright (C) 2024      William Vital <wvmscs@wvital.fr>      
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


"""Texts for e-mails."""
""" Modified to handle multipart html emails """ 

import os

if os.getenv('ENV_FEATURE__NEW_EMAIL'):
	from .new_emails import email_confirm_email
	from .new_emails import email_new_user
	from .new_emails import email_reset_pw
else:
	from .emails import email_confirm_email
	from .emails import email_new_user
	from .emails import email_reset_pw
