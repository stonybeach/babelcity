"""LLM API communication. Ported from _ask_llm, _ask_llm_json, _extract_json, _remove_think_tags in translate_epubs_new.py."""

import json
import re
import time
from typing import Any, Dict, Optional

from openai import OpenAI


DEFAULT_LLM_PARAMS: Dict[str, Any] = {
    "max_tokens": 8192,
    "temperature": 1.0,
    "top_p": 0.95,
    "min_p": 0,
    "top_k": None,
    "repetition_penalty": 1,
    "frequency_penalty": 0.05,
    "presence_penalty": 0.0,
}

# Parameters that are passed via the OpenAI `extra_body` extension.
_EXTRA_BODY_PARAMS = ("min_p", "repetition_penalty", "top_k")


def _create_client(base_url, api_key):
    return OpenAI(base_url=base_url, api_key=api_key)


def _p(val, default):
    """Get value or default if None."""
    return val if val is not None else default


def normalize_llm_config(llm_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fill in missing or None LLM parameters with DEFAULT_LLM_PARAMS.

    Returns a new dict where every key from DEFAULT_LLM_PARAMS is present.
    Keys not in DEFAULT_LLM_PARAMS (e.g. base_url, api_key, model) are
    passed through unchanged.
    """
    if llm_config is None:
        llm_config = {}
    normalized = dict(llm_config)
    for key, default_val in DEFAULT_LLM_PARAMS.items():
        if normalized.get(key) is None:
            normalized[key] = default_val
    return normalized


def _get_llm_kwargs(llm_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Extract LLM call keyword arguments from a config dict, applying defaults.

    Returns a dict suitable for passing as **kwargs to ask_llm / ask_llm_json,
    including connection params (base_url, api_key, model) and all generation
    parameters with defaults filled in for any missing or None values.
    """
    cfg = normalize_llm_config(llm_config)
    return {
        "base_url": cfg.get("base_url", "http://localhost:8080/v1"),
        "api_key": cfg.get("api_key", "not-needed"),
        "model": cfg.get("model", "default"),
        "max_tokens": cfg["max_tokens"],
        "temperature": cfg["temperature"],
        "top_p": cfg["top_p"],
        "min_p": cfg["min_p"],
        "repetition_penalty": cfg["repetition_penalty"],
        "frequency_penalty": cfg["frequency_penalty"],
        "presence_penalty": cfg["presence_penalty"],
        "top_k": cfg["top_k"],
    }


def remove_think_tags(text):
    """Remove thinking/reasoning tags. Ported from _remove_think_tags."""
    if '</anth>' in text:
        r = text.split('</anth>', 1)[-1]
    elif '<channel|>' in text:
        r = text.split('<channel|>', 1)[-1]
    elif '<|channel|>thought' in text:
        r = text.split('<|channel|>thought', 1)[-1]
    else:
        r = text
    return r.strip()


def extract_json(text):
    """Extract JSON from LLM output. Ported from _extract_json."""
    fence = "```"
    start_marker = fence + "json"
    start_idx = text.find(start_marker)

    if start_idx == -1:
        start_idx = text.find(fence)
        if start_idx != -1:
            start_idx += len(fence)
    else:
        start_idx += len(start_marker)

    end_idx = text.rfind(fence)

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = text[start_idx:end_idx].strip()
    else:
        first_brace, first_bracket = text.find('{'), text.find('[')
        last_brace, last_bracket = text.rfind('}'), text.rfind(']')
        starts = [i for i in (first_brace, first_bracket) if i != -1]
        ends = [i for i in (last_brace, last_bracket) if i != -1]
        if starts and ends:
            json_str = text[min(starts):max(ends)+1]
        else:
            raise ValueError("No JSON boundaries found.")
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        raise ValueError("Failed to decode JSON.")


def ask_llm(base_url, api_key, model, system_prompt, user_prompt,
            max_tokens=DEFAULT_LLM_PARAMS["max_tokens"],
            temperature=DEFAULT_LLM_PARAMS["temperature"],
            top_p=DEFAULT_LLM_PARAMS["top_p"],
            min_p=DEFAULT_LLM_PARAMS["min_p"],
            repetition_penalty=DEFAULT_LLM_PARAMS["repetition_penalty"],
            frequency_penalty=DEFAULT_LLM_PARAMS["frequency_penalty"],
            presence_penalty=DEFAULT_LLM_PARAMS["presence_penalty"],
            top_k=DEFAULT_LLM_PARAMS["top_k"], is_json=False, verbose=False):
    """Call LLM API with streaming. Ported from _ask_llm in translate_epubs_new.py."""
    client = _create_client(base_url, api_key)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    extra_body = {"min_p": min_p, "repetition_penalty": repetition_penalty}
    if top_k is not None:
        extra_body["top_k"] = top_k

    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            presence_penalty=0.0 if is_json else presence_penalty,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            extra_body=extra_body,
            stream=True,
            stream_options={"include_usage": True}
        )

        content = ""
        first_token_time = None
        usage = None

        for chunk in response:
            # Record first_token_time on first chunk received (match PoC logic)
            if first_token_time is None:
                first_token_time = time.time()
            if hasattr(chunk, 'choices') and chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content is not None:
                    content += delta.content
            # Capture usage from the final chunk (stream_options include_usage)
            if hasattr(chunk, 'usage') and chunk.usage is not None:
                usage = chunk.usage

        end_time = time.time()

        # Log metrics (match PoC _ask_llm logic: separate prefill vs generation TPS)
        if usage is not None and first_token_time is not None:
            prompt_tokens = getattr(usage, 'prompt_tokens', 0)
            completion_tokens = getattr(usage, 'completion_tokens', 0)
            total_tokens = getattr(usage, 'total_tokens', prompt_tokens + completion_tokens)
            prefill_time = first_token_time - start_time
            gen_time = end_time - first_token_time
            prefill_tps = prompt_tokens / prefill_time if prefill_time > 0 else 0
            gen_tps = completion_tokens / gen_time if gen_time > 0 else 0
            print(f"      [~] Tokens: {prompt_tokens} in / {completion_tokens} out / {total_tokens} total | "
                  f"Prefill: {prefill_tps:.1f} t/s | Generation: {gen_tps:.1f} t/s")
        elif usage is not None:
            prompt_tokens = getattr(usage, 'prompt_tokens', 0)
            completion_tokens = getattr(usage, 'completion_tokens', 0)
            total_tokens = getattr(usage, 'total_tokens', prompt_tokens + completion_tokens)
            print(f"      [~] Tokens: {prompt_tokens} in / {completion_tokens} out / {total_tokens} total")
        else:
            print(f"      [~] No usage metrics returned.")

        if verbose:
            print(f"\n      [LLM Response]:\n{content}\n")
        return remove_think_tags(content)

    except Exception as e:
        print(f"      [!] Streaming failed, falling back to standard request... ({e})")
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                presence_penalty=0.0 if is_json else presence_penalty,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                extra_body=extra_body,
            )
            content = response.choices[0].message.content or ""
            if hasattr(response, 'usage') and response.usage:
                usage = response.usage
                prompt_tokens = getattr(usage, 'prompt_tokens', 0)
                completion_tokens = getattr(usage, 'completion_tokens', 0)
                total_tokens = getattr(usage, 'total_tokens', prompt_tokens + completion_tokens)
                print(f"      [~] Tokens: {prompt_tokens} in / {completion_tokens} out / {total_tokens} total")
            if verbose:
                print(f"\n      [LLM Response]:\n{content}\n")
            return remove_think_tags(content)
        except Exception as e2:
            print(f"      [!] API Communication Error (fallback): {e2}")
            return ""


def ask_llm_json(base_url, api_key, model, system_prompt, user_prompt,
                  max_retries=3, max_tokens=DEFAULT_LLM_PARAMS["max_tokens"],
                  temperature=DEFAULT_LLM_PARAMS["temperature"],
                  top_p=DEFAULT_LLM_PARAMS["top_p"], min_p=DEFAULT_LLM_PARAMS["min_p"],
                  repetition_penalty=DEFAULT_LLM_PARAMS["repetition_penalty"],
                  frequency_penalty=DEFAULT_LLM_PARAMS["frequency_penalty"],
                  presence_penalty=DEFAULT_LLM_PARAMS["presence_penalty"],
                  top_k=DEFAULT_LLM_PARAMS["top_k"]):
    """Call LLM and extract JSON. Ported from _ask_llm_json."""
    for attempt in range(max_retries):
        response = ask_llm(
            base_url=base_url, api_key=api_key, model=model,
            system_prompt=system_prompt, user_prompt=user_prompt,
            max_tokens=max_tokens, temperature=temperature,
            top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty,
            frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,
            top_k=top_k,
            is_json=True
        )
        try:
            j = extract_json(response)
            if isinstance(j, dict):
                return j
            else:
                print(f"      [!] JSON Error: not a dict. Retrying ({attempt + 1}/{max_retries})...")
        except ValueError as e:
            print(f"      [!] JSON Error: {e}. Retrying ({attempt + 1}/{max_retries})...")
        if attempt == max_retries - 1:
            print(f"        Still receiving non-JSON output: {response}")
            return {}