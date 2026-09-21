"""
Every model call this platform makes.

All of them go to the local LiteLLM fleet gateway: no platform code talks to a
third-party provider, and no provider SDK is imported anywhere (2026-09-16).
The gateway serves the local fleet under purpose aliases -- `analyst` (Qwen3.6
with thinking, for analysis) and `tutor` (thinking off, for short or
interactive work) -- and MODEL_BY_PURPOSE below is the one place that says
which purpose gets which.

With no gateway configured there is no model: callers fall back to their
templates and heuristics, which every one of them already does.
"""
import asyncio
import json
import logging

import httpx
from django.conf import settings

logger = logging.getLogger('llm_runner')

# The gateway's GPU is shared with live student chat, so batches are paced.
MAX_CONCURRENT = 4
# A thinking model (`analyst`) averages about 70s on a narrative call.
TIMEOUT_PER_CALL = 150

# What each kind of work is worth spending thinking time on. Measured, not
# guessed: local Qwen3.6 beat the cloud model this platform used to call on
# narrative prose, and on communication scoring `tutor` was the most
# self-consistent of the candidates and fast enough to run while a student
# waits (analyst: 45s, tutor: 7s).
MODEL_BY_PURPOSE = {
    # Phase 2 round narratives
    'narrative_deep': 'analyst',     # briefing, coherence commentary, coaching
    'narrative_fast': 'tutor',       # outlook, sc_event, compliance notices
    # Interactive, a person is waiting
    'research_brief': 'tutor',
    'persona_reply': 'tutor',
    'query_translation': 'tutor',
    # Scored once at submission. Feedback only: R31 severed it from graded
    # coherence. (grading.py's `communication_quality` rubric component still
    # reads it if a rubric selects one -- an open owner question.)
    'communication_eval': 'tutor',
    # Batch analysis
    'persona_reaction': 'analyst',
    'coherence_rag': 'analyst',
    'teaching_note': 'analyst',
    'event_narrative': 'tutor',
    'briefing_framework': 'tutor',
}

DEFAULT_PURPOSE = 'narrative_fast'


def model_for_purpose(purpose):
    """The gateway alias for one kind of work.

    `LLM_PURPOSE_MODELS` (a dict, from JSON in the environment) overrides any
    entry, so a model can be changed without a code edit.
    """
    overrides = getattr(settings, 'LLM_PURPOSE_MODELS', None) or {}
    return overrides.get(purpose) or MODEL_BY_PURPOSE[purpose]


def _gateway_configured():
    return bool(getattr(settings, 'LLM_GATEWAY_URL', '')
                and getattr(settings, 'LLM_GATEWAY_KEY', ''))


def _get_url():
    return getattr(settings, 'LLM_GATEWAY_URL', '')


def _get_key():
    return getattr(settings, 'LLM_GATEWAY_KEY', '')


def resolve_model(model=None):
    """The model name actually sent: an explicit one, else the default purpose."""
    return model or model_for_purpose(DEFAULT_PURPOSE)


def llm_configured():
    """Whether a gateway is configured at all."""
    return _gateway_configured()


def endpoint_url():
    """The chat-completions URL calls go to. Never includes a key."""
    return _get_url()


def embeddings_url():
    """The embeddings endpoint beside the configured chat endpoint."""
    url = _get_url()
    if url.endswith('/chat/completions'):
        return url[:-len('/chat/completions')] + '/embeddings'
    return url


def chat_completion(messages, model=None, max_tokens=1500, temperature=0.3,
                    timeout=None):
    """One blocking chat completion. Returns the text, or None.

    Returning None rather than raising keeps every caller's fallback behaviour:
    they already treat "no answer" as "use the template".
    """
    if not llm_configured():
        logger.warning('No LLM gateway configured — skipping call')
        return None

    body = {
        'model': resolve_model(model),
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': temperature,
    }
    headers = {
        'Authorization': f'Bearer {_get_key()}',
        'Content-Type': 'application/json',
    }
    try:
        response = httpx.post(_get_url(), json=body, headers=headers,
                              timeout=timeout or TIMEOUT_PER_CALL)
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
    except httpx.TimeoutException:
        logger.warning('LLM call timed out after %ss', timeout or TIMEOUT_PER_CALL)
        return None
    except Exception as error:                        # noqa: BLE001
        logger.error('LLM call failed: %s', error)
        return None


async def call_llm_async(prompt, system_prompt=None, max_tokens=1500,
                          temperature=0.3, enable_thinking=None,
                          thinking_budget=None, model=None):
    """Single async LLM call via httpx.

    `enable_thinking=None` leaves thinking to the alias (`analyst` thinks,
    `tutor` does not); the gateway raises max_tokens so thinking cannot consume
    the answer.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": resolve_model(model),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    # vLLM reads Qwen's switch from chat_template_kwargs at the top level. Left
    # unset, the alias decides -- and an explicit False here would turn
    # `analyst`'s thinking off.
    if enable_thinking is not None:
        body["chat_template_kwargs"] = {"enable_thinking": bool(enable_thinking)}

    headers = {
        "Authorization": f"Bearer {_get_key()}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=TIMEOUT_PER_CALL) as client:
        try:
            response = await client.post(_get_url(), json=body, headers=headers)
            response.raise_for_status()
            data = response.json()

            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return {"success": True, "content": content}

        except httpx.TimeoutException:
            logger.warning(f"LLM call timed out after {TIMEOUT_PER_CALL}s")
            return {"success": False, "error": "timeout", "content": ""}
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {"success": False, "error": str(e), "content": ""}


async def run_llm_batch(calls):
    """
    Run multiple LLM calls concurrently with semaphore limiting.

    Args:
        calls: list of dicts with keys:
            id, prompt, system_prompt (opt), max_tokens (opt),
            temperature (opt), enable_thinking (opt), thinking_budget (opt),
            model (opt; gateway alias, defaults to the narrative_fast model)

    Returns:
        dict mapping call['id'] -> result dict
    """
    if not _get_key():
        logger.warning("No LLM gateway configured — skipping LLM batch")
        return {c['id']: {"success": False, "error": "no_api_key", "content": ""} for c in calls}

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    results = {}

    async def _call_with_semaphore(call):
        async with semaphore:
            result = await call_llm_async(
                prompt=call['prompt'],
                system_prompt=call.get('system_prompt'),
                max_tokens=call.get('max_tokens', 1500),
                temperature=call.get('temperature', 0.3),
                enable_thinking=call.get('enable_thinking'),
                thinking_budget=call.get('thinking_budget'),
                model=call.get('model'),
            )
            results[call['id']] = result

    tasks = [_call_with_semaphore(call) for call in calls]
    await asyncio.gather(*tasks, return_exceptions=True)

    successful = sum(1 for r in results.values() if r.get('success'))
    logger.info(f"LLM batch: {successful}/{len(calls)} succeeded")

    return results


def build_language_instruction(language):
    """Append language instruction for LLM output."""
    if language == 'zh-CN':
        return "\n\n请完全使用简体中文回复。使用专业的商业术语。"
    return ""


def run_llm_batch_sync(calls):
    """Synchronous wrapper for run_llm_batch. Safe from Django views/threads."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(run_llm_batch(calls))
    finally:
        loop.close()
