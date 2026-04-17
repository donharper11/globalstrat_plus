"""
Deterministic RNG utility for engine operations.

The engine must be reproducible: identical inputs must yield identical
probabilistic outcomes across runs. This enables replay, audit, and
fairness across parallel student sections running the same scenario
configuration.

Seeding convention
------------------
Every probabilistic engine call constructs a ``random.Random`` instance
seeded on ``(class_id, round_number, operation_id)``. The same triple
always returns the same draws.

``class_id`` is the identifier of the student cohort running the game —
for sectioned games, ``game.section_id``; for unsectioned/solo games,
``game.id``. Callers should pass ``game.section_id or game.id``.

``operation_id`` is a free-form string that must uniquely identify the
probabilistic operation *within a round*. Examples:

    "event_trigger:{event_template.id}"
    "compliance_event_roll:{template.id}:{team.id}"
    "tax_audit:{team.id}"
    "alliance_partner_defection:{alliance.id}"
    "govt_regulatory_relaxation:{market_code}"

Keep operation_id strings stable — changing them silently resegments the
RNG stream and invalidates replay against prior rounds.
"""
import hashlib
import random


def get_rng(class_id, round_number, operation_id):
    """Return a seeded :class:`random.Random` for one engine operation.

    Args:
        class_id: Student cohort identifier. Pass
            ``game.section_id or game.id``.
        round_number: Integer round number.
        operation_id: String uniquely identifying the operation within
            the round (see module docstring for conventions).

    Returns:
        A fresh ``random.Random`` instance. Safe to call ``.random()``,
        ``.choice()``, etc. on it. Each call with the same triple
        returns an RNG in the same initial state.
    """
    seed_str = f"{class_id}:{round_number}:{operation_id}"
    seed_int = int(hashlib.sha256(seed_str.encode()).hexdigest()[:16], 16)
    return random.Random(seed_int)
