"""Glossary scanning via LLM."""

import json

from .llm_handler import ask_llm, extract_json
from .text_processor import has_japanese


def build_system_prompt(existing_glossary, pre_translated):
    """Build the system prompt matching the PoC scan_for_entities logic."""
    dict_context = f"参考译名表: {json.dumps(pre_translated, ensure_ascii=False)}\n" if pre_translated else ""
    existing_context = f"现有实体表: {json.dumps(existing_glossary, ensure_ascii=False)}\n" if existing_glossary else ""

    return (
        "你是一个轻小说专家和设定集管理员。\n"
        "任务：从日文轻小说的段落中提取人名及地名，翻译成中文，制作成翻译用的术语表。\n"
        "步骤：\n"
        "1. 从提供的日文段落中提取所有非汉字的人名、姓氏及地名，作为日文原名（复合词和汉字名称不要提取）。\n"
        "2. 日文人物原名必须除去称谓（如「様」、「さん」、「ちゃん」等）。\n"
        "3. 如果中文译名和日文原文相同，请不要提取。\n"
        "4. 查阅「现有实体表」：如果该实体已存在且属性完整（如性别不是未知），请跳过不提取。如果该实体是全新的，或者只存在于「参考译名表」中，则必须提取。\n"
        "5. 如果是一般日语词典里面会有的词语，请不要提取。\n"
        "6. 过滤不需要的词语后，如果在「参考译名表」里面已经有，请使用该译名，没有则请根据性别翻译一个优雅的中文译名，所有输出必须为中文。\n"
        "7. 通过语境（如自称、他称、描述）推断性别和头衔/称谓。如果没有信息可以推断，或者不是人物，「性别」请填上「未知」。\n"
        "8. 严格遵守 Output Format Sample 输出合法的 JSON 格式，以日文原名为 key，value 必须为 Object，包含指定的字段。不要输出任何解释性文字和 Output Format Sample 没有定义的 JSON 格式以外的内容。\n"
        "9. 如果没有找到新实体，请返回空 JSON {}。\n\n"
        f"【{dict_context}】\n"
        f"【{existing_context}】\n"
    )


def build_user_prompt(text_chunk):
    """Build the user prompt matching the PoC."""
    return (
        f"日文文本片段:\n{text_chunk}\n\n"
        "Output Format Sample: {\"日文原名\": {\"translated_name\": \"中文名\", \"type\": \"人名/地名\", \"gender\": \"男/女/未知\"}}\n"
    )


def scan_for_entities(text_chunk, llm_config, existing_glossary=None, pre_translated=None):
    """Extract glossary terms from a text chunk using LLM.

    Matches PoC scan_for_entities logic from translate_epubs_new.py.

    Args:
        text_chunk: Text to scan
        llm_config: Dict with LLM config (base_url, api_key, model, etc.)
        existing_glossary: Current glossary to include in prompt context
        pre_translated: Optional dict of pre-translated terms

    Returns:
        Dict of extracted terms
    """
    system_prompt = build_system_prompt(existing_glossary or {}, pre_translated or {})
    user_prompt = build_user_prompt(text_chunk)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = ask_llm(
        base_url=llm_config.get("base_url", "http://localhost:8080/v1"),
        api_key=llm_config.get("api_key", "not-needed"),
        model=llm_config.get("model", "default"),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=llm_config.get("max_tokens", 8192),
        temperature=llm_config.get("temperature"),
        top_p=llm_config.get("top_p"),
    )

    result = extract_json(response)
    if result and isinstance(result, dict):
        return result
    return {}


def filter_glossary_terms(terms, source_language="ja"):
    """Filter glossary terms matching PoC inline logic.

    Discard terms >30 chars, non-Japanese terms (when source=ja),
    or terms where translated_name equals the original name.
    """
    filtered = {}
    for term, info in terms.items():
        # Skip terms longer than 30 characters
        if len(term) > 30:
            continue
        # For Japanese source, skip terms without hiragana/katakana
        if source_language == "ja" and not has_japanese(term):
            continue
        # Skip if translated_name is the same as the original (PoC smart filter)
        if isinstance(info, dict):
            translated = info.get("translated_name", "")
            if translated == term:
                continue
        filtered[term] = info
    return filtered


def merge_glossary(existing, new_terms, pre_translated=None):
    """Merge scanned terms into existing glossary.

    Apply pre-translated overrides. Uses 'translated_name' field matching PoC.
    """
    merged = dict(existing)

    for term, info in new_terms.items():
        if term in merged:
            # Update existing term
            if isinstance(info, dict):
                merged[term].update(info)
        else:
            merged[term] = info

    # Apply pre-translated overrides (PoC: predefined_dict overrides translated_name)
    if pre_translated:
        for term, translation in pre_translated.items():
            if term in merged:
                if isinstance(merged[term], dict):
                    merged[term]["translated_name"] = translation
                else:
                    merged[term] = {"translated_name": translation, "type": "未知", "gender": "未知"}
            else:
                merged[term] = {"translated_name": translation, "type": "未知", "gender": "未知"}

    return merged