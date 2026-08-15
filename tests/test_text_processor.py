"""Unit tests for text_processor.py"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from babelcity.text_processor import (
    has_japanese,
    has_literal_text,
    extract_text_with_ruby,
    parse_xml,
    serialize_xml,
    load_dictionary,
    build_mini_glossary,
    sync_quotes,
    finalize_text,
    chunk_paragraphs,
    failed_translation,
)
from lxml import etree


class TestHasJapanese(unittest.TestCase):
    def test_hiragana(self):
        self.assertTrue(has_japanese("こんにちは"))

    def test_katakana(self):
        self.assertTrue(has_japanese("カタカナ"))

    def test_mixed(self):
        self.assertTrue(has_japanese("にほんごEnglish"))

    def test_no_japanese(self):
        self.assertFalse(has_japanese("English only"))

    def test_chinese_only(self):
        self.assertFalse(has_japanese("中文只有"))

    def test_empty(self):
        self.assertFalse(has_japanese(""))

    def test_middle_dot_only(self):
        self.assertFalse(has_japanese("・"))

    def test_latin_with_middle_dot(self):
        self.assertFalse(has_japanese("A・B"))

    def test_long_vowel_mark(self):
        self.assertTrue(has_japanese("コーヒー"))

    def test_kana_with_middle_dot(self):
        self.assertTrue(has_japanese("ア・ア"))


class TestHasLiteralText(unittest.TestCase):
    def test_symbols_only(self):
        self.assertFalse(has_literal_text("◆◇◆"))

    def test_hiragana(self):
        self.assertTrue(has_literal_text("こんにちは"))

    def test_katakana(self):
        self.assertTrue(has_literal_text("カタカナ"))

    def test_kanji(self):
        self.assertTrue(has_literal_text("漢字"))

    def test_chinese(self):
        self.assertTrue(has_literal_text("中文"))

    def test_latin(self):
        self.assertTrue(has_literal_text("Hello world"))

    def test_emojis_only(self):
        self.assertFalse(has_literal_text("😀🎉"))

    def test_empty(self):
        self.assertFalse(has_literal_text(""))

    def test_mixed_hiragana_kanji_symbols(self):
        self.assertTrue(has_literal_text("──はい、完成！"))

    def test_mixed_hiragana_latin(self):
        self.assertTrue(has_literal_text("にほんごEnglish"))

    def test_mixed_symbols_and_latin(self):
        self.assertTrue(has_literal_text("◆◇◆Hello"))

    def test_mixed_symbols_and_kanji(self):
        self.assertTrue(has_literal_text("〜〜日本語"))

    def test_mixed_symbols_emojis_and_chinese(self):
        self.assertTrue(has_literal_text("😀🎉中文"))

    def test_mixed_symbols_and_emojis_only(self):
        self.assertFalse(has_literal_text("◆◇◆😀🎉"))


class TestExtractTextWithRuby(unittest.TestCase):
    def test_ruby_conversion(self):
        xml = "<p><ruby><rb>日本</rb><rt>にほん</rt></ruby></p>"
        tree = etree.fromstring(xml.encode('utf-8'))
        result = extract_text_with_ruby(tree)
        self.assertEqual(result, "日本(にほん)")

    def test_no_ruby(self):
        xml = "<p>plain text</p>"
        tree = etree.fromstring(xml.encode('utf-8'))
        result = extract_text_with_ruby(tree)
        self.assertEqual(result, "plain text")

    def test_multiple_ruby(self):
        xml = "<p><ruby><rb>東京</rb><rt>とうきょう</rt></ruby>と<ruby><rb>大阪</rb><rt>おおさか</rt></ruby></p>"
        tree = etree.fromstring(xml.encode('utf-8'))
        result = extract_text_with_ruby(tree)
        self.assertIn("東京(とうきょう)", result)
        self.assertIn("大阪(おおさか)", result)


class TestParseXml(unittest.TestCase):
    def test_parse_string(self):
        xml_str = '<?xml version="1.0"?><root><child>text</child></root>'
        tree = parse_xml(xml_str)
        self.assertIsNotNone(tree)
        self.assertEqual(tree.tag, 'root')

    def test_parse_bytes(self):
        xml_bytes = b'<?xml version="1.0"?><root><child>text</child></root>'
        tree = parse_xml(xml_bytes)
        self.assertIsNotNone(tree)

    def test_parse_xhtml(self):
        xml_str = '<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><body><p>test</p></body></html>'
        tree = parse_xml(xml_str)
        self.assertIsNotNone(tree)


class TestSerializeXml(unittest.TestCase):
    def test_serialize(self):
        xml_str = '<?xml version="1.0"?><root><child>text</child></root>'
        tree = parse_xml(xml_str)
        result = serialize_xml(tree)
        self.assertIn(b'root', result)
        self.assertIn(b'child', result)


class TestLoadDictionary(unittest.TestCase):
    def test_from_text(self):
        text = """ネル => 涅露
アミナ => 阿米娜 #女
クラス => 阶级 #組織"""
        result = load_dictionary(pre_translated_text=text)
        self.assertEqual(result["ネル"], "涅露")
        self.assertEqual(result["アミナ"], "阿米娜")
        self.assertEqual(result["クラス"], "阶级")

    def test_empty_lines(self):
        text = "ネル => 涅露\n\n\nクラス => 阶级"
        result = load_dictionary(pre_translated_text=text)
        self.assertEqual(len(result), 2)

    def test_no_hash_suffix(self):
        """Everything after # should be dropped."""
        text = "ネル => 涅露 #some comment"
        result = load_dictionary(pre_translated_text=text)
        self.assertEqual(result["ネル"], "涅露")

    def test_empty_input(self):
        result = load_dictionary(pre_translated_text="")
        self.assertEqual(result, {})

    def test_none_input(self):
        result = load_dictionary()
        self.assertEqual(result, {})


class TestBuildMiniGlossary(unittest.TestCase):
    def test_filter_by_text(self):
        glossary = {
            "ネル": {"translation": "涅露", "type": "人名", "gender": "女"},
            "クラス": {"translation": "阶级", "type": "其他", "gender": "未知"},
            "テスト": {"translation": "测试", "type": "其他", "gender": "未知"},
        }
        texts = ["ネルは来た", "クラスに入った"]
        mini = build_mini_glossary(texts, glossary)
        self.assertIn("ネル", mini)
        self.assertIn("クラス", mini)
        self.assertNotIn("テスト", mini)

    def test_no_matches(self):
        glossary = {"ネル": {"translation": "涅露"}}
        texts = ["完全別のテキスト"]
        mini = build_mini_glossary(texts, glossary)
        self.assertEqual(mini, {})

    def test_string_input(self):
        glossary = {"ネル": {"translation": "涅露"}}
        mini = build_mini_glossary("ネルテスト", glossary)
        self.assertIn("ネル", mini)


class TestSyncQuotes(unittest.TestCase):
    def test_basic_sync(self):
        source = "「こんにちは」"
        trans = '"hello"'
        result, synced = sync_quotes(trans, source)
        self.assertTrue(synced)
        self.assertEqual(result, "「hello」")

    def test_no_quotes(self):
        source = "plain text"
        trans = "plain translation"
        result, synced = sync_quotes(trans, source)
        self.assertTrue(synced)
        self.assertEqual(result, "plain translation")

    def test_mismatch_count(self):
        source = "「text"
        trans = '"text"'
        result, synced = sync_quotes(trans, source)
        self.assertFalse(synced)

    def test_empty(self):
        result, synced = sync_quotes("", "")
        self.assertFalse(synced)


class TestFinalizeText(unittest.TestCase):
    def test_finalize_with_source(self):
        source = "「こんにちは」"
        trans = '"hello"'
        result = finalize_text(trans, source, to_traditional=False)
        self.assertIn("「", result)

    def test_finalize_no_source(self):
        result = finalize_text("hello", to_traditional=False)
        self.assertEqual(result, "hello")

    def test_empty(self):
        result = finalize_text("", to_traditional=False)
        self.assertEqual(result, "")

    def test_fallback_curly_quotes(self):
        result = finalize_text("“hello”", to_traditional=False)
        self.assertEqual(result, "「hello」")

    def test_fallback_straight_quotes(self):
        result = finalize_text('"hello"', to_traditional=False)
        self.assertEqual(result, "「hello」")


class TestFailedTranslation(unittest.TestCase):
    def test_empty_line(self):
        self.assertTrue(failed_translation(["こんにちは"], [""]))

    def test_unchanged_japanese(self):
        self.assertTrue(failed_translation(["こんにちは"], ["こんにちは"]))

    def test_too_long(self):
        orig = "こ" * 12
        trans = "あ" * 37
        self.assertTrue(failed_translation([orig], [trans]))

    def test_too_short(self):
        orig = "こ" * 21
        self.assertTrue(failed_translation([orig], ["短"]))

    def test_valid_translation(self):
        self.assertFalse(failed_translation(["こんにちは"], ["你好"]))

    def test_empty_inputs(self):
        self.assertFalse(failed_translation([], []))


class TestChunkParagraphs(unittest.TestCase):
    def test_basic_chunking(self):
        paragraphs = ["p1", "p2", "p3", "p4", "p5"]
        chunks = chunk_paragraphs(paragraphs, 2)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0], ["p1", "p2"])
        self.assertEqual(chunks[1], ["p3", "p4"])
        self.assertEqual(chunks[2], ["p5"])

    def test_chunk_size_larger(self):
        paragraphs = ["p1", "p2"]
        chunks = chunk_paragraphs(paragraphs, 10)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], ["p1", "p2"])

    def test_empty(self):
        chunks = chunk_paragraphs([], 5)
        self.assertEqual(chunks, [])


if __name__ == '__main__':
    unittest.main()