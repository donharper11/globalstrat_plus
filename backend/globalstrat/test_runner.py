"""
Test runner that can actually build a test database for this project.

Roughly 50 of the core models are managed=False — legacy raw-SQL tables
(`users`, `enrollment`, `simulation_state`, ...) that Django never creates.
Two *managed* models (DecisionChangeLog, BriefingReadStatus) hold foreign keys
into the unmanaged `users` table, so migrating a fresh database fails at the
deferred FK constraint:

    django.db.utils.ProgrammingError: relation "users" does not exist

which made `manage.py test` impossible to run against a clean database.

For tests we flip every model to managed=True and build the schema straight
from the models, skipping migration replay entirely. Migrations are disabled
for *every* app, not just `core`: Django syncs unmigrated apps before it runs
migrations, so leaving `auth` migrated would have core's tables created before
`auth_user` existed. With everything unmigrated, all tables are created inside
one schema_editor block and the foreign keys are applied as deferred SQL at
the end, so creation order stops mattering.

Production is untouched: this runner is only used by `manage.py test`, and both
the managed flags and MIGRATION_MODULES are restored on teardown.

Because migrations are skipped, anything a migration installs beyond the model
schema has to be installed here too. `core.services.audit_guards` is the single
source for the append-only trigger DDL, and both this runner and migration
0070 apply it.
"""
from django.apps import apps
from django.conf import settings
from django.test.runner import DiscoverRunner


class _DisableMigrations(dict):
    """Makes every app look unmigrated, so migrate() falls back to syncdb."""

    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


class GlobalStratTestRunner(DiscoverRunner):

    def setup_databases(self, **kwargs):
        self._original_migration_modules = getattr(
            settings, 'MIGRATION_MODULES', {},
        )
        settings.MIGRATION_MODULES = _DisableMigrations()
        config = super().setup_databases(**kwargs)
        # Skipping migration replay also skips the RunSQL migration that
        # installs the append-only audit triggers, so without this the test
        # database is the one place those guards do not exist — which is
        # exactly where they need to be provable. Installed from the same
        # module the migration uses, so the two cannot drift.
        from django.db import connections
        from core.services.audit_guards import install
        for alias in connections:
            install(connections[alias])
        return config

    def teardown_databases(self, old_config, **kwargs):
        super().teardown_databases(old_config, **kwargs)
        settings.MIGRATION_MODULES = self._original_migration_modules

    def setup_test_environment(self, **kwargs):
        self._unmanaged = [m for m in apps.get_models() if not m._meta.managed]
        for model in self._unmanaged:
            model._meta.managed = True
        super().setup_test_environment(**kwargs)

    def teardown_test_environment(self, **kwargs):
        super().teardown_test_environment(**kwargs)
        for model in self._unmanaged:
            model._meta.managed = False
