"""The checked-in shape of the manifest envelope.

Hash equality proves two runs agreed. It does not prove the manifest still
covers what it claims to cover: a model that quietly gains a field would
produce a new, self-consistent hash on every run and nobody would notice the
envelope moved. The inventory below is the reviewed record of that shape —
every section, its natural key, and every field that is hashed, tokenised,
treated as narrative or dropped with a reason.
"""
import pathlib

from core.services.canonical_json import canonical_sha256
from core.services.manifest_sections import (
    INPUT_SECTIONS, NARRATIVE_SECTIONS, OUTPUT_SECTIONS,
)
from core.services.manifest_snapshot import Snapshot


SCHEMA_INVENTORY_PATH = str(
    pathlib.Path(__file__).resolve().parent / 'manifest_schema_v2.json')


def _inventory(sections, mode):
    # Field classification is pure metadata; no database access is needed.
    snapshot = Snapshot(sections, mode, scenario_id=None, game_id=None)
    for section in snapshot.sections:
        from core.services.manifest_snapshot import _model, section_field_plan
        snapshot.field_plans[section.name] = section_field_plan(
            section, _model(section.model), mode)
    return snapshot.field_inventory()


def build_schema_inventory():
    inventory = {
        'schema_version': 2,
        'input': _inventory(INPUT_SECTIONS, 'input'),
        'output': _inventory(OUTPUT_SECTIONS, 'output'),
        'narrative': _inventory(NARRATIVE_SECTIONS, 'output'),
    }
    inventory['sha256'] = canonical_sha256(
        {key: value for key, value in inventory.items() if key != 'sha256'})
    return inventory
