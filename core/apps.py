from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):

        # Connect the audit signal handlers (logins,
        # assistant access changes) at startup.

        from core import signals  # noqa: F401
