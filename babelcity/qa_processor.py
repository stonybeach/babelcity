"""QA correction. Ported from _process_qa_document in translate_epubs_new.py."""

import json

from lxml import etree

from .llm_handler import ask_llm_json
from .text_processor import (
    parse_xml, serialize_xml, build_mini_glossary,
    finalize_text, extract_text_with_ruby, has_japanese
)


def process_qa_document(content, glossary, llm_config):
    """QA a chapter. Ported from _process_qa_document."""
    try:
        tree = parse_xml(content)
    except Exception as e:
        print(f"    [!] Failed to parse document XML: {e}")
        return None, {}

    tags = tree.xpath('//*[local-name()="p" or local-name()="h1" or local-name()="h2" or local-name()="h3" or local-name()="h4"]')
    if not tags:
        return None, {}

    chapter_abbrevs = {}

    # Build pairs of (original, translated) tags
    pairs = []
    for i in range(len(tags) - 1):
        style = tags[i].get('style', '')
        if 'opacity: 0.4' in style or 'opacity:0.4' in style:
            pairs.append({
                'index': i + 1,
                'jp': "".join(tags[i].itertext()).strip(),
                'zh': "".join(tags[i+1].itertext()).strip(),
                'tag_orig': tags[i],
                'tag_zh': tags[i+1],
            })

    if not pairs:
        return None, {}

    chunk_size = llm_config.get("chunk_size", 12)
    use_mini_glossary = llm_config.get("use_mini_glossary", True)
    trad_chinese = llm_config.get("traditional_chinese", True)

    for i in range(0, len(pairs), chunk_size):
        chunk = pairs[i:i+chunk_size]

        jp_texts = [p['jp'] for p in chunk]
        current_glossary = build_mini_glossary(jp_texts, glossary, chapter_abbrevs) if use_mini_glossary else glossary

        system_prompt = (
            "你是一位极度严格的轻小说校对编辑。\n"
            "任务：检查日文原文与中文翻译的一致性。\n"
            "请阅读待校对段落的中文部分（zh），比较日语原文(jp），根据以下规则进行编辑。\n"
            "【规则】：\n"
            "1. 严格检查【术语表】。如果译文没有使用术语表中的规定译名，必须修改。\n"
            "2. 修正明显的主语推断错误、代词错置或性别错误。\n"
            "3. 【重要】如果原文是使用方引号（「」）的话，而译文改为西式引号，必须改回方引号，和原文一样。\n"
            "4. 如果段落 jp 和 zh 没有分别，或者 zh 有很多日文文字，请重新翻译。\n"
            "5. 如果翻译结果中有英语，除了原文里面的英语专有名称以外，请重新翻译，例如把「such」改为「这种」。\n"
            "6. 如果译文文法不对或语句不通顺，请修改成为通顺的语句。\n"
            "7. 如果译文已经通顺且没有违反上述各点，保留原译文风格，【绝对不要】进行修辞性或风格性的过度润色或重写！\n"
            "输出要求：若有错，请严格使用 payload 中的 id 数字作为 key，回传 JSON，例如 {\"1\": \"修正后的中文1\", \"3\": \"修正后的中文3\"}。若完全没错，【必须】回传空对象 {}。\n\n"
            f"【术语表】: {json.dumps(current_glossary, ensure_ascii=False)}\n"
        )

        try:
            import opencc
            cc_back = opencc.OpenCC('t2s.json')
            eval_payload = [
                {"id": str(p['index']), "jp": p['jp'], "zh": cc_back.convert(p['zh'])}
                for p in chunk
            ]
        except Exception:
            eval_payload = [
                {"id": str(p['index']), "jp": p['jp'], "zh": p['zh']}
                for p in chunk
            ]

        user_prompt = (
            f"payload: {json.dumps(eval_payload, ensure_ascii=False)}\n\n"
            "JSON 输出:"
        )

        qa_result = ask_llm_json(
            base_url=llm_config.get("base_url", "http://localhost:8080/v1"),
            api_key=llm_config.get("api_key", "not-needed"),
            model=llm_config.get("model", "default"),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_retries=llm_config.get("retry_attempts", 2),
            max_tokens=llm_config.get("max_tokens", 8192),
            temperature=llm_config.get("temperature", 1.0),
        )

        # Apply corrections
        for p in chunk:
            idx_str = str(p['index'])
            if idx_str in qa_result:
                corrected = qa_result[idx_str]
                finalized = finalize_text(corrected, p['jp'], trad_chinese)
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