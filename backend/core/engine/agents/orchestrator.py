"""
CC-32E: Agent Orchestrator — Convergence loop coordinating all agent classes.

Replaces scattered agent processing in the engine pipeline with a unified
multi-agent coordination layer. Each agent evaluates the same state snapshot,
proposes actions, cross-agent dependencies are resolved, and actions are
applied atomically.
"""
import logging
from typing import Dict, List

from django.db import transaction
from django.utils import timezone

from .base import AgentAction
from .registry import AgentRegistry
from .state import build_state_snapshot

logger = logging.getLogger('agent_orchestrator')

MAX_CONVERGENCE_ITERATIONS = 3
CONVERGENCE_THRESHOLD = 0.05


def run_agent_cycle(game, round_obj, context=None):
    """
    Main orchestration entry point.

    Called from advance_round AFTER human decision processing (Steps 1-14).
    Replaces:
    - Step 12.8 (AI capital markets / investor trading)
    - Alliance satisfaction post-processing
    - Government processing (placeholder for CC-32F)
    """
    agents = AgentRegistry.get_all()

    if not agents:
        # No agents registered — fall back to legacy processing
        logger.warning("No agents registered — running legacy agent processing")
        _run_legacy_processing(game, round_obj, context)
        return {'actions': [], 'narratives': [], 'convergence_iterations': 0}

    # 1. Build immutable state snapshot
    snapshot = build_state_snapshot(game, round_obj)
    logger.info(
        f"Agent cycle starting: Round {round_obj.round_number}, "
        f"{len(snapshot.teams)} teams, {len(snapshot.markets)} markets"
    )

    # 2. Initial evaluation — each agent proposes actions
    all_actions = {}
    agent_summary = {}
    for agent in agents:
        try:
            actions = agent.evaluate(snapshot)
            all_actions[agent.agent_class] = actions
            agent_summary[agent.agent_class] = {
                'actions_proposed': len(actions),
                'actions_revised': 0,
                'actions_applied': 0,
            }
            logger.info(f"  {agent.agent_class}: proposed {len(actions)} actions")
        except Exception as e:
            logger.error(f"  {agent.agent_class} evaluation failed: {e}")
            all_actions[agent.agent_class] = []
            agent_summary[agent.agent_class] = {
                'actions_proposed': 0,
                'actions_revised': 0,
                'actions_applied': 0,
                'error': str(e),
            }

    # 3. Convergence loop — agents revise based on each other's proposals
    flat_actions = _flatten_actions(all_actions)
    iteration = 0

    for iteration in range(MAX_CONVERGENCE_ITERATIONS):
        revised_actions = {}
        changes = 0

        for agent in agents:
            own_actions = all_actions.get(agent.agent_class, [])
            try:
                revised = agent.resolve_dependencies(own_actions, flat_actions)
                if _actions_differ(own_actions, revised):
                    changes += 1
                    agent_summary[agent.agent_class]['actions_revised'] += 1
                revised_actions[agent.agent_class] = revised
            except Exception as e:
                logger.error(f"  {agent.agent_class} dependency resolution failed: {e}")
                revised_actions[agent.agent_class] = own_actions

        all_actions = revised_actions
        flat_actions = _flatten_actions(all_actions)

        logger.info(f"  Convergence iteration {iteration + 1}: {changes} agents revised")

        if changes == 0:
            logger.info(f"  Converged after {iteration + 1} iterations")
            break
    else:
        logger.warning(f"  Did not converge within {MAX_CONVERGENCE_ITERATIONS} iterations")

    # 4. Sort by priority and dependency order
    final_actions = _sort_by_dependency(flat_actions)

    # 5. Apply all actions atomically
    errors = []
    with transaction.atomic():
        for agent in agents:
            agent_actions = [a for a in final_actions if a.agent_class == agent.agent_class]
            if agent_actions:
                try:
                    agent.apply_actions(agent_actions, game, round_obj)
                    agent_summary[agent.agent_class]['actions_applied'] = len(agent_actions)
                    logger.info(f"  {agent.agent_class}: applied {len(agent_actions)} actions")
                except Exception as e:
                    logger.error(f"  {agent.agent_class} action application failed: {e}")
                    errors.append({
                        'agent': agent.agent_class,
                        'phase': 'apply',
                        'error': str(e),
                    })
                    raise  # Rollback entire transaction

    # 6. Generate narratives
    narratives = []
    for agent in agents:
        agent_actions = [a for a in final_actions if a.agent_class == agent.agent_class]
        try:
            agent_narratives = agent.get_narrative(agent_actions)
            narratives.extend(agent_narratives)
        except Exception as e:
            logger.error(f"  {agent.agent_class} narrative generation failed: {e}")

    # 7. Store agent cycle log
    _store_cycle_log(
        game, round_obj, iteration + 1,
        final_actions, narratives, agent_summary, errors,
    )

    # 8. Store narratives for briefing engine
    _store_agent_narratives(game, round_obj, narratives)

    logger.info(
        f"Agent cycle complete: {len(final_actions)} actions, "
        f"{len(narratives)} narratives, {iteration + 1} iterations"
    )

    return {
        'actions': final_actions,
        'narratives': narratives,
        'convergence_iterations': iteration + 1,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten_actions(all_actions: Dict[str, list]) -> List[AgentAction]:
    """Flatten all agent actions into a single list."""
    flat = []
    for actions in all_actions.values():
        flat.extend(actions)
    return flat


def _actions_differ(old: List[AgentAction], new: List[AgentAction]) -> bool:
    """Check if an agent's actions changed between iterations."""
    if len(old) != len(new):
        return True

    for o, n in zip(old, new):
        if o.action_type != n.action_type:
            return True
        if o.parameters != n.parameters:
            for key in set(list(o.parameters.keys()) + list(n.parameters.keys())):
                old_val = o.parameters.get(key)
                new_val = n.parameters.get(key)
                if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
                    denom = max(abs(old_val), 1)
                    if abs(old_val - new_val) / denom > CONVERGENCE_THRESHOLD:
                        return True
                elif old_val != new_val:
                    return True

    return False


def _sort_by_dependency(actions: List[AgentAction]) -> List[AgentAction]:
    """Sort actions by dependency and priority."""
    action_types_available = set(a.action_type for a in actions)

    independent = [
        a for a in actions
        if not any(d in action_types_available for d in a.dependencies)
    ]
    dependent = [
        a for a in actions
        if any(d in action_types_available for d in a.dependencies)
    ]

    independent.sort(key=lambda a: a.priority)
    dependent.sort(key=lambda a: a.priority)

    return independent + dependent


def _store_cycle_log(game, round_obj, iterations, actions, narratives,
                     agent_summary, errors):
    """Store agent cycle log for monitoring and debugging."""
    try:
        from core.models.cc32e_models import AgentCycleLog

        action_log = []
        for a in actions:
            action_log.append({
                'agent_class': a.agent_class,
                'agent_id': a.agent_id,
                'action_type': a.action_type,
                'target_team': a.target_team,
                'target_market': a.target_market,
                'priority': a.priority,
                # Don't serialize full parameters — could be large
                'param_keys': list(a.parameters.keys()),
            })

        AgentCycleLog.objects.update_or_create(
            game=game, round=round_obj,
            defaults={
                'completed_at': timezone.now(),
                'convergence_iterations': iterations,
                'total_actions': len(actions),
                'total_narratives': len(narratives),
                'agent_summary': agent_summary,
                'action_log': action_log,
                'errors': errors,
            },
        )
    except Exception as e:
        logger.error(f"Failed to store agent cycle log: {e}")


def _store_agent_narratives(game, round_obj, narratives):
    """Store narratives for consumption by briefing engine and ticker."""
    if not narratives:
        return

    try:
        from core.models.cc32e_models import AgentCycleLog
        log = AgentCycleLog.objects.filter(game=game, round=round_obj).first()
        if log:
            log.narrative_items = narratives
            log.save(update_fields=['narrative_items'])
    except Exception as e:
        logger.error(f"Failed to store agent narratives: {e}")


def _run_legacy_processing(game, round_obj, context):
    """Fallback to legacy agent processing if no agents are registered."""
    if context is None:
        return

    # Legacy Step 12.8: AI Capital Markets
    try:
        from core.engine.capital_markets import process_capital_markets
        process_capital_markets(context)
    except Exception as e:
        context.log.append(f'Legacy CC-26 capital markets failed: {e}')
