"""LLM API communication. Ported from _ask_llm, _ask_llm_json, _extract_json, _remove_think_tags in translate_epubs_new.py."""

import json
import re
import time

from openai import OpenAI


def _create_client(base_url, api_key):
    return OpenAI(base_url=base_url, api_key=api_key)


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
            max_tokens=8192, temperature=1.0, top_p=0.92,
            min_p=0.05, repetition_penalty=1.04, frequency_penalty=0.05,
            presence_penalty=0.0, is_json=False, verbose=False):
    """Call LLM API. Ported from _ask_llm."""
    client = _create_client(base_url, api_key)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    extra_body = {"min_p": min_p, "repetition_penalty": repetition_penalty}

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
        if verbose:
            print(f"\n      [LLM Response]:\n{content}\n")
        return remove_think_tags(content)
    except Exception as e:
        print(f"      [!] API Communication Error: {e}")
        return ""


def ask_llm_json(base_url, api_key, model, system_prompt, user_prompt,
                 max_retries=3, max_tokens=8192, temperature=1.0,
                 top_p=0.92, min_p=0.05, repetition_penalty=1.04,
                 frequency_penalty=0.05, presence_penalty=0.0):
    """Call LLM and extract JSON. Ported from _ask_llm_json."""
    for attempt in range(max_retries):
        response = ask_llm(
            base_url=base_url, api_key=api_key, model=model,
            system_prompt=system_prompt, user_prompt=user_prompt,
            max_tokens=max_tokens, temperature=temperature,
            top_p=top_p, min_p=min_p, repetition_penalty=repetition_penalty,
            frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,
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