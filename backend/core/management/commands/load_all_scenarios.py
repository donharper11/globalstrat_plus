"""
Scan the scenarios/ directory and load any YAML scenarios not already in the database.

Usage:
    python manage.py load_all_scenarios
"""
import yaml
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.models.scenario import Scenario


class Command(BaseCommand):
    help = "Load all scenario YAML files that are not already present in the database."

    def handle(self, *args, **options):
        scenarios_dir = Path(settings.BASE_DIR) / "scenarios"

        if not scenarios_dir.is_dir():
            self.stderr.write(self.style.ERROR(f"Scenarios directory not found: {scenarios_dir}"))
            return

        yaml_files = sorted(scenarios_dir.glob("*.yaml"))
        if not yaml_files:
            self.stdout.write(self.style.WARNING("No .yaml files found in scenarios/."))
            return

        loaded = []
        skipped = []

        for yaml_path in yaml_files:
            with open(yaml_path, "r") as f:
                data = yaml.safe_load(f)

            scenario_data = data.get("scenario", {})
            name = scenario_data.get("name")

            if not name:
                self.stdout.write(self.style.WARNING(f"  SKIP (no scenario.name): {yaml_path.name}"))
                skipped.append(yaml_path.name)
                continue

            if Scenario.objects.filter(name=name).exists():
                self.stdout.write(f"  SKIP (already loaded): {name}  [{yaml_path.name}]")
                skipped.append(yaml_path.name)
                continue

            self.stdout.write(f"  LOADING: {name}  [{yaml_path.name}]")
            call_command("load_scenario", file=str(yaml_path))
            loaded.append(yaml_path.name)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Loaded: {len(loaded)}  |  Skipped: {len(skipped)}"))
        for f in loaded:
            self.stdout.write(self.style.SUCCESS(f"  + {f}"))
        for f in skipped:
            self.stdout.write(f"  - {f}")
