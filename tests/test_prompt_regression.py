"""Regression tests proving centralized ja->zh prompts render byte-identically."""

import os
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

from babelcity import glossary_processor, prompts, qa_processor, translation_processor


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_head_module(name, repo_path):
    try:
        source = subprocess.check_output(
            ["git", "show", f"HEAD:{repo_path}"],
            cwd=REPO_ROOT,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise unittest.SkipTest("git baseline unavailable")

    module_name = f"babelcity._baseline_{name}"
    module = types.ModuleType(module_name)
    module.__package__ = "babelcity"
    sys.modules[module_name] = module
    exec(compile(source, repo_path, "exec"), module.__dict__)
    return module


class JaToZhPromptRegressionTest(unittest.TestCase):
    def tearDown(self):
        for name in list(sys.modules):
            if name.startswith("babelcity._baseline_"):
                del sys.modules[name]

    def _capture_current_translation_prompts(self, cfg, texts):
        calls = []

        def fake_ask_llm(system_prompt=None, user_prompt=None, **kwargs):
            calls.append((system_prompt, user_prompt))
            if len(texts) == 1:
                return "訳一"
            return "訳一====訳二"

        with patch.object(translation_processor, "ask_llm", side_effect=fake_ask_llm):
            for text in texts:
                if len(texts) == 1:
                    translation_processor.translate_single_line(
                        text, {"用語": "訳語"}, {"简称": "訳"}, cfg, "prev"
                    )
                else:
                    translation_processor.translate_chunk(
                        texts, {"用語": "訳語"}, {"简称": "訳"}, cfg, "prev"
                    )

        return calls[0]

    def _capture_baseline_translation_prompts(self, cfg, texts):
        mod = load_head_module("translation_processor", "babelcity/translation_processor.py")
        calls = []

        def fake_ask_llm(system_prompt=None, user_prompt=None, **kwargs):
            calls.append((system_prompt, user_prompt))
            if len(texts) == 1:
                return "訳一"
            return "訳一====訳二"

        with patch.object(mod, "ask_llm", side_effect=fake_ask_llm):
            for text in texts:
                if len(texts) == 1:
                    mod.translate_single_line(
                        text, {"用語": "訳語"}, {"简称": "訳"}, cfg, "prev"
                    )
                else:
                    mod.translate_chunk(
                        texts, {"用語": "訳語"}, {"简称": "訳"}, cfg, "prev"
                    )

        return calls[0]

    def test_translation_single_prompt_regression(self):
        current = self._capture_current_translation_prompts({}, ["日本語原文"])
        baseline = self._capture_baseline_translation_prompts({}, ["日本語原文"])
        self.assertEqual(current, baseline)

    def test_translation_chunk_prompt_regression(self):
        current = self._capture_current_translation_prompts({}, ["日本語原文一", "日本語原文二"])
        baseline = self._capture_baseline_translation_prompts({}, ["日本語原文一", "日本語原文二"])
        self.assertEqual(current, baseline)

    def test_glossary_prompt_regression(self):
        existing = {"既存": {"translated_name": "訳"}}
        pre_translated = {"参考": "訳"}

        current = glossary_processor.build_system_prompt(existing, pre_translated, {})
        current_user = glossary_processor.build_user_prompt("日本語テキスト", {})

        mod = load_head_module("glossary_processor", "babelcity/glossary_processor.py")
        baseline = mod.build_system_prompt(existing, pre_translated)
        baseline_user = mod.build_user_prompt("日本語テキスト")

        self.assertEqual(current, baseline)
        self.assertEqual(current_user, baseline_user)

    def test_qa_prompt_regression(self):
        content = """<?xml version="1.0"?><html><body><p style="opacity: 0.4;">日本語</p><p>中文译文</p></body></html>"""
        glossary = {"用語": {"translated_name": "訳語", "gender": "unknown", "type": "person"}}

        current_calls = []

        def fake_current_ask_llm_json(**kwargs):
            current_calls.append(kwargs)
            return {}

        with patch.object(qa_processor, "ask_llm_json", side_effect=fake_current_ask_llm_json):
            qa_processor.process_qa_document(content, glossary, {})

        mod = load_head_module("qa_processor", "babelcity/qa_processor.py")
        baseline_calls = []

        def fake_baseline_ask_llm_json(**kwargs):
            baseline_calls.append(kwargs)
            return {}

        with patch.object(mod, "ask_llm_json", side_effect=fake_baseline_ask_llm_json):
            mod.process_qa_document(content, glossary, {})

        self.assertEqual(current_calls[0]["system_prompt"], baseline_calls[0]["system_prompt"])
        self.assertEqual(current_calls[0]["user_prompt"], baseline_calls[0]["user_prompt"])


if __name__ == "__main__":
    unittest.main()
