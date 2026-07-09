"""Text processing utilities ported from translate_epubs_new.py PoC code."""

import re
import json

from lxml import etree
from bs4 import BeautifulSoup


def has_japanese(text):
    """Check for Japanese hiragana/katakana characters."""
    return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text))


def extract_text_with_ruby(tag):
    """Convert ruby tags to (ruby) format. Ported from _extract_text_with_ruby."""
    tag_html = etree.tostring(tag, encoding='unicode', method='html')
    tag_copy = BeautifulSoup(tag_html, 'html.parser')

    for ruby in tag_copy.find_all('ruby'):
        rt_text = "".join([rt.get_text() for rt in ruby.find_all('rt')])
        for t in ruby.find_all(['rt', 'rp']):
            t.decompose()
        base_text = ruby.get_text().strip()
        ruby.replace_with(f"{base_text}({rt_text})" if rt_text else base_text)

    return tag_copy.get_text().strip()


def parse_xml(content):
    """Parse XHTML into an XML tree. Ported from _parse_xml."""
    if isinstance(content, str):
        content = content.encode('utf-8')
    parser = etree.XMLParser(recover=True, resolve_entities=False)
    return etree.fromstring(content, parser=parser)


def serialize_xml(tree):
    """Convert XML tree into string. Ported from _serialize_xml."""
    new_tree = tree.getroottree()
    doctype = new_tree.docinfo.doctype
    if doctype:
        return etree.tostring(new_tree, encoding='utf-8', xml_declaration=True, doctype=doctype, method='xml')
    return etree.tostring(new_tree, encoding='utf-8', xml_declaration=True, method='xml')


def load_dictionary(pre_translated_text):
    """Load pre-translated terms. Ported from _load_dictionary.

    Can load from file path or from text string.
    Format: one per line, `Source => Translation # Comment`. Everything after # is dropped.
    """
    user_dict = {}

    print(f"Text = {len(pre_translated_text)}")
    if pre_translated_text:
        for line in pre_translated_text.strip().split('\n'):
            print(line)
            line = line.split('#')[0].strip()
            if '=>' in line:
                parts = line.split('=>', 1)
                jp_name = parts[0].strip()
                zh_name = parts[1].strip()
                if jp_name and zh_name:
                    user_dict[jp_name] = zh_name

    return user_dict


def build_mini_glossary(jp_texts, global_glossary, chapter_abbrevs=None):
    """Create a mini-glossary subset for the current text chunk. Ported from _build_mini_glossary."""
    if isinstance(jp_texts, str):
        combined_text = jp_texts
    else:
        combined_text = "".join(jp_texts)

    active_full_names = set()
    if chapter_abbrevs:
        for abbrev, full_name in chapter_abbrevs.items():
            if abbrev in combined_text:
                active_full_names.add(full_name)

    mini_glossary = {}
    for jp_name, data in global_glossary.items():
        if jp_name in combined_text or jp_name in active_full_names:
            mini_glossary[jp_name] = data

    return mini_glossary


def sync_quotes(trans_text, source_text):
    """Synchronize quotes and brackets from source to translation. Ported from _sync_quotes."""
    #QUOTE_CHARS = set("「」【】""''『』《》〖〗\"'‘’")
    QUOTE_CHARS = set("「」【】“”『』《》〖〗\"'‘’")

    if not source_text or not trans_text:
        return trans_text, False

    src_quotes = [c for c in source_text if c in QUOTE_CHARS]
    trans_quotes_info = [(i, c) for i, c in enumerate(trans_text) if c in QUOTE_CHARS]
    trans_quotes = [c for _, c in trans_quotes_info]

    is_synced = False

    # Rule 4: 2 more quotes in source, source starts/ends with quote, trans does not
    if len(src_quotes) == len(trans_quotes) + 2:
        src_stripped = source_text.strip()
        trans_stripped = trans_text.strip()

        if src_stripped and src_stripped[0] == src_quotes[0] and src_stripped[-1] == src_quotes[-1]:
            has_start_quote = trans_stripped and trans_stripped[0] in QUOTE_CHARS
            has_end_quote = trans_stripped and trans_stripped[-1] in QUOTE_CHARS

            if not (has_start_quote and has_end_quote):
                trans_text = src_quotes[0] + trans_text + src_quotes[-1]
                trans_quotes_info = [(i, c) for i, c in enumerate(trans_text) if c in QUOTE_CHARS]
                trans_quotes = [c for _, c in trans_quotes_info]

    # Rule 4b: 2 more quotes in trans, trans starts/ends with quote, source does not
    elif len(trans_quotes) == len(src_quotes) + 2:
        src_stripped = source_text.strip()
        trans_stripped = trans_text.strip()

        if trans_stripped and trans_stripped[0] == trans_quotes[0] and trans_stripped[-1] == trans_quotes[-1]:
            has_start_quote = src_stripped and src_stripped[0] in QUOTE_CHARS
            has_end_quote = src_stripped and src_stripped[-1] in QUOTE_CHARS

            if not (has_start_quote and has_end_quote):
                first_idx = trans_quotes_info[0][0]
                last_idx = trans_quotes_info[-1][0]
                trans_text = trans_text[:first_idx] + trans_text[first_idx+1:last_idx] + trans_text[last_idx+1:]
                trans_quotes_info = [(i, c) for i, c in enumerate(trans_text) if c in QUOTE_CHARS]
                trans_quotes = [c for _, c in trans_quotes_info]

    # Rule 5: mismatch, leave alone
    if len(src_quotes) != len(trans_quotes):
        return trans_text, False

    # Rules 2 & 3: orderly replacement
    is_synced = True
    if not src_quotes:
        return trans_text, is_synced

    trans_list = list(trans_text)
    for (idx, _), src_char in zip(trans_quotes_info, src_quotes):
        trans_list[idx] = src_char

    return "".join(trans_list), is_synced


def finalize_text(text, source_text=None, to_traditional=True):
    """Finalize translated text with quote sync and OpenCC conversion. Ported from _finalize_text."""
    if not text:
        return text

    is_synced = False
    if source_text:
        text, is_synced = sync_quotes(text, source_text)

    if not is_synced:
        # Fallback for mismatched/absent quotes
        text = text.replace('"', '「').replace('"', '」')
        parts = text.split('"')
        if len(parts) > 1:
            new_text = parts[0]
            for i in range(1, len(parts)):
                if i % 2 != 0:
                    new_text += '「' + parts[i]
                else:
                    new_text += '」' + parts[i]
            text = new_text

    # Chinese conversion
    if to_traditional:
        try:
            import opencc
            cc = opencc.OpenCC('s2hk')
            text = cc.convert(text)
        except Exception:
            pass
    else:
        try:
            import opencc
            cc = cc = opencc.OpenCC('t2s')
            text = cc.convert(text)
        except Exception:
            pass

    return text


def extract_paragraphs(text):
    """Extract paragraph texts from EPUB XML content. Follows translation_processor/qa_processor pattern."""
    try:
        tree = parse_xml(text)
    except Exception:
        return []

    tags = tree.xpath('//*[local-name()="p" or local-name()="h1" or local-name()="h2" or local-name()="h3" or local-name()="h4"]')
    paragraphs = []
    for tag in tags:
        txt = extract_text_with_ruby(tag)
        if txt:
            paragraphs.append(txt)

    return paragraphs


def chunk_paragraphs(paragraphs, chunk_size):
    """Group paragraphs into chunks of given size."""
    return [paragraphs[i:i+chunk_size] for i in range(0, len(paragraphs), chunk_size)]