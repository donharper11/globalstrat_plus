"""
CC-32H: Async LLM runner for concurrent DashScope API calls.

Provides call_llm_async() for single calls and run_llm_batch_sync() for
concurrent batches. Used by Phase 2 narrative generation to fire all LLM
calls simultaneously instead of sequentially.
"""
import asyncio
import json
import logging

import httpx
from django.conf import settings

logger = logging.getLogger('llm_runner')

MAX_CONCURRENT = 8
TIMEOUT_PER_CALL = 30


def _get_url():
    return getattr(
        settings, 'DASHSCOPE_COMPATIBLE_URL',
        'https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions',
    )


def _get_key():
    return getattr(settings, 'DASHSCOPE_API_KEY', '')


def _get_model():
    return getattr(settings, 'DASHSCOPE_MODEL', 'qwen3-max-preview')


async def call_llm_async(prompt, system_prompt=None, max_tokens=1500,
                          temperature=0.3, enable_thinking=False,
                          thinking_budget=None):
    """Single async LLM call via httpx."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": _get_model(),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    if enable_thinking:
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
            temperature (opt), enable_thinking (opt), thinking_budget (opt)

    Returns:
        dict mapping call['id'] -> result dict
    """
    if not _get_key():
        logger.warning("No DASHSCOPE_API_KEY — skipping LLM batch")
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
                enable_thinking=call.get('enable_thinking', False),
                thinking_budget=call.get('thinking_budget'),
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
