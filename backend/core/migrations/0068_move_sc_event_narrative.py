"""Move existing SC-event prose out of the competitive JSON column.

`resolution_data` carries the `pending` / `applied` flags the engine reads to
decide whether an instructor-injected event fires, so it is inside the
competitive hash. Phase 2 used to append its narrative to the same column.
Rows written before that split keep the prose in the JSON; this moves it to
the dedicated field so no competitive column holds narrative text.

This changes where text is stored, never a published result. Rounds resolved
before the split already did not reconcile with their own manifests — that is
V2-015, which is what the split fixes going forward.
"""
from django.db import migrations


def move_narrative_out(apps, schema_editor):
    SCEventInstance = apps.get_model('core', 'SCEventInstance')
    moved = 0
    for instance in SCEventInstance.objects.all().order_by('pk').iterator():
        data = instance.resolution_data or {}
        text = data.pop('narrative', None)
        if text is None:
            continue
        instance.narrative = instance.narrative or text
        instance.resolution_data = data
        instance.save(update_fields=['narrative', 'resolution_data'])
        moved += 1
    if moved:
        print(f'  moved narrative out of resolution_data on {moved} row(s)')


def put_narrative_back(apps, schema_editor):
    SCEventInstance = apps.get_model('core', 'SCEventInstance')
    for instance in SCEventInstance.objects.exclude(narrative='').order_by(
            'pk').iterator():
        instance.resolution_data = {**(instance.resolution_data or {}),
                                    'narrative': instance.narrative}
        instance.save(update_fields=['resolution_data'])


class Migration(migrations.Migration):
    dependencies = [('core', '0067_narrativejob_degraded')]
    operations = [migrations.RunPython(move_narrative_out, put_narrative_back)]
