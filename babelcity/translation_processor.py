"""Chapter and Nav translation. Ported from translate_epubs_new.py."""

import json
import re
from lxml import etree

from .llm_handler import ask_llm, ask_llm_json, remove_think_tags
from .text_processor import (
    parse_xml, serialize_xml, build_mini_glossary,
    finalize_text, extract_text_with_ruby, has_japanese
)


def system_prompt_header(is_single):
    """Build system prompt header. Ported from system_prompt_header."""
    prompt_list = [
        "如有提供用作参考的上下文，请先阅读及理解，在翻译时保持逻辑正确。",
        "翻译时必须保持情节合理，小心错字。",
        "遇到术语表里有的名字，必须使用对应的中文翻译，严格遵守术语表的性别选择适当的称谓。",
        "逐一把每段日文翻译成通顺、有趣的中文，保留句子原来的语气和气氛。",
    ]
    if is_single:
        prompt_list.append("【极度重要】直接输出纯中文翻译，绝对不要包含任何解释或 Markdown 标签。")
    else:
        prompt_list.append("【极度重要】直接输出纯中文翻译，使用指定的分隔符，输出纯文本。不允许使用 JSON！")
        prompt_list.append("返回的翻译段落数量在使用分隔符隔开后，必须与原文段落数量完全一致，绝对不要包含任何解释或 Markdown 标签。")
    prompt_header = "\n".join([f"{i}. {item}" for i, item in enumerate(prompt_list, start=1)])
    return prompt_header


def translate_single_line(jp_text, current_glossary, chapter_abbrevs, llm_config, history_context=""):
    """Translate one line. Ported from translate_single_line."""
    system_prompt = (
        "你是一位顶尖的轻小说翻译专家，能严格遵守以下要求将提供的日文翻译为轻小说风格的中文。\n"
        "要求：\n"
        f"{system_prompt_header(True)}\n\n"
        f"【术语表】: {json.dumps(current_glossary, ensure_ascii=False)}\n"
        f"【本章简称映射表】: {json.dumps(chapter_abbrevs, ensure_ascii=False)}\n"
        "请勿输出未经翻译的日文原文。\n"
    )

    context_block = f"历史翻译上下文 (仅供参考, 请勿重新翻译):\n{history_context}\n\n" if history_context else ""

    user_prompt = (
        f"{context_block}"
        f"待翻译日文原文: {jp_text}\n\n"
        "翻译结果:"
    )
    res = ask_llm(
        base_url=llm_config.get("base_url", "http://localhost:8080/v1"),
        api_key=llm_config.get("api_key", "not-needed"),
        model=llm_config.get("model", "default"),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=llm_config.get("max_tokens", 8192),
        temperature=llm_config.get("temperature", 1.0),
    )
    return res.strip()


def translate_chunk(jp_texts, current_glossary, chapter_abbrevs, llm_config, history_context=""):
    """Translate a chunk of paragraphs. Ported from translate_chunk with exact delimiter/recovery logic."""
    if len(jp_texts) == 1:
        return [translate_single_line(jp_texts[0], current_glossary, chapter_abbrevs, llm_config, history_context)]

    system_prompt = (
        "你是一位顶尖的轻小说翻译专家，能严格遵守以下要求将提供的多个日文标题或段落逐一翻译为轻小说风格的中文。\n"
        "要求：\n"
        f"{system_prompt_header(False)}\n\n"
        f"【术语表】: {json.dumps(current_glossary, ensure_ascii=False)}\n"
        f"【本章简称映射表】: {json.dumps(chapter_abbrevs, ensure_ascii=False)}\n"
        "请勿输出未经翻译的日文原文。\n"
    )

    context_block = f"历史翻译上下文 (仅供参考, 请勿重新翻译):\n{history_context}\n\n" if history_context else ""

    attempts = llm_config.get("retry_attempts", 2)

    for attempt in range(attempts):
        if attempt % 3 == 0:
            delimiter = "===="
        elif attempt % 3 == 1:
            delimiter = "$$$$"
        else:
            delimiter = "~~~~"

        user_prompt = (
            "请根据以下要求执行翻译任务，输出流畅的中文。\n"
            f"【分隔符规则】：为了区分不同的段落，你必须在每个翻译段落之间单独使用 `{delimiter}` 作为换行分隔符。\n"
            f"格式范例：\n第一段翻译\n{delimiter}\n第二段翻译\n\n"
            f"{context_block}"
            f"待翻译日文段落 (共 {len(jp_texts)} 段):\n{delimiter.join(jp_texts)}\n\n"
            f"中文翻译结果 (使用 {delimiter} 分隔):"
        )

        res = ask_llm(
            base_url=llm_config.get("base_url", "http://localhost:8080/v1"),
            api_key=llm_config.get("api_key", "not-needed"),
            model=llm_config.get("model", "default"),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=llm_config.get("max_tokens", 8192),
            temperature=llm_config.get("temperature", 1.0),
        )

        res_clean = re.sub(r'^```.*?\n|```$', '', res.strip(), flags=re.MULTILINE).strip()

        escaped_delimiter = re.escape(delimiter)
        out = [t.strip() for t in re.split(rf'\n*\s*{escaped_delimiter}\s*\n*', res_clean)]

        if out and not out[-1]:
            out.pop()

        if len(out) != len(jp_texts):
            # Recovery: try splitting by newlines
            out = [t.strip() for t in re.split(rf'\n*\s*{escaped_delimiter}\s*\n*|\n+', res_clean)]
            if out and not out[-1]:
                out.pop()

        if len(out) == len(jp_texts):
            # Check for failed translation (identical unchanged lines)
            failed_translation = False
            for orig_line, trans_line in zip(jp_texts, out):
                if orig_line.strip() in trans_line.strip() and has_japanese(trans_line):
                    failed_translation = True
                    break

            if failed_translation:
                print(f"      [!] Chunk translation failed: Detected identical unchanged line. Retrying...")
                continue

            return out
        else:
            print(f"      [!] Wrong length: expected {len(jp_texts)}, got {len(out)}. Retrying with new delimiter...")

    # Fallback: line-by-line translation
    print(f"      [!] Chunk translation failed {attempts} times. Falling back to line-by-line.")

    fallback_translations = []
    dynamic_history = history_context.split('\n') if history_context else []
    history_count = llm_config.get("history", 5)

    for i, text in enumerate(jp_texts):
        print(f"      - Line-by-line fallback ({i+1}/{len(jp_texts)})...")
        current_history_str = "\n".join(dynamic_history[-history_count:])
        zh_text = translate_single_line(text, current_glossary, chapter_abbrevs, llm_config, current_history_str)
        fallback_translations.append(zh_text)
        if zh_text:
            dynamic_history.append(zh_text)

    return fallback_translations


def apply_translations_to_chunk(chunk, zh_batch, local_heading_map=None):
    """Inject translated text below original; dim original. Ported from _apply_translations_to_chunk."""
    for (tag, original_txt), zh in zip(chunk, zh_batch):
        current_style = tag.get('style', '')
        tag.set('style', f"{current_style}; opacity: 0.4;".strip('; '))

        new_tag = etree.Element(tag.tag)

        finalized_zh = None
        if zh:
            finalized_zh = finalize_text(zh, original_txt, True)
            new_tag.text = finalized_zh if finalized_zh else original_txt
        else:
            new_tag.text = original_txt

        if local_heading_map is not None:
            tag_name = tag.tag.split('}')[-1].lower()
            if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                clean_orig = original_txt.strip()
                if clean_orig and has_japanese(clean_orig):
                    local_heading_map[clean_orig] = new_tag.text.strip()

        parent = tag.getparent()
        parent.insert(parent.index(tag) + 1, new_tag)


def process_document(content, glossary, llm_config, resume=False):
    """Translate a chapter. Ported from _process_document."""
    try:
        tree = parse_xml(content)
    except Exception as e:
        print(f"      [!] Failed to parse document XML: {e}")
        return None, {}

    tags = tree.xpath('//*[local-name()="p" or local-name()="h1" or local-name()="h2" or local-name()="h3" or local-name()="h4"]')
    if not tags:
        return None, {}

    chapter_abbrevs = {}  # resolve_contextual_names skipped per requirements

    valid_tags = []
    for tag in tags:
        txt = extract_text_with_ruby(tag)
        if txt:
            valid_tags.append((tag, txt))

    local_heading_map = {}
    chunk_size = llm_config.get("chunk_size", 12)
    use_mini_glossary = llm_config.get("use_mini_glossary", True)
    sync_quotes_enabled = llm_config.get("synchronize_quotes", True)
    trad_chinese = llm_config.get("traditional_chinese", True)

    # Override finalize_text behavior via config
    previous_translations = []
    chunks = [valid_tags[i:i+chunk_size] for i in range(0, len(valid_tags), chunk_size)]

    for chunk in chunks:
        jp_texts = [t[1] for t in chunk]

        current_glossary = build_mini_glossary(jp_texts, glossary, chapter_abbrevs) if use_mini_glossary else glossary

        history_context = "\n".join(previous_translations) if previous_translations else ""

        zh_batch = translate_chunk(jp_texts, current_glossary, chapter_abbrevs, llm_config, history_context)

        if zh_batch:
            valid_zh = [zh for zh in zh_batch if zh]
            if valid_zh:
                history_count = llm_config.get("history", 5)
                previous_translations = valid_zh[-history_count:]

        apply_translations_to_chunk(chunk, zh_batch, local_heading_map)

    modified_xml = serialize_xml(tree)
    return modified_xml, local_heading_map


def translate_toc_content(content, chunk_size, heading_map, glossary, llm_config):
    """Translate TOC, reusing pre-translated headers. Ported from _translate_toc_content."""
    try:
        tree = parse_xml(content)
    except Exception as e:
        print(f"      [!] Failed to parse TOC XML: {e}")
        return content

    tags = tree.xpath('//*[local-name()="a" or local-name()="span" or local-name()="h1" or local-name()="h2" or local-name()="h3" or local-name()="text"]')
    if not tags:
        return content

    valid_tags = [(tag, "".join(tag.itertext()).strip()) for tag in tags if "".join(tag.itertext()).strip()]

    # Sort headings by length descending for longest-match-first
    sorted_headings = sorted(
        [(h, zh) for h, zh in heading_map.items() if len(h.strip()) > 0],
        key=lambda x: len(x[0]),
        reverse=True
    )

    for i in range(0, len(valid_tags), chunk_size):
        chunk = valid_tags[i:i+chunk_size]

        texts_to_translate = []
        pre_translated = {}

        for idx, (tag, text) in enumerate(chunk):
            zh_text = None

            # Check against cached headings
            for jp_h, zh_h in sorted_headings:
                if jp_h in text:
                    replaced = text.replace(jp_h, zh_h)
                    remainder = text.replace(jp_h, "")

                    if not has_japanese(remainder):
                        zh_text = replaced
                        break

            if zh_text is not None:
                pre_translated[idx] = zh_text
                print(f"      [TOC Cache Hit] {text} -> {zh_text}")
            elif not has_japanese(text):
                pre_translated[idx] = text
            else:
                texts_to_translate.append((idx, text))

        zh_batch = [None] * len(chunk)
        for idx, zh_text in pre_translated.items():
            zh_batch[idx] = zh_text

        if texts_to_translate:
            use_mini = llm_config.get("use_mini_glossary", True)
            current_glossary = glossary if not use_mini else glossary
            llm_texts = [t[1] for t in texts_to_translate]
            llm_translated = translate_chunk(llm_texts, current_glossary, {}, llm_config)
            for (idx, _), zh_text in zip(texts_to_translate, llm_translated):
                zh_batch[idx] = zh_text

        for (tag, _), zh in zip(chunk, zh_batch):
            for child in list(tag):
                tag.remove(child)
            if zh:
                finalized_zh = finalize_text(zh, _, llm_config.get("traditional_chinese", True))
                tag.text = finalized_zh if finalized_zh else _
            else:
                tag.text = _

    return serialize_xml(tree)


def process_toc(content, chunk_size, heading_map, glossary, llm_config):
    """Translate a Nav file. Ported from _process_toc."""
    return translate_toc_content(content, chunk_size, heading_map, glossary, llm_config)