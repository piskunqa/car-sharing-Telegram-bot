from datetime import datetime
import shutil
from os import makedirs, listdir, rmdir, remove
from os.path import splitext, join, isdir, basename, exists

import flask_admin as admin
from flask import Flask, Response, redirect, request, flash
from flask_admin import AdminIndexView
from flask_admin.actions import action
from flask_admin.babel import lazy_gettext, gettext, ngettext
from flask_admin.contrib.peewee import ModelView
from flask_basicauth import BasicAuth
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename
from wtforms import FileField
from wtforms.validators import ValidationError, Length
from datetime import date

from config import admin_password, admin_user, admin_secret_key, allow_ip_list, lock_by_ip
from models import Users, Trips, Presets

app = Flask(__name__)
app.config['SECRET_KEY'] = admin_secret_key
app.config['BASIC_AUTH_USERNAME'] = admin_user
app.config['BASIC_AUTH_PASSWORD'] = admin_password
basic_auth = BasicAuth(app)


@app.route('/')
def index():
    return '<script>document.location.href = "/admin"</script>'


class DashboardView(AdminIndexView):
    """
        Custom admin dashboard view for Flask-Admin.

        This class customizes visibility and access control for the admin dashboard.
        It integrates HTTP Basic Authentication and optional IP-based restrictions.
    """

    def is_visible(self):
        """
            Determine whether this view should be visible in the Flask-Admin menu.

            Returns:
                bool: False to hide the dashboard link from the menu.
        """
        return False

    def is_accessible(self):
        """
            Determine whether the current user can access the dashboard.

            Performs authentication using HTTP Basic Auth and optional IP restriction.

            Raises:
                AuthException: If the user is not authenticated or their IP is not allowed.

            Returns:
                bool: True if access is granted.
        """
        if not basic_auth.authenticate():
            raise AuthException('Not authenticated.')
        else:
            if lock_by_ip:
                if request.remote_addr not in allow_ip_list:
                    raise AuthException('Not authenticated.')
                else:
                    return True
            else:
                return True

    def inaccessible_callback(self, name, **kwargs):
        """
            Callback invoked when a user tries to access the view but is denied.

            Redirects the user to the Basic Auth login prompt.

            Args:
                name (str): The name of the view.
                **kwargs: Additional keyword arguments passed by Flask-Admin.

            Returns:
                werkzeug.wrappers.Response: A redirect response to trigger Basic Auth challenge.
        """
        return redirect(basic_auth.challenge())


class AuthException(HTTPException):
    """
        Custom HTTP exception used for authentication failures.

        This exception is raised when a user fails to authenticate, either
        due to incorrect credentials or IP restriction. It automatically
        returns an HTTP 401 Unauthorized response with a Basic Auth challenge.
    """

    def __init__(self, message):
        """
            Initialize the AuthException.

            Args:
                message (str): A descriptive message explaining the authentication failure.

            Behavior:
                - Calls the parent HTTPException constructor.
                - Returns an HTTP 401 response with the body:
                    "You could not be authenticated. Please refresh the page."
                - Includes the 'WWW-Authenticate' header to trigger Basic Auth login prompt.
        """
        super().__init__(message, Response(
            "You could not be authenticated. Please refresh the page.", 401,
            {'WWW-Authenticate': 'Basic realm="Login Required"'}))


class SecureView(ModelView):
    """
        Custom Flask-Admin ModelView with authentication and optional IP restriction.

        This class extends the standard ModelView to enforce access control
        using HTTP Basic Authentication and an optional allowed IP list.
        It can be used as a base class for all admin models that require security.
    """

    def is_accessible(self):
        """
            Determine whether the current user can access this model view.

            Performs authentication using HTTP Basic Auth and, if enabled,
            checks whether the request originates from an allowed IP address.

            Raises:
                AuthException: If the user fails authentication or their IP is not allowed.

            Returns:
                bool: True if the user is authenticated and, if IP restriction is active,
                      their IP is in the allow list.
        """
        if not basic_auth.authenticate():
            raise AuthException('Not authenticated.')
        else:
            if lock_by_ip:
                if request.remote_addr not in allow_ip_list:
                    raise AuthException('Not authenticated.')
                else:
                    return True
            else:
                return True

    def inaccessible_callback(self, name, **kwargs):
        """
            Callback invoked when a user tries to access the view but is denied.

            Redirects the user to the Basic Auth login prompt.

            Args:
                name (str): The name of the view being accessed.
                **kwargs: Additional keyword arguments provided by Flask-Admin.

            Returns:
                werkzeug.wrappers.Response: A redirect response triggering the Basic Auth challenge.
        """
        return redirect(basic_auth.challenge())



admin = admin.Admin(app, name='Bot Admin', index_view=DashboardView())
admin.add_view(SecureView(Users))
admin.add_view(SecureView(Trips))
admin.add_view(SecureView(Presets))
app.run("0.0.0.0", port=80, debug=True)
