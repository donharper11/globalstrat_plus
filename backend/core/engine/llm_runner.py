"""
CC-32H: Async LLM runner for concurrent narrative LLM calls.

Provides call_llm_async() for single calls and run_llm_batch_sync() for
concurrent batches. Used by Phase 2 narrative generation to fire all LLM
calls simultaneously instead of sequentially.

Endpoint: the local LiteLLM fleet proxy when NARRATIVE_LLM_URL and
NARRATIVE_LLM_KEY are both set, otherwise DashScope's compatible-mode API as
before. Only Phase 2 narratives use this runner. Student communication scoring
(core/rag/communication_eval.py) feeds graded coherence and deliberately still
calls DashScope directly -- do not route it through here without its own test.
"""
import asyncio
import json
import logging

import httpx
from django.conf import settings

logger = logging.getLogger('llm_runner')

# The proxy's GPU is shared with live student chat, so batches are paced.
MAX_CONCURRENT = 4
# A thinking model (`analyst`) averages about 70s per narrative call.
TIMEOUT_PER_CALL = 150

DASHSCOPE_DEFAULT_URL = (
    'https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions')


def _proxy_configured():
    return bool(getattr(settings, 'NARRATIVE_LLM_URL', '')
                and getattr(settings, 'NARRATIVE_LLM_KEY', ''))


def _get_url():
    if _proxy_configured():
        return settings.NARRATIVE_LLM_URL
    return getattr(settings, 'DASHSCOPE_COMPATIBLE_URL', DASHSCOPE_DEFAULT_URL)


def _get_key():
    if _proxy_configured():
        return settings.NARRATIVE_LLM_KEY
    return getattr(settings, 'DASHSCOPE_API_KEY', '')


def _get_model():
    return getattr(settings, 'DASHSCOPE_MODEL', 'qwen3-max-preview')


def resolve_model(model=None):
    """The model name actually sent for a call.

    A per-call name (`analyst`, `tutor`) is a proxy alias that DashScope does not
    know, so it applies only when the proxy is configured; the DashScope
    fallback keeps sending DASHSCOPE_MODEL exactly as before.
    """
    if model and _proxy_configured():
        return model
    return _get_model()


def llm_configured():
    """Whether narrative calls have an endpoint key to use at all."""
    return bool(_get_key())


def endpoint_url():
    """The chat-completions URL narrative calls go to. Never includes a key."""
    return _get_url()


async def call_llm_async(prompt, system_prompt=None, max_tokens=1500,
                          temperature=0.3, enable_thinking=None,
                          thinking_budget=None, model=None):
    """Single async LLM call via httpx.

    `enable_thinking=None` leaves thinking to the model: through the proxy the
    alias decides (`analyst` thinks, `tutor` does not) and the proxy raises
    max_tokens so thinking cannot consume the answer. Sending an explicit False
    here would switch `analyst`'s thinking off.
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

    if _proxy_configured():
        # vLLM reads Qwen's switch from chat_template_kwargs at the top level.
        if enable_thinking is not None:
            body["chat_template_kwargs"] = {"enable_thinking": bool(enable_thinking)}
    elif enable_thinking:
        body["extra_body"] = {"enable_thinking": True}
        if thinking_budget:
            body["extra_body"]["thinking_budget"] = thinking_budget

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
            model (opt; proxy alias, defaults to DASHSCOPE_MODEL)

    Returns:
        dict mapping call['id'] -> result dict
    """
    if not _get_key():
        logger.warning("No narrative LLM key (NARRATIVE_LLM_KEY or "
                       "DASHSCOPE_API_KEY) — skipping LLM batch")
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
