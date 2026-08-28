"""QA correction. Ported from _process_qa_document in translate_epubs_new.py."""

import json

from lxml import etree

from .llm_handler import ask_llm_json, normalize_llm_config
from .text_processor import (
    parse_xml, serialize_xml, build_mini_glossary, failed_translation,
    finalize_text, extract_text_with_ruby, has_japanese, failed_translation_generic
)
from .prompts import get_system_prompt, get_user_prompt, get_language_kwargs, PAYLOAD_KEYS
from .job_executors import JobPausedException


def process_qa_document(content, glossary, llm_config, should_stop=None):
    """QA a chapter. Ported from _process_qa_document.

    Args:
        content: XHTML content string.
        glossary: Project glossary dictionary.
        llm_config: LLM configuration dictionary.
        should_stop: Optional callable returning True if the job queue is paused.
            If so, raises JobPausedException after the current chunk.
    """
    try:
        tree = parse_xml(content)
    except Exception as e:
        print(f"    [!] Failed to parse document XML: {e}")
        return None, {}

    tags = tree.xpath('//*[local-name()="p" or local-name()="h1" or local-name()="h2" or local-name()="h3" or local-name()="h4"]')
    if not tags:
        return None, {}

    chapter_abbrevs = {}

    generic = bool(llm_config.get("generic", False))
    src_key, tgt_key = PAYLOAD_KEYS["generic" if generic else "ja_to_zh"]

    # Build pairs of (original, translated) tags
    pairs = []
    for i in range(len(tags) - 1):
        style = tags[i].get('style', '')
        if 'opacity: 0.4' in style or 'opacity:0.4' in style:
            pairs.append({
                'index': i + 1,
                src_key: "".join(tags[i].itertext()).strip(),
                tgt_key: "".join(tags[i+1].itertext()).strip(),
                'tag_orig': tags[i],
                'tag_zh': tags[i+1],
            })

    if not pairs:
        return None, {}

    chunk_size = llm_config.get("chunk_size", 12)
    use_mini_glossary = llm_config.get("use_mini_glossary", True)
    trad_chinese = llm_config.get("traditional_chinese", True)

    for i in range(0, len(pairs), chunk_size):
        if should_stop and should_stop():
            raise JobPausedException("Job queue paused during QA")
        chunk = pairs[i:i+chunk_size]

        src_texts = [p[src_key] for p in chunk]
        current_glossary = build_mini_glossary(src_texts, glossary, chapter_abbrevs) if use_mini_glossary else glossary

        kwargs = {"glossary": json.dumps(current_glossary, ensure_ascii=False)}
        kwargs.update(get_language_kwargs(llm_config))
        system_prompt = get_system_prompt(llm_config, "qa_system", kwargs)

        if generic:
            eval_payload = [
                {"id": str(p['index']), src_key: p[src_key], tgt_key: p[tgt_key]}
                for p in chunk
            ]
        else:
            try:
                import opencc
                cc_back = opencc.OpenCC('t2s')
                eval_payload = [
                    {"id": str(p['index']), src_key: p[src_key], tgt_key: cc_back.convert(p[tgt_key])}
                    for p in chunk
                ]
            except Exception:
                eval_payload = [
                    {"id": str(p['index']), src_key: p[src_key], tgt_key: p[tgt_key]}
                    for p in chunk
                ]

        user_prompt = get_user_prompt(llm_config, "qa_user", {"payload": json.dumps(eval_payload, ensure_ascii=False)})

        cfg = normalize_llm_config(llm_config)
        qa_result = ask_llm_json(
            base_url=cfg.get("base_url", "http://localhost:8080/v1"),
            api_key=cfg.get("api_key", "not-needed"),
            model=cfg.get("model", "default"),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_retries=cfg.get("retry_attempts", 2),
            max_tokens=cfg["max_tokens"],
            temperature=cfg["temperature"],
            top_p=cfg["top_p"],
            min_p=cfg["min_p"],
            repetition_penalty=cfg["repetition_penalty"],
            frequency_penalty=cfg["frequency_penalty"],
            presence_penalty=cfg["presence_penalty"],
            top_k=cfg["top_k"],
        )

        # Apply corrections
        check = failed_translation_generic if generic else failed_translation
        for p in chunk:
            idx_str = str(p['index'])
            if idx_str in qa_result:
                corrected = qa_result[idx_str]
                src_text = p[src_key]
                if not check([src_text], [corrected]):
                    finalized = corrected if generic else finalize_text(corrected, src_text, trad_chinese)
                    p['tag_zh'].text = finalized

    modified_xml = serialize_xml(tree)
    return modified_xml, {}


def run_qa_on_chapters(chapter_items, glossary, qa_config, threads):
    """QA all chapters in parallel."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = []

    def process_single(args):
        item_id, content = args
        modified, heading_map = process_qa_document(content, glossary, qa_config)
        return (item_id, modified, heading_map)

    if threads > 1:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(process_single, (item_id, content)): (item_id, content)
                for item_id, content in chapter_items
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    item_id, _ = futures[future]
                    print(f"Error processing item {item_id}: {e}")
    else:
        for item_id, content in chapter_items:
            result = process_single((item_id, content))
            results.append(result)

    return results