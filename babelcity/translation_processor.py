"""Chapter and Nav translation. Ported from translate_epubs_new.py."""

import json
import re
from lxml import etree

from .llm_handler import ask_llm, _get_llm_kwargs
from .text_processor import (
    parse_xml, serialize_xml, build_mini_glossary, failed_translation,
    finalize_text, extract_text_with_ruby, has_japanese, has_literal_text,
    has_literal_text_generic, failed_translation_generic
)
from .prompts import (
    system_prompt_header, get_prompts, get_system_prompt, get_user_prompt,
    get_language_kwargs,
)
from .job_executors import JobPausedException


def _select_failure_check(llm_config):
    return failed_translation_generic if llm_config.get("generic") else failed_translation


def translate_single_line(jp_text, current_glossary, chapter_abbrevs, llm_config, history_context=""):
    """Translate one line. Ported from translate_single_line."""
    kwargs = {
        "glossary": json.dumps(current_glossary, ensure_ascii=False),
        "abbrevs": json.dumps(chapter_abbrevs, ensure_ascii=False),
    }
    kwargs.update(get_language_kwargs(llm_config))
    system_prompt = get_system_prompt(llm_config, "translation_single_system", kwargs)

    header = get_prompts(llm_config)["history_block_header"]
    context_block = f"{header}:\n{history_context}\n\n" if history_context else ""

    kwargs.update({"context_block": context_block, "text": jp_text})
    user_prompt = get_user_prompt(llm_config, "translation_single_user", kwargs)

    attempts = llm_config.get("retry_attempts", 2)
    check = _select_failure_check(llm_config)

    for attempt in range(attempts, 0, -1):
        res_strip = ask_llm(system_prompt=system_prompt, user_prompt=user_prompt, **_get_llm_kwargs(llm_config))
        if not check([jp_text], [res_strip]):
            return res_strip
        elif attempt > 1:
            print(f"      [!] Line translation failed. Received '{res_strip}'. Retrying...")
        else:
            print(f"      [!] Line translation still failed. Received '{res_strip}'. Giving up.")
            return res_strip

    return jp_text


def translate_chunk(jp_texts, current_glossary, chapter_abbrevs, llm_config, history_context=""):
    """Translate a chunk of paragraphs. Ported from translate_chunk with exact delimiter/recovery logic."""
    if len(jp_texts) == 1:
        return [translate_single_line(jp_texts[0], current_glossary, chapter_abbrevs, llm_config, history_context)]

    kwargs = {
        "glossary": json.dumps(current_glossary, ensure_ascii=False),
        "abbrevs": json.dumps(chapter_abbrevs, ensure_ascii=False),
    }
    kwargs.update(get_language_kwargs(llm_config))
    system_prompt = get_system_prompt(llm_config, "translation_chunk_system", kwargs)

    header = get_prompts(llm_config)["history_block_header"]
    context_block = f"{header}:\n{history_context}\n\n" if history_context else ""

    attempts = llm_config.get("retry_attempts", 2)
    check = _select_failure_check(llm_config)

    for attempt in range(attempts):
        if attempt % 3 == 0:
            delimiter = "===="
        elif attempt % 3 == 1:
            delimiter = "$$$$"
        else:
            delimiter = "~~~~"

        kwargs.update({"delimiter": delimiter, "count": len(jp_texts),
                       "texts": delimiter.join(jp_texts), "context_block": context_block})
        user_prompt = get_user_prompt(llm_config, "translation_chunk_user", kwargs)

        res = ask_llm(system_prompt=system_prompt, user_prompt=user_prompt, **_get_llm_kwargs(llm_config))

        res_clean = re.sub(r'^```.*?\n|```$', '', res, flags=re.MULTILINE).strip()

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
            if check(jp_texts, out):
                print(f"      [!] Chunk translation failed. Retrying...")
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


def process_document(content, glossary, llm_config, resume=False, should_stop=None):
    """Translate a chapter. Ported from _process_document.

    Args:
        content: XHTML content string.
        glossary: Project glossary dictionary.
        llm_config: LLM configuration dictionary.
        resume: Unused (kept for signature compatibility).
        should_stop: Optional callable returning True if the job queue is paused.
            If so, raises JobPausedException after the current chunk.
    """
    try:
        tree = parse_xml(content)
    except Exception as e:
        print(f"      [!] Failed to parse document XML: {e}")
        return None, {}

    tags = tree.xpath('//*[local-name()="p" or local-name()="h1" or local-name()="h2" or local-name()="h3" or local-name()="h4"]')
    if not tags:
        return None, {}

    chapter_abbrevs = {}  # resolve_contextual_names skipped per requirements

    generic = bool(llm_config.get("generic", False))
    literal_check = has_literal_text_generic if generic else has_literal_text

    valid_tags = []
    for tag in tags:
        txt = extract_text_with_ruby(tag)
        if txt and literal_check(txt):
            valid_tags.append((tag, txt))

    local_heading_map = {}
    chunk_size = llm_config.get("chunk_size", 12)
    use_mini_glossary = llm_config.get("use_mini_glossary", True)
    trad_chinese = llm_config.get("traditional_chinese", True)

    def apply_with_config(chunk, zh_batch, heading_map):
        for (tag, original_txt), zh in zip(chunk, zh_batch):
            current_style = tag.get('style', '')
            tag.set('style', f"{current_style}; opacity: 0.4;".strip('; '))

            new_tag = etree.Element(tag.tag)

            finalized_zh = None
            if zh:
                finalized_zh = zh if generic else finalize_text(zh, original_txt, trad_chinese)
                new_tag.text = finalized_zh if finalized_zh else original_txt
            else:
                new_tag.text = original_txt

            if heading_map is not None:
                tag_name = tag.tag.split('}')[-1].lower()
                if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    clean_orig = original_txt.strip()
                    if clean_orig and (generic or has_japanese(clean_orig)):
                        heading_map[clean_orig] = new_tag.text.strip()

            parent = tag.getparent()
            parent.insert(parent.index(tag) + 1, new_tag)

    previous_translations = []
    chunks = [valid_tags[i:i+chunk_size] for i in range(0, len(valid_tags), chunk_size)]

    for chunk in chunks:
        if should_stop and should_stop():
            raise JobPausedException("Job queue paused during translation")
        jp_texts = [t[1] for t in chunk]

        current_glossary = build_mini_glossary(jp_texts, glossary, chapter_abbrevs) if use_mini_glossary else glossary

        history_context = "\n".join(previous_translations) if previous_translations else ""

        zh_batch = translate_chunk(jp_texts, current_glossary, chapter_abbrevs, llm_config, history_context)

        if zh_batch:
            valid_zh = [zh for zh in zh_batch if zh]
            if valid_zh:
                history_count = llm_config.get("history", 5)
                previous_translations = valid_zh[-history_count:]

        apply_with_config(chunk, zh_batch, local_heading_map)

    modified_xml = serialize_xml(tree)
    return modified_xml, local_heading_map


_TOC_XPATH = '//*[local-name()="a" or local-name()="span" or local-name()="h1" or local-name()="h2" or local-name()="h3" or local-name()="text"]'
_NCX_XPATH = '//*[local-name()="navLabel"]/*[local-name()="text"]'


def _translate_nav_tags(tree, xpath, chunk_size, heading_map, glossary, llm_config):
    """Common TOC/NCX translation logic. Text is replaced in-place."""
    tags = tree.xpath(xpath)
    if not tags:
        return serialize_xml(tree)

    valid_tags = [(tag, "".join(tag.itertext()).strip()) for tag in tags if "".join(tag.itertext()).strip()]

    sorted_headings = sorted(
        [(h, zh) for h, zh in heading_map.items() if len(h.strip()) > 0],
        key=lambda x: len(x[0]),
        reverse=True
    )

    use_mini_glossary = llm_config.get("use_mini_glossary", True)
    generic = bool(llm_config.get("generic", False))

    for i in range(0, len(valid_tags), chunk_size):
        chunk = valid_tags[i:i+chunk_size]

        texts_to_translate = []
        pre_translated = {}

        for idx, (tag, text) in enumerate(chunk):
            zh_text = None
            for jp_h, zh_h in sorted_headings:
                if jp_h in text:
                    replaced = text.replace(jp_h, zh_h)
                    remainder = text.replace(jp_h, "")

                    if generic or not has_japanese(remainder):
                        zh_text = replaced
                        break

            if zh_text is not None:
                pre_translated[idx] = zh_text
                print(f"      [TOC Cache Hit] {text} -> {zh_text}")
            elif not generic and not has_japanese(text):
                pre_translated[idx] = text
            else:
                texts_to_translate.append((idx, text))

        zh_batch = [None] * len(chunk)
        for idx, zh_text in pre_translated.items():
            zh_batch[idx] = zh_text

        if texts_to_translate:
            llm_texts = [t[1] for t in texts_to_translate]
            current_glossary = build_mini_glossary(llm_texts, glossary, {}) if use_mini_glossary else glossary
            llm_translated = translate_chunk(llm_texts, current_glossary, {}, llm_config)
            for (idx, orig_text), zh_text in zip(texts_to_translate, llm_translated):
                if zh_text and not generic:
                    zh_text = finalize_text(zh_text, orig_text, llm_config.get("traditional_chinese", True))
                zh_batch[idx] = zh_text

        for (tag, _), zh in zip(chunk, zh_batch):
            for child in list(tag):
                tag.remove(child)
            if zh:
                tag.text = zh if zh else _
            else:
                tag.text = _

    return serialize_xml(tree)


def translate_toc_content(content, chunk_size, heading_map, glossary, llm_config):
    """Translate HTML5 Nav TOC, reusing pre-translated headers."""
    try:
        tree = parse_xml(content)
    except Exception as e:
        print(f"      [!] Failed to parse TOC XML: {e}")
        return content
    return _translate_nav_tags(tree, _TOC_XPATH, chunk_size, heading_map, glossary, llm_config)


def translate_ncx_content(content, chunk_size, heading_map, glossary, llm_config):
    """Translate EPUB 2.0 NCX TOC. Text is replaced in-place in <text> elements."""
    try:
        tree = parse_xml(content)
    except Exception as e:
        print(f"      [!] Failed to parse NCX XML: {e}")
        return content
    return _translate_nav_tags(tree, _NCX_XPATH, chunk_size, heading_map, glossary, llm_config)


def process_toc(content, chunk_size, heading_map, glossary, llm_config):
    """Translate a Nav file (HTML5 Nav or EPUB 2.0 NCX). Auto-detects format."""
    try:
        tree = parse_xml(content)
        root_name = etree.QName(tree.tag).localname if isinstance(tree.tag, str) else tree.tag
        if root_name == "ncx":
            return translate_ncx_content(content, chunk_size, heading_map, glossary, llm_config)
    except Exception:
        pass
    return translate_toc_content(content, chunk_size, heading_map, glossary, llm_config)