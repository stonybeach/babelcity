"""Glossary scanning via LLM."""

import json

from .llm_handler import ask_llm_json, normalize_llm_config
from .text_processor import has_japanese
from .prompts import get_system_prompt, get_user_prompt, get_language_kwargs


def build_system_prompt(existing_glossary, pre_translated, llm_config=None):
    """Build the system prompt matching the PoC scan_for_entities logic."""
    generic = bool((llm_config or {}).get("generic", False))
    if generic:
        dict_context = f"Reference translation table: {json.dumps(pre_translated, ensure_ascii=False)}\n" if pre_translated else ""
        existing_context = f"Existing entity table: {json.dumps(existing_glossary, ensure_ascii=False)}\n" if existing_glossary else ""
    else:
        dict_context = f"参考译名表: {json.dumps(pre_translated, ensure_ascii=False)}\n" if pre_translated else ""
        existing_context = f"现有实体表: {json.dumps(existing_glossary, ensure_ascii=False)}\n" if existing_glossary else ""

    kwargs = {"dict_context": dict_context, "existing_context": existing_context}
    kwargs.update(get_language_kwargs(llm_config))
    return get_system_prompt(llm_config, "glossary_system", kwargs)


def build_user_prompt(text_chunk, llm_config=None):
    """Build the user prompt matching the PoC."""
    kwargs = {"text_chunk": text_chunk}
    kwargs.update(get_language_kwargs(llm_config))
    return get_user_prompt(llm_config, "glossary_user", kwargs)


def scan_for_entities(text_chunk, llm_config, existing_glossary=None, pre_translated=None):
    """Extract glossary terms from a text chunk using LLM.

    Matches PoC scan_for_entities: retries on JSON failures, applies inline
    filtering (has_japanese, len > 30), and applies pre_translated overrides
    per-term before returning.
    """
    system_prompt = build_system_prompt(existing_glossary or {}, pre_translated or {}, llm_config)
    user_prompt = build_user_prompt(text_chunk, llm_config)

    cfg = normalize_llm_config(llm_config)
    terms = ask_llm_json(
        base_url=cfg.get("base_url", "http://localhost:8080/v1"),
        api_key=cfg.get("api_key", "not-needed"),
        model=cfg.get("model", "default"),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=cfg["max_tokens"],
        temperature=cfg["temperature"],
        top_p=cfg["top_p"],
        min_p=cfg["min_p"],
        repetition_penalty=cfg["repetition_penalty"],
        frequency_penalty=cfg["frequency_penalty"],
        presence_penalty=cfg["presence_penalty"],
        top_k=cfg["top_k"],
        max_retries=cfg.get("retry_attempts", 3),
    )

    # Inline filtering matching PoC scan_for_entities (lines 468-482)
    pre_translated = pre_translated or {}
    generic = bool(llm_config.get("generic", False)) if llm_config else False
    filtered = {}
    for name, data in terms.items():
        if not isinstance(data, dict):
            continue
        if not generic and not has_japanese(name):
            continue
        if len(name) > 30:
            continue
        # Apply pre_translated override (PoC line 478-479)
        if name in pre_translated:
            data['translated_name'] = pre_translated[name]
        filtered[name] = data

    return filtered


def merge_glossary(existing, new_terms):
    """Merge scanned terms into existing glossary.

    Matching PoC: scan_for_entities already applies pre_translated overrides
    and filtering inline. merge_glossary only handles merging new terms.
    """
    merged = dict(existing)

    for term, info in new_terms.items():
        # PoC overwrites entire entry: self.global_glossary[name] = data
        merged[term] = info

    return merged