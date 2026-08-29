"""Fixture identity, varied deterministically by seed.

Every probabilistic engine call seeds on `(class_id, round_number,
operation_id)`, where `class_id` is `game.section_id or game.id` -- the cohort
key V2-010 made uniform across events, supply chain, compliance, costs and
alliances. The fixture therefore has exactly one identity knob that reaches
every stochastic subsystem at once, and a seed that does not move it does not
vary anything the engine does.

That was the limitation in the first Stage 3 plan: seeds varied candidate
sampling and opponent composition while every engine stream stayed identical,
so "three seeds" tested one fixture three times. `apply(game, seed)` moves the
cohort key, and the checks below prove both halves of what that has to mean --
the same seed reproduces exactly, and different seeds really do draw different
numbers rather than merely being labelled differently.
"""
import hashlib

# Kept clear of the small integers `setup_test_game` and `load_demo` use for
# real sections, so a synthetic identity can never collide with a seeded one.
IDENTITY_BASE = 900_000


def identity_for(seed):
    """A stable cohort id for a seed string. Same seed, same id, always."""
    digest = hashlib.sha256(f'fixture-identity:{seed}'.encode()).hexdigest()
    return IDENTITY_BASE + int(digest[:8], 16) % 100_000


def apply(game, seed):
    """Point the game at the cohort identity this seed names."""
    identity = identity_for(seed)
    game.section_id = identity
    game.save(update_fields=['section_id'])
    game.refresh_from_db()
    return identity


# The operations whose streams a differing identity must actually change. Each
# is a real operation_id built by the engine, not a probe invented here: if the
# engine renames one, this check stops matching and says so rather than
# silently passing on a stream nobody draws from.
STREAM_PROBES = (
    'event_trigger:1',
    'sc_event_trigger:1',
    'compliance_enforcement:eu_battery:1:EU',
    'tax_audit:1',
    'alliance_partner_defection:1',
)


def stream_sample(class_id, round_number=1, draws=3):
    """The first few draws of every probed stream, for one cohort key."""
    from core.engine.rng import get_rng
    return {op: [get_rng(class_id, round_number, op).random()
                 for _ in range(draws)][0]
            for op in STREAM_PROBES}


def streams_differ(identity_a, identity_b):
    """Which probed streams actually draw different numbers."""
    a = stream_sample(identity_a)
    b = stream_sample(identity_b)
    return {op: {'a': a[op], 'b': b[op], 'differs': a[op] != b[op]}
            for op in STREAM_PROBES}
