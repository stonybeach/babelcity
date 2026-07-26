"""Glossary scanning via LLM."""

import json

from .llm_handler import ask_llm_json, normalize_llm_config
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

    Matches PoC scan_for_entities: retries on JSON failures, applies inline
    filtering (has_japanese, len > 30), and applies pre_translated overrides
    per-term before returning.
    """
    system_prompt = build_system_prompt(existing_glossary or {}, pre_translated or {})
    user_prompt = build_user_prompt(text_chunk)

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
    filtered = {}
    for name, data in terms.items():
        if not isinstance(data, dict):
            continue
        if not has_japanese(name):
            continue
        if len(name) > 30:
            continue
        # Apply pre_translated override (PoC line 478-479)
        if name in pre_translated:
            data['translated_name'] = pre_translated[name]
        filtered[name] = data

    return filtered

    # Inline filtering matching PoC scan_for_entities (lines 468-482)
    pre_translated = pre_translated or {}
    filtered = {}
    for name, data in terms.items():
        if not isinstance(data, dict):
            continue
        if not has_japanese(name):
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