from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # A-03: take the source digest now, while the disk still holds the code
        # this process is loading. Taken lazily it described the disk at the
        # first resolution instead, which can be days after start. Best-effort
        # and cheap (one walk of backend/); it never stops a process starting.
        from core.services.build_identity import prime_source_tree_digest
        prime_source_tree_digest()
