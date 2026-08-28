"""Build a sequence-independent snapshot of the tables a section registry names.

Two properties matter and both come from the same mechanism.

**Rows are identified by natural keys, never by surrogate ids.** A row's token
is built from its declared natural key with every foreign key replaced by the
referenced row's token, recursively. Sections are therefore materialised in
dependency order. A table with no natural key gets a token derived from its own
canonical content plus an occurrence index, which is still free of sequence
values. Nothing in a manifest changes because a sequence advanced.

**Row order is imposed, never inherited.** Sections are sorted by token, so the
snapshot does not depend on the database's physical row order, on the planner's
choice of scan, or on insertion sequence. That is what makes the forward /
reverse insertion tests meaningful.
"""
from collections import defaultdict

from django.apps import apps

from core.services.canonical_json import canonical_dumps, canonical_sha256
from core.services.manifest_sections import (
    EXTERNAL_KEYS, MEASURED_TIME_FIELDS, duplicate_models,
)


class SnapshotError(RuntimeError):
    """The registry cannot be materialised as declared."""


def _model(label):
    app_label, model_name = label.split('.')
    return apps.get_model(app_label, model_name)


def _relation_fields(model):
    """attname -> related model label, for every forward relation."""
    return {f.attname: f'{f.related_model._meta.app_label}.'
                       f'{f.related_model.__name__}'
            for f in model._meta.fields
            if f.is_relation and (f.many_to_one or f.one_to_one)}


def natural_key_attnames(section, model):
    """The declared natural key, resolved to database attnames.

    Defaults to the model's ``unique_together`` when it declares exactly one,
    so the key follows the schema rather than a hand-maintained copy of it.
    """
    if section.key is not None:
        declared = section.key
    else:
        unique_together = list(model._meta.unique_together)
        if len(unique_together) != 1:
            return None
        declared = tuple(unique_together[0])
    by_name = {f.name: f for f in model._meta.fields}
    resolved = []
    for name in declared:
        field = by_name.get(name) or by_name.get(name[:-3] if name.endswith('_id') else name)
        if field is None:
            raise SnapshotError(
                f'Section "{section.name}" names key field "{name}", which '
                f'{model.__name__} does not have.')
        resolved.append(field.attname)
    return tuple(resolved)


def section_field_plan(section, model, mode):
    """Split a model's concrete fields into hashed, relation and dropped sets.

    ``mode`` is ``'input'`` or ``'output'``; measured wall-clock fields are
    hashed in the input snapshot (frozen facts about the starting state) and
    dropped from the output snapshot (they differ between two correct runs).
    """
    relations = _relation_fields(model)
    hashed, narrative, dropped = [], [], {}
    for field in model._meta.fields:
        attname = field.attname
        if field.primary_key:
            dropped[attname] = ('Surrogate primary key; the row is identified '
                                'by its natural-key token instead.')
            continue
        if attname in relations:
            continue  # carried as a token by _row_relations
        if attname in section.exclude:
            dropped[attname] = section.exclude[attname]
            continue
        if field.name in section.exclude:
            dropped[attname] = section.exclude[field.name]
            continue
        if field.name in section.narrative_fields or attname in section.narrative_fields:
            narrative.append(attname)
            continue
        if mode == 'output' and attname in MEASURED_TIME_FIELDS:
            dropped[attname] = MEASURED_TIME_FIELDS[attname]
            continue
        hashed.append(attname)
    known_names = ({f.name for f in model._meta.fields} |
                   {f.attname for f in model._meta.fields})
    unknown = set(section.exclude) - known_names
    if unknown:
        raise SnapshotError(
            f'Section "{section.name}" excludes {sorted(unknown)}, which '
            f'{model.__name__} does not have.')
    return {'hashed': tuple(sorted(hashed)), 'relations': relations,
            'narrative': tuple(sorted(narrative)), 'dropped': dropped}


def _order_sections(sections):
    """Materialisation order: a section follows every section it points at."""
    duplicates = duplicate_models(sections)
    if duplicates:
        raise SnapshotError(
            f'One snapshot cannot contain two sections for {sorted(duplicates)}; '
            f'a row would then have two different tokens.')
    by_model = {section.model: section for section in sections}
    ordered, state = [], {}

    def visit(section, trail):
        mark = state.get(section.name)
        if mark == 'done':
            return
        if mark == 'visiting':
            raise SnapshotError(
                'Foreign-key cycle between manifest sections: ' +
                ' -> '.join(trail + [section.name]))
        state[section.name] = 'visiting'
        for label in sorted(set(_relation_fields(_model(section.model)).values())):
            parent = by_model.get(label)
            if parent is not None and parent.name != section.name:
                visit(parent, trail + [section.name])
        state[section.name] = 'done'
        ordered.append(section)

    for section in sections:
        visit(section, [])
    return ordered


class Snapshot:
    """Materialised sections plus the digests and diagnostics they produce."""

    def __init__(self, sections, mode, scenario_id, game_id):
        self.sections = _order_sections(list(sections))
        self.mode = mode
        self.scenario_id = scenario_id
        self.game_id = game_id
        self.rows = {}
        self.narrative_rows = {}
        self.field_plans = {}
        self.tokens = defaultdict(dict)      # model label -> {pk: token}
        self.unmapped_references = []
        self._external_cache = {}

    # -- token resolution ---------------------------------------------------

    def _external_token(self, label, pk):
        if pk is None:
            return None
        cached = self._external_cache.get((label, pk))
        if cached is not None:
            return cached
        key_fields = EXTERNAL_KEYS.get(label)
        if not key_fields:
            self.unmapped_references.append({'model': label, 'pk': pk})
            token = f'{label}#surrogate:{pk}'
        else:
            values = _model(label).objects.filter(pk=pk).values(*key_fields).first()
            if values is None:
                token = f'{label}#missing'
            else:
                token = '{}({})'.format(label, '|'.join(
                    canonical_dumps(values[name]) for name in key_fields))
        self._external_cache[(label, pk)] = token
        return token

    def token_for(self, label, pk):
        if pk is None:
            return None
        known = self.tokens.get(label)
        if known is not None and pk in known:
            return known[pk]
        return self._external_token(label, pk)

    # -- materialisation ----------------------------------------------------

    def _queryset(self, section, model):
        from core.services.manifest_sections import SCENARIO
        scope_id = self.scenario_id if section.scope == SCENARIO else self.game_id
        # Ordering is imposed on the rendered rows, but an explicit ORDER BY
        # keeps the fetch itself reproducible and cheap to reason about.
        return model.objects.filter(**{section.lookup: scope_id}).order_by('pk')

    def build(self):
        for section in self.sections:
            model = _model(section.model)
            plan = section_field_plan(section, model, self.mode)
            self.field_plans[section.name] = plan
            key_attnames = natural_key_attnames(section, model)
            columns = ['pk'] + list(plan['hashed']) + list(plan['relations']) + \
                list(plan['narrative'])
            raw = list(self._queryset(section, model).values(*columns))

            rendered, narratives = [], []
            for record in raw:
                relations = {name: self.token_for(label, record[name])
                             for name, label in sorted(plan['relations'].items())}
                body = {name: record[name] for name in plan['hashed']}
                body.update(relations)
                rendered.append({'pk': record['pk'], 'body': body,
                                 'narrative': {name: record[name]
                                               for name in plan['narrative']}})

            tokens = self._assign_tokens(section, key_attnames, rendered, plan)
            for row, token in zip(rendered, tokens):
                self.tokens[section.model][row['pk']] = token

            ordered = sorted(zip(tokens, rendered), key=lambda pair: pair[0])
            self.rows[section.name] = [
                dict(_key=token, **row['body']) for token, row in ordered]
            narratives = [dict(_key=token, **row['narrative'])
                          for token, row in ordered if row['narrative']]
            if narratives:
                self.narrative_rows[section.name] = narratives
        return self

    def _assign_tokens(self, section, key_attnames, rendered, plan):
        if key_attnames:
            tokens, seen = [], {}
            for row in rendered:
                parts = []
                for attname in key_attnames:
                    if attname in plan['relations']:
                        parts.append(str(row['body'][attname]))
                    else:
                        parts.append(canonical_dumps(row['body'][attname]))
                token = '{}({})'.format(section.name, '|'.join(parts))
                if token in seen:
                    raise SnapshotError(
                        f'Natural key {key_attnames} is not unique in section '
                        f'"{section.name}": {token} appears twice. Declare a '
                        f'key that identifies a row, or set key=None to use a '
                        f'content key.')
                seen[token] = True
                tokens.append(token)
            return tokens
        # Content key: identity from the row's own canonical content, with an
        # occurrence index so byte-identical rows stay distinguishable.
        digests = [canonical_sha256(row['body'])[:32] for row in rendered]
        counts = defaultdict(int)
        tokens = []
        for digest in digests:
            counts[digest] += 1
            tokens.append(f'{section.name}#{digest}:{counts[digest]}')
        return tokens

    # -- outputs ------------------------------------------------------------

    def section_digests(self):
        return {name: {'sha256': canonical_sha256(rows), 'rows': len(rows)}
                for name, rows in sorted(self.rows.items())}

    def narrative_digests(self):
        return {name: {'sha256': canonical_sha256(rows), 'rows': len(rows)}
                for name, rows in sorted(self.narrative_rows.items())}

    def field_inventory(self):
        """The declared shape of the snapshot, for the schema-drift test."""
        inventory = {}
        for section in self.sections:
            model = _model(section.model)
            plan = self.field_plans[section.name]
            inventory[section.name] = {
                'model': section.model,
                'scope': section.scope,
                'lookup': section.lookup,
                'natural_key': list(natural_key_attnames(section, model) or ()),
                'hashed': list(plan['hashed']),
                'relations': dict(sorted(plan['relations'].items())),
                'narrative': list(plan['narrative']),
                'dropped': dict(sorted(plan['dropped'].items())),
            }
        return inventory


def build_snapshot(sections, mode, scenario_id, game_id):
    return Snapshot(sections, mode, scenario_id, game_id).build()
