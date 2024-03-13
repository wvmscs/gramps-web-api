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

from email.message import EmailMessage
import qrcode
from qrcode.image.pure import PyPNGImage
from io import BytesIO
import base64
import re


from gettext import gettext as _


BASE_MODEL="""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" 
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schem=
as-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <meta name="sg:pagetag" content="">
    <meta name="sg:flowtag" content="">
    <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
    <meta content="width=device-width, initial-scale=1.0" name="viewport" />
    <title>Tests Bienvenue</title>
    <style type="text/css">
        @media only screen and (max-width: 699px) {
            table[class="full"],
            td[class="full"] {
                width: 375px !important;
                min-height: 1px !mportant;
            };
            p[class="intro"], p[class="action"], p[class="end"] {style="color: #9B9B9B; 
                text-decoration: none; 
                font-size:15px;
                font-family: 'Open Sans', sans-serif;
            };
            
        }
    </style>
  </head>
  <body  style="padding:0; margin:0;font-family: 'Open Sans', sans-serif; background-color:#FFFFFF;">
  <table id="heredoc" width="100%" cellpadding="0" cellspacing="0" style="background-color: #FFFFFF;">
    <tbody>
      <tr>
        <td align="center" valign="top">
          <p style="text-align: center">
            <!--a style="color: #9B9B9B; text-decoration: none; font-size:12px;font-family: 'Open Sans', sans-serif;" target="_blank" href="#heredoc">Lisez ce message dans votre navigateur</a -->
          </p>
          <table width="680" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF" align="center" class="full">
            <tbody>
              <tr>
                <td align="left" style="padding-left:48px; padding-right:48px; padding-top:40px; padding-bottom:8px;">
                <img src="https://gramps-project.org/blog/wp-content/uploads/2016/01/Gramps_LogoType-2015.png" width="291" height="63" alt="Gramps – Free Genealogy Software: Open Source Free Genealogy Software">
                </td>
              </tr>
            </tbody>
          </table>
          %%__insert__%%
        </td>
      </tr>
    </tbody>
  </table>
  </body>
</html>
"""


def build_qr(url, alt="", intro="", action="", end=""):

    fragment = """          
    <table width="680" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF" align="center" class="full">
            <tbody>
              <tr>
                <td align="left" style="padding-left:48px; padding-right:4px; padding-top:40px; padding-bottom:8px;">
                <a href="{url}"><img width="150" style="display:block; border:0;" alt="{alt}" src="{src}" /></a>
                </td>
                <td align="left" style="padding-left:4px; padding-right:48px; padding-top:40px; padding-bottom:8px;">
                <div><p class="into">{intro}</p><p class="action">{action}</p><p class="end">{end}</p>
                </div>
                </td>
              </tr>
            </tbody>
          </table>
    """
    
    src="""data:image/png;base64,{bb}"""

    qr = qrcode.QRCode()
    qr.add_data(url)
    img = qr.make_image(image_factory=PyPNGImage)
    bio = BytesIO()    
    img.save(bio)
    last_img = img
    bb = base64.b64encode(bio.getvalue()).decode()
    bio.close()

    res = fragment.format(
        url = url,
        alt = alt,
        src = src.format(bb = bb),
        intro = intro,
        action = action,
        end = end,
    )
    return res


def email_reset_pw(base_url: str, token: str):
    """Reset password e-mail text."""
    reset_password_url = f"{base_url}/api/users/-/password/reset/?jwt={token}"
    intro = _(
        "You are receiving this e-mail because you (or someone else) "
        "have requested the reset of the password for your account."
    )

    action_plain = _(
        "Please click on the following link, or paste this into your browser "
        "to complete the process:"
    )

    action_html = _(
        "Please click on or scan the QRCode "
        "to complete the process."
    )

    end = _(
        "If you did not request this, please ignore this e-mail "
        "and your password will remain unchanged."
    )
    
    plain_text = f"""{intro}

{action_plain}

{reset_password_url}

{end}
"""
    html_page = BASE_MODEL.replace("%%__insert__%%", build_qr(reset_password_url, 
	    alt=_("Complete the process"), 
	    intro = intro,
	    action = action_html,
	    end = end ))
    msg = EmailMessage()
    msg.preamble = _('You will not see this in a MIME-aware mail reader.\n')
    msg.make_alternative()
    msg.add_alternative( plain_text, subtype='plain')
    msg.add_alternative( html_page , subtype='html')

    return msg




def email_confirm_email(base_url: str, token: str):
    """Confirm e-mail address e-mail text."""
    confirm_email_addr = f"{base_url}/api/users/-/email/confirm/?jwt={token}"
    intro = (
        _(
            "You are receiving this e-mail because you (or someone else) "
            "have registered a new account at %s."
        )
        % base_url
    )
    intro_html = (
        _(
            "You are receiving this e-mail because you (or someone else) "
            "have registered a new account at <pre>%s</pre>"
        )
        % re.sub('http[s]{0,1}://','', base_url)
    )
    action = _(
        "Please click on or scan the QRCode "
        "to complete the process."
    )

    plain_text = f"""{intro}

{action}

{confirm_email_addr}
"""
    html_page = BASE_MODEL.replace("%%__insert__%%", build_qr(confirm_email_addr, 
	    alt=_("Complete the process"), 
	    intro = intro_html,
	    action = action,
	    end = "" ))
    msg = EmailMessage()
    msg.preamble = _('You will not see this in a MIME-aware mail reader.\n')
    msg.make_alternative()
    msg.add_alternative( plain_text, subtype='plain')
    msg.add_alternative( html_page , subtype='html')

    return msg


def email_new_user(base_url: str, username: str, fullname: str, email: str):
    """E-mail notifying owners of a new registered user."""
    intro = _("A new user registered at %s:") % base_url
    label_username = _("User name")
    label_fullname = _("Full name")
    label_email = _("E-mail")
    user_details = f"""{label_username}: {username}
{label_fullname}: {fullname}
{label_email}: {email}
"""
    plain_text = f"""{intro}

{user_details}
"""
    html_fragment = f"""    
          <table width="680" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF" align="center" class="full">
            <tbody>
              <tr>
                <td width="150" align="left" style="padding-left:48px; padding-right:16px; padding-top:40px; padding-bottom:8px;">
                <table class="newuser">
                    <thead><tr><td width="100%"><a href="{base_url}">{intro}</a></td></tr>
                           <tr><td width="100%">{_("As a tree owner, think to give him/her a role.")}</td></tr>
                    </thead>
                    <tbody>
                	<tr>
                	<td width="30%">{label_username}</td><td>{username}</td>
                	</tr><tr>
                	<td width="30%">{label_fullname}</td><td>{fullname}</td>
                	</tr><tr>
                	<td width="30%">{label_email}</td><td>{email}</td>
                	</tr>
                	<tbody>
                </table>
                </td>
              </tr>
            </tbody>
          </table>
 """
    html_page = BASE_MODEL.replace("%%__insert__%%", html_fragment)
    msg = EmailMessage()
    msg.preamble = _('You will not see this in a MIME-aware mail reader.\n')
    msg.make_alternative()
    msg.add_alternative( plain_text, subtype='plain')
    msg.add_alternative( html_page , subtype='html')

    return msg

