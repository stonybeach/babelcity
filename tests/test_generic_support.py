"""Tests for Generic project type support."""

import json
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from babelcity.api.projects import (
    ProjectCreate,
    ProjectUpdate,
    VolumeCreate,
    add_volume,
    create_project,
    get_project,
    remove_volume,
    update_project,
)
from babelcity.database import Base
from babelcity import glossary_processor, job_executors, qa_processor, translation_processor
from babelcity.job_executors import _inject_project_language_context
from babelcity.job_queue import Job
from babelcity.models import Project, TaskDefinition
from babelcity.prompts import PAYLOAD_KEYS, get_language_kwargs, get_prompts, get_system_prompt, get_user_prompt
from babelcity.text_processor import failed_translation_generic, has_literal_text_generic


class GenericProjectApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def create(self, **overrides):
        data = {
            "project_name": "Generic Project",
            "source_title": "Source",
            "project_type": "Generic",
            "source_language": "Korean",
            "target_language": "Spanish",
        }
        data.update(overrides)
        return create_project(ProjectCreate(**data), self.db)

    def assert_status(self, exc_type, status, func, *args, **kwargs):
        with self.assertRaises(exc_type) as ctx:
            func(*args, **kwargs)
        self.assertEqual(ctx.exception.status_code, status)

    def test_create_generic_requires_source_language(self):
        self.assert_status(HTTPException, 400, self.create, source_language="   ")

    def test_create_generic_requires_target_language(self):
        self.assert_status(HTTPException, 400, self.create, target_language="   ")

    def test_create_generic_stores_trimmed_languages(self):
        project_id = self.create(source_language=" Korean ", target_language=" Spanish ")["id"]
        project = get_project(project_id, self.db)
        self.assertEqual(project["source_language"], "Korean")
        self.assertEqual(project["target_language"], "Spanish")

    def test_create_light_novel_forces_ja_to_zh(self):
        project_id = self.create(
            project_name="Light Novel Project",
            project_type="Light Novel",
            source_language="English",
            target_language="French",
        )["id"]
        project = get_project(project_id, self.db)
        self.assertEqual(project["source_language"], "ja")
        self.assertEqual(project["target_language"], "zh")

    def test_create_web_novel_auto_volume_generic_can_add_volume(self):
        web_id = self.create(project_name="Web", project_type="Web Novel")["id"]
        generic_id = self.create(project_name="Generic", project_type="Generic")["id"]

        self.assertEqual([v["volume_number"] for v in get_project(web_id, self.db)["volumes"]], ["1"])
        self.assertEqual(get_project(generic_id, self.db)["volumes"], [])

        add_volume(generic_id, VolumeCreate(volume_number="1"), self.db)
        self.assertEqual([v["volume_number"] for v in get_project(generic_id, self.db)["volumes"]], ["1"])

        self.assert_status(HTTPException, 400, add_volume, web_id, VolumeCreate(volume_number="2"), self.db)

    def test_update_generic_language_trims_and_rejects_change_project_type(self):
        project_id = self.create()["id"]
        update_project(project_id, ProjectUpdate(source_language=" Portuguese ", target_language=" German "), self.db)
        project = get_project(project_id, self.db)
        self.assertEqual(project["source_language"], "Portuguese")
        self.assertEqual(project["target_language"], "German")

        self.assert_status(HTTPException, 400, update_project, project_id, ProjectUpdate(project_type="Light Novel"), self.db)
        self.assert_status(HTTPException, 400, update_project, project_id, ProjectUpdate(source_language="   "), self.db)

    def test_update_light_novel_language_cannot_change(self):
        project_id = self.create(project_name="Light", project_type="Light Novel")["id"]
        self.assert_status(HTTPException, 400, update_project, project_id, ProjectUpdate(source_language="English"), self.db)
        self.assert_status(HTTPException, 400, update_project, project_id, ProjectUpdate(target_language="French"), self.db)

    def test_remove_volume_generic_only_web_protected(self):
        generic_id = self.create(project_name="Generic", project_type="Generic")["id"]
        web_id = self.create(project_name="Web", project_type="Web Novel")["id"]

        add_volume(generic_id, VolumeCreate(volume_number="1"), self.db)
        remove_volume(generic_id, "1", self.db)
        self.assertEqual(get_project(generic_id, self.db)["volumes"], [])
        self.assert_status(HTTPException, 400, remove_volume, web_id, "1", self.db)


class GenericLanguageContextTest(unittest.TestCase):
    def test_generic_injection_disables_ja_zh_specific_options(self):
        config = SimpleNamespace(override_system_prompt="custom $target_language prompt")
        project = SimpleNamespace(
            project_type="Generic",
            source_language="Korean",
            target_language="Spanish",
        )
        llm_config = {"traditional_chinese": True, "synchronize_quotes": True}

        _inject_project_language_context(llm_config, project, config)

        self.assertTrue(llm_config["generic"])
        self.assertEqual(llm_config["source_language"], "Korean")
        self.assertEqual(llm_config["target_language"], "Spanish")
        self.assertEqual(llm_config["override_system_prompt"], "custom $target_language prompt")
        self.assertFalse(llm_config["traditional_chinese"])
        self.assertFalse(llm_config["synchronize_quotes"])

    def test_ja_to_zh_injection_keeps_japanese_pipeline_flags(self):
        config = SimpleNamespace(override_system_prompt=None)
        project = SimpleNamespace(
            project_type="Light Novel",
            source_language="ja",
            target_language="zh",
        )
        llm_config = {"traditional_chinese": True, "synchronize_quotes": True}

        _inject_project_language_context(llm_config, project, config)

        self.assertFalse(llm_config["generic"])
        self.assertTrue(llm_config["traditional_chinese"])
        self.assertTrue(llm_config["synchronize_quotes"])

    def test_prompt_selection_substitutes_generic_languages(self):
        cfg = {
            "generic": True,
            "source_language": "Korean",
            "target_language": "Spanish",
            "override_system_prompt": "Translate to $target_language.",
        }
        kwargs = get_language_kwargs(cfg)

        self.assertIs(get_prompts(cfg), __import__("babelcity.prompts", fromlist=["GENERIC_PROMPTS"]).GENERIC_PROMPTS)
        self.assertEqual(PAYLOAD_KEYS["generic"], ("src", "tgt"))
        self.assertEqual(get_system_prompt(cfg, "translation_single_system", kwargs), "Translate to Spanish.")
        self.assertIn("Korean", get_user_prompt(cfg, "translation_single_user", kwargs))

    def test_generic_failure_checks_are_language_agnostic(self):
        self.assertTrue(has_literal_text_generic("한글"))
        self.assertTrue(has_literal_text_generic("Español"))
        self.assertTrue(has_literal_text_generic("ー한글"))
        self.assertFalse(has_literal_text_generic("---"))
        self.assertFalse(has_literal_text_generic("123"))
        self.assertFalse(has_literal_text_generic("ーーーーーー"))
        self.assertFalse(has_literal_text_generic("ー 〜 ‥"))

        self.assertFalse(failed_translation_generic(["한글"], ["Spanish translation"]))
        self.assertTrue(failed_translation_generic(["한글"], [""]))
        self.assertTrue(failed_translation_generic(["한글"], ["한글"]))

        self.assertTrue(failed_translation_generic(["12345678901"], ["y" * 56]))
        self.assertFalse(failed_translation_generic(["12345678901"], ["y" * 55]))
        self.assertTrue(failed_translation_generic(["x" * 21], ["y" * 4]))
        self.assertFalse(failed_translation_generic(["x" * 21], ["y" * 5]))


class GenericProcessorPipelineTest(unittest.TestCase):
    def cfg(self, override=None):
        cfg = {
            "generic": True,
            "source_language": "Korean",
            "target_language": "Spanish",
            "retry_attempts": 1,
            "history": 1,
            "chunk_size": 10,
            "use_mini_glossary": False,
            "traditional_chinese": True,
            "synchronize_quotes": True,
        }
        if override:
            cfg["override_system_prompt"] = override
        return cfg

    def test_translation_single_line_uses_generic_prompts_and_bypasses_finalize(self):
        calls = []

        def fake_ask_llm(system_prompt, user_prompt, **kwargs):
            calls.append((system_prompt, user_prompt))
            return "Hola mundo"

        with patch.object(translation_processor, "ask_llm", side_effect=fake_ask_llm):
            result = translation_processor.translate_single_line("안녕하세요 세계", {}, {}, self.cfg())

        self.assertEqual(result, "Hola mundo")
        self.assertIn("Spanish", calls[0][0])
        self.assertIn("Korean", calls[0][1])

    def test_translation_override_system_prompt_reaches_llm(self):
        calls = []
        glossary = {"김": "Kim"}

        def fake_ask_llm(system_prompt, user_prompt, **kwargs):
            calls.append((system_prompt, user_prompt))
            return "Hola"

        cfg = self.cfg(override="Translate $source_language into $target_language using $glossary now.")
        with patch.object(translation_processor, "ask_llm", side_effect=fake_ask_llm):
            result = translation_processor.translate_single_line("안녕하세요", glossary, {}, cfg)

        self.assertEqual(result, "Hola")
        self.assertEqual(
            calls[0][0],
            f"Translate Korean into Spanish using {json.dumps(glossary, ensure_ascii=False)} now.",
        )

    def test_glossary_override_system_prompt_reaches_llm(self):
        calls = []
        existing = {"서울": {"translated_name": "Seoul"}}
        pre_translated = {"김": "Kim"}

        def fake_ask_llm_json(**kwargs):
            calls.append(kwargs)
            return {}

        cfg = self.cfg(override="Scan $source_language into $target_language. $dict_context|$existing_context")
        with patch.object(glossary_processor, "ask_llm_json", side_effect=fake_ask_llm_json):
            glossary_processor.scan_for_entities(
                "안녕하세요 세계",
                cfg,
                existing_glossary=existing,
                pre_translated=pre_translated,
            )

        expected_dict = f"Reference translation table: {json.dumps(pre_translated, ensure_ascii=False)}\n"
        expected_existing = f"Existing entity table: {json.dumps(existing, ensure_ascii=False)}\n"
        self.assertEqual(calls[0]["system_prompt"], f"Scan Korean into Spanish. {expected_dict}|{expected_existing}")

    def test_qa_override_system_prompt_reaches_llm(self):
        calls = []
        glossary = {"김": "Kim"}

        def fake_ask_llm_json(**kwargs):
            calls.append(kwargs)
            return {}

        content = """<?xml version="1.0"?><html><body><p style="opacity: 0.4;">한글</p><p>Old</p></body></html>"""
        cfg = self.cfg(override="Review $source_language into $target_language using $glossary.")
        with patch.object(qa_processor, "ask_llm_json", side_effect=fake_ask_llm_json):
            qa_processor.process_qa_document(content, glossary, cfg)

        self.assertEqual(
            calls[0]["system_prompt"],
            f"Review Korean into Spanish using {json.dumps(glossary, ensure_ascii=False)}.",
        )

    def test_process_document_keeps_non_latin_letters_and_skips_symbols(self):
        calls = []

        def fake_translate_chunk(texts, *args, **kwargs):
            calls.append(list(texts))
            return ["First line", "Segunda línea"]

        content = """<?xml version="1.0"?><html><body><p>한글</p><p>***</p><p>Español</p></body></html>"""
        with patch.object(translation_processor, "translate_chunk", side_effect=fake_translate_chunk):
            xml, _ = translation_processor.process_document(content, {}, self.cfg())

        xml_text = xml.decode("utf-8")
        self.assertEqual(calls, [["한글", "Español"]])
        self.assertEqual(xml_text.count("<p"), 5)
        self.assertLess(xml_text.index("한글"), xml_text.index("First line"))
        self.assertLess(xml_text.index("First line"), xml_text.index("***"))
        self.assertLess(xml_text.index("***"), xml_text.index("Español"))
        self.assertLess(xml_text.index("Español"), xml_text.index("Segunda línea"))

    def test_process_document_generic_headings_are_mapped_without_japanese(self):
        def fake_translate_chunk(texts, *args, **kwargs):
            return ["Capítulo", "Primera línea"]

        content = """<?xml version="1.0"?><html><body><h1>제 목차</h1><p>한글</p></body></html>"""
        with patch.object(translation_processor, "translate_chunk", side_effect=fake_translate_chunk):
            xml, heading_map = translation_processor.process_document(content, {}, self.cfg())

        self.assertEqual(heading_map, {"제 목차": "Capítulo"})

    def test_glossary_scan_generic_keeps_non_japanese_names_and_applies_override(self):
        calls = []

        def fake_ask_llm_json(**kwargs):
            calls.append(kwargs)
            return {
                "김철수": {"translated_name": "Old", "type": "person", "gender": "male"},
                "서울": {"translated_name": "Old Seoul", "type": "place", "gender": "unknown"},
            }

        cfg = self.cfg()
        with patch.object(glossary_processor, "ask_llm_json", side_effect=fake_ask_llm_json):
            terms = glossary_processor.scan_for_entities(
                "김철수는 서울에 왔다",
                cfg,
                existing_glossary={},
                pre_translated={"김철수": "Kim Chul-su"},
            )

        self.assertIn("김철수", terms)
        self.assertIn("서울", terms)
        self.assertEqual(terms["김철수"]["translated_name"], "Kim Chul-su")
        self.assertIn("Spanish", calls[0]["system_prompt"])
        self.assertIn("Korean", calls[0]["user_prompt"])

    def test_qa_generic_uses_src_tgt_payload_and_applies_generic_failure_check(self):
        calls = []

        def fake_ask_llm_json(**kwargs):
            calls.append(kwargs)
            return {"1": "Una línea"}

        content = """<?xml version="1.0"?><html><body><p style="opacity: 0.4;">한글</p><p>Old</p></body></html>"""
        with patch.object(qa_processor, "ask_llm_json", side_effect=fake_ask_llm_json):
            xml, _ = qa_processor.process_qa_document(content, {}, self.cfg())

        self.assertIn("Una línea", xml.decode("utf-8"))
        self.assertIn("Spanish", calls[0]["system_prompt"])
        self.assertIn("Korean", calls[0]["system_prompt"])
        self.assertIn('"src"', calls[0]["user_prompt"])
        self.assertIn('"tgt"', calls[0]["user_prompt"])
        self.assertNotIn('"jp"', calls[0]["user_prompt"])
        self.assertNotIn('"zh"', calls[0]["user_prompt"])


class ExecuteJobSmokeTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

        self.project = Project(
            project_type="Generic",
            project_name="Generic Project",
            source_title="Source",
            source_language="Korean",
            target_language="Spanish",
            glossary={"김": "Kim"},
        )
        self.config = TaskDefinition(
            config_name="generic-config",
            config_type="Translation",
            base_url="http://example.test/v1",
            api_key="test-key",
            model="generic-model",
            max_tokens=1234,
            temperature=0.2,
            top_p=0.9,
            min_p=0.1,
            top_k=20,
            presence_penalty=0.3,
            frequency_penalty=0.4,
            repetition_penalty=0.5,
            chunk_size=17,
            history=5,
            use_mini_glossary=False,
            threads=3,
            synchronize_quotes=True,
            traditional_chinese=True,
            override_system_prompt="Translate $source_language into $target_language.",
        )
        self.db.add_all([self.project, self.config])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    @contextmanager
    def _fake_session(self):
        yield self.db

    def _job(self, job_type):
        return Job(
            id=f"{job_type.lower()}-job",
            job_type=job_type,
            project_id=self.project.id,
            project_name=self.project.project_name,
            volume_id="volume-1",
            volume_number="1",
            config_id=self.config.id,
            params={"resume": True},
        )

    def test_execute_job_preloads_shared_context_and_dispatches_every_job_type(self):
        progress_callback = lambda *args: None
        stop_callback = lambda: False

        for job_type, mock_name in (
            ("Glossary", "execute_glossary_job"),
            ("Translation", "execute_translation_job"),
            ("QA", "execute_qa_job"),
        ):
            job = self._job(job_type)
            with patch.object(job_executors, "get_session", new=self._fake_session), \
                    patch.object(job_executors, mock_name) as executor:
                job_executors.execute_job(job, progress_callback, stop_callback)

            args = executor.call_args.args
            self.assertEqual(args[0], job)
            self.assertIs(args[1], progress_callback)
            self.assertIs(args[2], stop_callback)
            self.assertIs(args[3], self.db)
            self.assertIs(args[4], self.project)
            self.assertIs(args[5], self.config)
            self.assertEqual(args[7], {"김": "Kim"})

            llm_config = args[6]
            self.assertTrue(llm_config["generic"])
            self.assertEqual(llm_config["source_language"], "Korean")
            self.assertEqual(llm_config["target_language"], "Spanish")
            self.assertFalse(llm_config["traditional_chinese"])
            self.assertFalse(llm_config["synchronize_quotes"])
            self.assertEqual(llm_config["override_system_prompt"], "Translate $source_language into $target_language.")
            self.assertEqual(llm_config["model"], "generic-model")

            if job_type == "Glossary":
                self.assertNotIn("chunk_size", llm_config)
            else:
                self.assertEqual(llm_config["chunk_size"], 17)
                self.assertEqual(llm_config["threads"], 3)

    def test_execute_job_keeps_light_novel_language_context(self):
        self.project.project_type = "Light Novel"
        self.project.source_language = "ja"
        self.project.target_language = "zh"
        self.db.commit()
        job = self._job("Translation")

        with patch.object(job_executors, "get_session", new=self._fake_session), \
                patch.object(job_executors, "execute_translation_job") as executor:
            job_executors.execute_job(job, lambda *args: None)

        args = executor.call_args.args
        llm_config = args[6]
        self.assertFalse(llm_config["generic"])
        self.assertEqual(llm_config["source_language"], "ja")
        self.assertEqual(llm_config["target_language"], "zh")
        self.assertTrue(llm_config["traditional_chinese"])
        self.assertTrue(llm_config["synchronize_quotes"])

    def test_execute_job_rejects_unknown_job_type(self):
        with patch.object(job_executors, "get_session", new=self._fake_session):
            with self.assertRaises(ValueError):
                job_executors.execute_job(self._job("Unknown"), lambda *args: None)


if __name__ == "__main__":
    unittest.main()
