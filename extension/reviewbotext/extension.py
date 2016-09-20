from __future__ import unicode_literals

from celery import Celery
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.utils.importlib import import_module
from django.utils.translation import ugettext_lazy as _
from reviewboard.admin.server import get_server_url
from reviewboard.extensions.base import Extension
from reviewboard.extensions.hooks import IntegrationHook

from reviewbotext.integration import ReviewBotIntegration
from reviewbotext.resources import (review_bot_review_resource,
                                    tool_resource)


class ReviewBotExtension(Extension):
    """An extension for communicating with Review Bot."""

    metadata = {
        'Name': 'Review Bot',
        'Summary': _('Performs automated analysis and review on code posted '
                     'to Review Board.'),
        'Author': 'Review Board',
        'Author-URL': 'http://www.reviewboard.org/',
    }

    is_configurable = True
    has_admin_site = True

    resources = [
        review_bot_review_resource,
        tool_resource,
    ]

    default_settings = {
        'broker_url': '',
        'user': None,
    }

    css_bundles = {
        'integration-config': {
            'source_filenames': ['css/integration-config.less'],
        },
    }

    js_bundles = {
        'integration-config': {
            'source_filenames': ['js/integrationConfig.es6.js'],
        },
    }

    def initialize(self):
        """Initialize the extension."""
        IntegrationHook(self, ReviewBotIntegration)

        self.celery = Celery('reviewbot.tasks')

    def login_user(self):
        """Log in as the configured user.

        This does not depend on the auth backend (hopefully). This is based on
        Client.login() with a small hack that does not require the call to
        authenticate().

        Returns:
            unicode:
            The session key of the new user session.
        """
        user = User.objects.get(pk=self.settings['user'])
        user.backend = 'reviewboard.accounts.backends.StandardAuthBackend'
        engine = import_module(settings.SESSION_ENGINE)

        # Create a fake request to store login details.
        request = HttpRequest()
        request.session = engine.SessionStore()
        login(request, user)
        request.session.save()
        return request.session.session_key

    def send_refresh_tools(self):
        """Request workers to update tool list."""
        self.celery.conf.broker_url = self.settings['broker_url']
        payload = {
            'session': self.login_user(),
            'url': get_server_url(),
        }
        self.celery.control.broadcast('update_tools_list', payload=payload)
