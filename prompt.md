Please provide a detailed plan for implementing an application based on the requirements in @requirements.md. 

The plan should include the following:
- python packages to use
- database schema design
- list of python files to build with descriptions
- list of python classes and functions in each file with descriptions
- UI design including the list of tabs, panels, forms and tables with descriptions
- any potential issues or concerns
- any questions, unclear or conflicting requirements

Please save the plan in a file called plan.md.

==
Please make the following changes to the plan:

1. Do not use ebooklib as it cannot handle non-English EPUB files. Please use zipfile to process EPUBs.
2. For the Glossary Editor, when the Save button is clicked, please check if there are any issues like duplicates in the Source Term, empty Source Term or empty Translated Name. If yes, then display a warning with the duplication item and cancel the Save. If the gender and types are empty, replace them with "未知" when saving. Please also add a button to delete a glossary item. 
3. In the Job table, a "Running" job cannot be Deleted.

Regarding issues and concerns:

1. Yes, please use WAL for SQLite.
2. Yes, please compress the XHTML upon writing
3. If the program is restarted, then jobs need to be added from scratch. It is ok.
4. Based on your comments, shall we consider using Reflex instead of Streamlit? Please update if you have concerns.
5. Please see #4
6. If an EPUB is imported again, it is usually because it is a "Web Novel" EPUB. in this case, the full_path should be the same. If needed, I'll manually "Invalid" the translated file and retranslate.
7. After the original translation has completed, the Nav file should be translated (either by reusing translated headers in the chapters or use single line translation.) Then it is stored with QA_Round = 0. When QA Pass #1 is finished for each Chapter, the Nav file will be updated using the chapter headers after QA. However, if no pre-translated chapter header is found for a Nav item this times, the Nav item can be left as is (i.e. same as QA_Round = 0).
8. In the PoC prompts, the JSON format is provided and many models have been tested ok. So please use the provided logic to handle the JSON response. The same goes with the delimited output format for translation.
9. Yes, let's use opencc-python-reimplemented this times
10. If multiple Nav files are found, then let's mark only one as "Nav" and leave the others as "Resource". To pick the single "Nav", let's first go with nav.xhtml (if it exists), or else toc.xhtml (if it exists), or else the first entry in the manifest with property="nav".

Regarding questions:

1. Yes, Please create 1 Book Volume automatically for Web Novel and do not allow it to be deleted. Please do not allow adding more Book Volumes to Web Novels. The single Book Volume can be re-uploaded with more chapters as the Web Novel is updated. For an example, please see @book.epub.
2. The content field in item_translations should store the full modified XHTML with both original and translated paragraphs.
3. I have updated @requirements.md with some empty lines to make the table fields more clear. The "History" field is actually not used for QA Task but since the 3 types of task definitions are very similar, they can all be stored in the same table. History, Use mini-glossary, Synchronize quotes, Traditional Chinese, Model type, Retry attempts, Override system prompt are all used in Translation Task. In fact, the Translation Task and QA task are almost the same, the only difference is the prompt they use and the output format for the LLM.
4. Resume in translation means that only translate the items that does not have a translation OR an item that has a translation but the translation item is marked as Invalid.
5. I have updated the requirements.md to remove the "Resume" button for QA Task.
6. Yes, the "Repeat" button change the status of a Completed job to Pending so it is added back to the job queue. If the job queue is started nothing else is running, this job will be started.
7. The fields "type" and "gender" are optional, but they can also be filled with "未知" if we don't want to omit them. The JSON is passed to the LLM in the prompt as text so it does not matter too much.
8. The exported EPUB should be downloaded as a file in the browser instead of being saved locally. Since the UI is web-based, in theory it can be used by other people on the same local network. 
9. Yes, the Pre-translated terms format is a single line per item. Please refer to @example_glossary.txt.
10. A silhouette of a tower on a hill with sunset behind

Please update the plan.md and update the list of concerns or questions if there are still any based on the above.

==
Regarding the issues and concerns:

1. Please use the Reflex framework (reflex-dev/reflex) instead of Streamlit. I have updated @requirements.md.
2. Please use SQLite in WAL mode with timeout-30.0. Based on experience, each chapter takes 1-2 minutes to translate or QA and at most I will use 4-6 threads only. If the timeout is 30.0, it should be good enough.
3. Yes, searching in the XHTML content is not needed.
4. It is ok for the EPUB to take a few seconds to download.
5. Yes, the fallback logic for Nav is the same as Chapters.
6. Your understanding is correct. By marking a translated chapter as Invalid and using Resume, I can retranslate only that chapter, e.g. to fix a broken paragraph due to bad glossary.
7. Correct, this is the intended behavior. If the Nav title is broken, I can just do a translate with Resume=yes to force a retranslation. In the worst case, I just manually edit the exported EPUB file.

Open Questions:

1. Please use a warm color scheme for the sunset (e.g. orange). A generic, simple but ancient-looking tower is preferred.
2. There is no need, because we will determine the gender using LLM which is much more reliable. Please drop anything after \#. 
3. Yes, please refer to run_translation_pass in @translate_epubs_new.py. Translation Tasks can be run in parallel if threads > 1 and each chapter is assigned to a thread. If there are 10 chapters and threads = 2, each thread may translate 5 chapters. The chunks within a chapter is translated in the same thread so translated paragraphs from the last chunks can be used in the prompt for translating the chunk. 
4. In the Book Viewer, only Chapters can be displayed (since only these files are included in the spine of the EPUB). There is no need to show CSS or other files, so no need to wrap them in HTML tags. On the other hand, since an XHTML file may import a CSS resource using relative path, please see if you can make it work. You can refer 
5. Yes, let's say I have translated a book with Qwen3.6 and 1 round of QA, and with gemma-4-31b and 2 rounds of QA. If I choose Qwen3.6 as the model, the QA Rounds drop down should have 0 and 1. If I choose gemma-4-31b, the QA Rounds drop down should have 0, 1 and 2. Please note that "Original" should be also shown as an option in the model drop down, and if I choose it, the QA Round can only be 0.

Please update plan.md with these, review the requirements and plan again carefully, and see if you have any further questions.

==

On the issues and concerns:

1. This is ok for development
2. Serving the resource files as static content is preferred
3. Good
4. Good, I have space, as long as SQLite can handle databases of up to several Gb. 
5. Yes, in this case you can assume that the full_path would match. 

On the questions:

1. Let's do (a)
2. For the Glossary Editor, I would like in-line editing and bulk save. Before I "Save", all the changes are temporary in the UI table only. When I click Save, the table is checked, and converted to JSON for saving. Is it doable using AG-Grid for Reflex? In particular, I need to be able to delete a row easily, as Glossary scanning typically generates a lot of garbage. 
3. For the Export Function, I should be able to choose the Model and QA_Round based on the available Model and QA_Round of the Nav item only. When the QA_Round 1 finishes, it must create an Nav with QA_Round 1. Since the Nav is always the last item to update after all the chapters are translated or QA'ed, if a Model and QA_Round exists for Nav, this means that set of files under the Model and QA_Round should be complete. The "fall back" logic is justt a fail-safe mechanism.

Please update @plan.md again, and check carefully if there any more questions or concerns.
==
Please find my answers:

1. Yes, please use Vite
2. Yes, please use the same repo for frontend and backend. Frontend in the "web" folder.
3. Yes, let's use Lucide React
4. Please continue to use AG-Grid
5. Yes, React Query is ok
6. Websocket is perfect
7. Yes, this is good
8. Well, I think you you want to serve the chapters with a URL path that contains the model name and QA Round, am I right? In that case, for the CSS and resources, in order to match the URL path, the model name and QA round needs to be there, although you would be loading the data from the File Item table that only has volume ID and full path. Please correct me if I am wrong and you have a different plan for the chapters.
9. Persisting the mode in localStorage is fine.
10. Yes, this is ok. However, for production, I want to run one python (babelcity.py for example) that serves both the FastAPI backend and the static files. Is that ok? 
11. No authentication for now, but please design the code in a way such that OAuth2 authentication can be added easily later.
12. Don't commit @translate_epubs_new.py in the repo.

Plesae update the plan if you have no further concerns, or let me know if you have more questions.
==
I have actually selected a volume before. However, there was a message and the file was not uploaded:

Skipping data after last boundary

To make it easier to use, can you do this: 

1. Do not show the upload area in the Project Editor page
2. When a user click the upload button, open a dialog box with the upload area for that volume. There is an Ok button which is disabled.
3. After user has uploaded a file, the Ok button is enabled and the user can click it to confirm. 
4. The user can also cancel the upload by closing the dialog box.
==
Before restarting, you were working on the following tasks in the Book Viewer. Please updatae @plan.md and continue.

1. The resources returned by URLs like below seems to have garbled data:

http://localhost:8000/api/v1/resources/volumes/1aba4a27-e99c-479c-810b-eeaa2e30f432/items/item/style/fixed-layout-jp.css
http://localhost:8000/api/v1/resources/volumes/1aba4a27-e99c-479c-810b-eeaa2e30f432/items/item/image/kuchie-001.jpg

Please fix this so they return the proper contents.

2. In the left panel of the Book Viewer, currently it is showing the list of chapters as in the "li" tags in the Nav file. However, the Nav file of some EPUB does not cover all the chapters, so this is not working for them. Instead of using the Nav directly, can you do this:
   - Take the list of file paths from the OPF, like the list returned as "spine" from "get_epub_metadata", as the TOC items 
   - Take the list of li items from the Nav files, convert the href into full path (i.e if "href" is a relative path, then take folder of the Nav file itself + "/" + the relative path in "href". If it is an absolute path then use it as it), and store the mapping of full path -> link text into a dict
   - For each of the TOC items, look up the file path (href) in the above dict. If it exists, uses the mapped name. Otherwise, just use the file path (href) directly
   - This way, all the chapters would be able to show up in the left pane. Moreover, please make sure that the left arrow button and the right arrow button on the right hand side works.

==
Can you please help to analyze all method calls on what type are the input parameters expected and whether the caller are passing the right types?



==
Please continue on the "Next Steps" as you mentioned, and in addition, please help to update the following:

1. In the "Projects" tab, please add a Header like as in the "Task Definition" tab.
2. In the "Task Definition" tab,
   - If "Config Type" is "Glossary", disable the input for "Model Type", "History" and "Use Mini Glossary". Set "Threads" to 1 and prevent chaanges. 
   - If "Config Type" is "QA", disable the input for "History". 
   - "Model Type" is mandatory for "Translation Task" and "QA Task". If it is empty, please display an error when "Save" is clicked.
   - Please use "12" as the default of "History"
   - Please enable "Use Mini Glossary", "Synchronize Quotes" and "Traditional Chinese" by default.
   - Please disable "Override System Prompt" for now.
   - What is the usage of "Set Default"? It seems that there is no implementation. For it to work properly:
     - Only one config of each type can be set as default
     - The default config has a solid star in this tab
     - When creating a new "Job", if a default config of that type is set, it will be populated by default
3. In the "Jobs" tab, 
   - Please add a Header like as in the "Task Definition" tab.
   - "Progress" is not updated while a job is running. It is supposed to show the finished chapter / total chapters, e.g. "0 / 1".

Please update @plan.md and @tech_spec.md if they are not up-to-date.

===
Please continue on this project to build the following application. The requirements are in @requirements.md. The previous plan is in @plan.md. The Technical Spec is in @tech_spec.md. To recap:

## Goal
Build Babel City, a local Web Novel & EPUB Translation Organizer with a FastAPI backend, React + Vite + Tailwind CSS frontend, SQLite database, and background LLM job queue.

## Constraints & Preferences
- Python 3.11 (venv), FastAPI, SQLAlchemy, SQLite (WAL mode, `timeout=30.0`), `zipfile` (no `ebooklib`), `opencc-python-reimplemented`, `lxml`
- Frontend: React 18, TypeScript, Vite, Tailwind CSS 3, Lucide React, AG-Grid React, React Query (TanStack Query)
- WebSocket for real-time job progress; conditional rendering (no React Router)
- Frontend in `web/` folder, backend in `babelcity/` folder, same repo
- OAuth2-ready design (no auth enforced currently)
- Dark/light theme persisted in localStorage
- Production: single `python main.py` serves FastAPI + static files from `web/dist/`
- User's system Python is 3.9; `.venv` uses 3.11

## Progress
### Done
- **Phase 1: Backend Foundation ✅** — All models, API endpoints, WebSocket, EPUB handler, processors, job queue
- **Phase 2: Frontend Foundation ✅** — Vite + React + TypeScript, all 6 pages, API client, WebSocket hook, TypeScript clean, Vite build passes
- **Phase 3: Projects Tab ✅** — BookViewer with chapter nav + keyboard shortcuts, drag-and-drop EPUB upload dialog, file validation
- **Phase 4: Tasks Tab ✅** — Task CRUD with form validation (Config Name, Model, Base URL required)
- **Phase 5: Jobs Tab ✅** — Job queue with form validation (project, volume, task required), WebSocket progress
- **Phase 6: Polish & Production ✅** — ConfirmDialogs, production build, single entry point, dark/light theme, Lucide `BookOpen` as logo
- **Phase 9: BookViewer Fixes ✅** — Resource decompression, spine-based TOC, UUID chapter lookup
- **Phase 10: LLM Streaming + Full Params + Translation/QA Jobs ✅** — Streaming with metrics, all LLM params passed, complete translation/QA executors with multi-threading
- **zlib decompression fix** — `chapters.py` now uses `decompress()` helper to decompress `zlib`-compressed content before UTF-8 decoding
- **glossary_processor.py rewrite** — Updated to match PoC `translate_epubs_new.py` logic: `build_system_prompt()`, `build_user_prompt()`, `translated_name` field, smart filters
- **job_executors.py fix** — `scan_for_entities()` now passes `existing_glossary=merged` for context-aware scanning
- **Source chapters 404 fix** — `get_chapter` now uses `item_path:path` route with `full_path` lookup + fallback `%/{item_path}` and `%filename%` matching for relative nav links
- **QA Round dropdown fix** — Added `/available_translations` endpoint in `chapters.py`; `BookViewer.tsx` dynamically populates QA rounds from DB instead of hardcoding 0/1/2/3
- **EPUB export UnicodeEncodeError fix** — `projects.py` strips non-ASCII from filename before `Content-Disposition` header
- **TasksPage 3 add buttons** — Added "Glossary Config", "Translation Config", "QA Config" buttons per requirements.md; added `createMutation`, `createTask()`, updated `handleSave` for create vs update; fixed `config_type` capitalization to match backend ("Glossary", "Translation", "QA")
- **glossary_processor.py import fix** — Removed non-existent `validate_json_response` from `llm_handler` import
- **Job queue logging** — Added `logging` module and `logger` to `job_queue.py`; detailed logging in `worker_loop` for job start/completion/failure with `exc_info=True`
- **Failed job Repeat button** — Added Repeat button for Failed jobs in `JobsPage.tsx`; added "Failed" status display with error tooltip
- **Glossary double-encoding fix** — `job_executors.py` stores glossary as dict (not `json.dumps()`); `glossary.py` API handles double-encoded strings
- **Resource endpoint decompression** — `resources.py` added `_try_decompress()` helper for `zlib`-compressed CSS/images with `charset=utf-8` media types
- **Spine-based TOC** — New `/volumes/{volume_id}/toc` endpoint in `chapters.py` builds chapter list from all Chapter items + Nav name mapping; `BookViewer.tsx` uses `getTOC()` instead of parsing Nav HTML
- **UUID chapter lookup** — `get_chapter()` tries UUID lookup first (from TOC item.id), then falls back to `full_path`, relative path, and filename matching
- **LLM streaming with metrics** — `ask_llm()` uses `stream=True` with `stream_options={"include_usage": True}`; logs prompt/completion/total tokens, latency, TPS; falls back to non-streaming on error
- **top_k parameter** — Added `top_k` to `ask_llm()` and `ask_llm_json()` in `extra_body`
- **All LLM parameters passed** — All callers (`glossary_processor.py`, `translation_processor.py`, `qa_processor.py`) now pass all LLM parameters from `TaskDefinition`: temperature, top_p, min_p, top_k, presence_penalty, frequency_penalty, repetition_penalty
- **Complete translation job executor** — `execute_translation_job()` with `process_document()`, zlib compression, `ItemTranslation` storage (qa_round=0), Nav translation, complete `llm_config` from `TaskDefinition`
- **Complete QA job executor** — `execute_qa_job()` with multi-pass QA, `ThreadPoolExecutor` multi-threading (respects `config.threads`), previous round lookup, `ItemTranslation` storage with incremented `qa_round`
- **`project.glossary` type fix** — `job_executors.py` now checks `isinstance(project.glossary, dict)` before `json.loads()` (3 locations: lines 74, 151, 254)
- **`serialize_xml()` bytes fix** — `job_executors.py` now checks `isinstance(modified_xml, bytes)` before `.encode("utf-8")` (3 locations: lines 181, 210, 325)
- **`ItemTranslation.volume_id` removal** — Removed invalid `volume_id` parameter from all `ItemTranslation()` constructors (lines 183, 211, 336)
- **PK default generators** — Added `default=lambda: str(uuid.uuid4())` to all model `id` columns (`Project`, `BookVolume`, `FileItem`, `ItemTranslation`, `TaskDefinition`)
- **TPS metrics fix** — `llm_handler.py` now records `first_token_time` on first chunk received (before checking choices/content), matching PoC `_ask_llm` logic; separate `prefill_tps` and `gen_tps`
- **Nav `.encode()` fix** — `job_executors.py:210` and `api/chapters.py:144` now check `isinstance(..., bytes)` before `.encode("utf-8")`
- **`tech_spec.md` created** — 763-line comprehensive backend spec documenting all models, methods, parameters, types, and data flows

## Key Decisions
- FastAPI + React replaces Reflex entirely
- Existing Python modules reused as-is; `translate_epubs_new.py` kept as reference (excluded from git)
- Conditional rendering instead of React Router
- Chapter HTML resource paths rewritten inline to absolute API URLs for IFrame compatibility
- Web Novel projects auto-create default volume "1"
- `glossary` column: `Text` → `JSON`; content stored as `zlib`-compressed `LargeBinary`
- EPUB upload uses modal dialog with drag-and-drop, file validation, and confirm button
- Glossary field name: `translated_name` (matches PoC), not `translation`
- Lucide `BookOpen` icon used as app logo instead of custom SVG
- Task `config_type` values are capitalized ("Glossary", "Translation", "QA") per backend validation in `tasks.py:112`
- Frontend served from `web/dist/` in production; must rebuild after source changes
- TOC uses spine-based chapter list + Nav name mapping instead of parsing Nav HTML directly
- `ask_llm()` uses streaming with metrics logging matching `_ask_llm` in `translate_epubs_new.py`
- Translation/QA jobs use `ThreadPoolExecutor` for multi-threading with `config.threads`
- All model `id` columns use `default=lambda: str(uuid.uuid4())` for PK generation
- `serialize_xml()` returns `bytes` (not `str`); all callers must check type before `.encode()`
- `first_token_time` recorded on first chunk received (not on first content), matching PoC logic

## Critical Context
- `babelcity/api/chapters.py`: Content is `zlib`-compressed in DB; `decompress()` helper added; `get_chapter` uses `item_path:path` with `full_path` lookup + fallback matching; `available_translations` endpoint added; `/toc` endpoint builds spine-based chapter list with Nav name mapping; `nav_content.encode()` guarded with `isinstance` check
- `babelcity/api/resources.py`: Added `_try_decompress()` helper for `zlib`-compressed CSS/images with `charset=utf-8` media types
- `babelcity/glossary_processor.py`: Rewritten to match PoC; `validate_json_response` import removed (doesn't exist in `llm_handler.py`); passes all LLM parameters
- `babelcity/job_executors.py`: `scan_for_entities()` now passes `existing_glossary=merged`; glossary stored as dict (not `json.dumps()`); `execute_translation_job()` and `execute_qa_job()` fully implemented with multi-threading; `project.glossary` type check added; `serialize_xml()` bytes check added; `volume_id` removed from `ItemTranslation`; Nav `.encode()` guarded
- `babelcity/job_queue.py`: Added `logging` module; `worker_loop` logs job start/completion/failure with `exc_info=True` for full traceback
- `babelcity/api/projects.py`: EPUB export filename strips non-ASCII characters to avoid `UnicodeEncodeError`
- `babelcity/api/tasks.py`: Backend validates `config_type` as "Glossary", "Translation", or "QA" (capitalized)
- `babelcity/llm_handler.py`: `ask_llm()` uses streaming with metrics logging; `top_k` parameter added; `ask_llm_json()` passes `top_k`; `first_token_time` recorded on first chunk (not first content); separate prefill/gen TPS
- `babelcity/translation_processor.py`: All `ask_llm()` calls pass all LLM parameters from `llm_config`
- `babelcity/qa_processor.py`: All `ask_llm_json()` calls pass all LLM parameters from `llm_config`
- `babelcity/models.py`: All model `id` columns have `default=lambda: str(uuid.uuid4())`; `ItemTranslation` has no `volume_id` column
- `web/src/pages/TasksPage.tsx`: 3 add buttons added; `createTask()` capitalizes type; form shows for both create (`form.config_type`) and edit (`editingTask`)
- `web/src/pages/JobsPage.tsx`: Failed status shows red badge with error tooltip; Repeat button added for Failed jobs
- `web/src/pages/BookViewer.tsx`: Dynamic QA rounds from `available_translations` endpoint; model change resets QA round to 0; TOC uses `getTOC()` API instead of parsing Nav HTML
- `web/src/services/api.ts`: API client with `availableTranslations` and `getTOC` endpoints added
- `web/dist/` is up to date — rebuilt with `npx vite build`
- Backend runs on `127.0.0.1:8000`; Vite dev server proxies `/api` and `/ws`
- DB path: `babelcity.db` in project root; `BABELCITY_DB` env var overrides
- Python 3.9 on system; `.venv` uses 3.11 with all dependencies
- `plan.md` updated with Phase 9 (BookViewer Fixes) and Phase 10 (LLM Streaming + Full Params + Translation/QA Jobs)
- `tech_spec.md` created with comprehensive backend documentation (763 lines)

## Relevant Files
- `/Users/agentic/Projects/babelcity/babelcity/api/chapters.py`: Chapter/Nav serving — zlib decompression, `full_path` lookup with fallback, `available_translations` endpoint, `/toc` endpoint, UUID chapter lookup, `nav_content.encode()` guarded
- `/Users/agentic/Projects/babelcity/babelcity/api/resources.py`: EPUB resource serving — `_try_decompress()` helper for zlib-compressed CSS/images with charset=utf-8
- `/Users/agentic/Projects/babelcity/babelcity/glossary_processor.py`: Glossary scanning — rewritten to match PoC; `validate_json_response` import removed; passes all LLM parameters
- `/Users/agentic/Projects/babelcity/babelcity/job_executors.py`: Job executors — glossary stored as dict; `execute_translation_job()` and `execute_qa_job()` fully implemented with multi-threading; `project.glossary` type check; `serialize_xml()` bytes check; `volume_id` removed; Nav `.encode()` guarded
- `/Users/agentic/Projects/babelcity/babelcity/job_queue.py`: Added logging module; `worker_loop` logs job start/completion/failure with `exc_info=True`
- `/Users/agentic/Projects/babelcity/babelcity/api/projects.py`: EPUB export — filename strips non-ASCII characters
- `/Users/agentic/Projects/babelcity/babelcity/api/tasks.py`: Backend validates `config_type` as "Glossary"/"Translation"/"QA"
- `/Users/agentic/Projects/babelcity/babelcity/llm_handler.py`: LLM API handler — streaming with metrics logging; `top_k` parameter added; `ask_llm_json()` passes `top_k`; `first_token_time` on first chunk; separate prefill/gen TPS
- `/Users/agentic/Projects/babelcity/babelcity/translation_processor.py`: Translation logic — all `ask_llm()` calls pass all LLM parameters
- `/Users/agentic/Projects/babelcity/babelcity/qa_processor.py`: QA logic — all `ask_llm_json()` calls pass all LLM parameters
- `/Users/agentic/Projects/babelcity/babelcity/models.py`: All model `id` columns have `default=lambda: str(uuid.uuid4())`; `ItemTranslation` has no `volume_id` column
- `/Users/agentic/Projects/babelcity/web/src/pages/TasksPage.tsx`: 3 add buttons, `createMutation`, `createTask()`, form for create+edit, `config_type` capitalization
- `/Users/agentic/Projects/babelcity/web/src/pages/JobsPage.tsx`: Failed status display with error tooltip, Repeat button for Failed jobs
- `/Users/agentic/Projects/babelcity/web/src/pages/BookViewer.tsx`: Dynamic QA rounds from `available_translations`, model change resets QA round, TOC uses `getTOC()` API
- `/Users/agentic/Projects/babelcity/web/src/pages/ProjectEditor.tsx`: EPUB upload dialog with drag-and-drop and validation
- `/Users/agentic/Projects/babelcity/web/src/pages/GlossaryEditor.tsx`: AG-Grid glossary table (uses `translated_name`)
- `/Users/agentic/Projects/babelcity/web/src/services/api.ts`: API client with `availableTranslations` and `getTOC` endpoints added
- `/Users/agentic/Projects/babelcity/plan.md`: Full implementation plan (all phases marked done, Phase 9 and 10 added)
- `/Users/agentic/Projects/babelcity/translate_epubs_new.py`: Reference PoC code (excluded from git)
- `/Users/agentic/Projects/babelcity/tech_spec.md`: Comprehensive backend technical specification (763 lines)

## Next Steps
1. In the "Projects" tab, please add a Header like as in the "Task Definition" tab.
2. In the "Task Definition" tab,
   - If "Config Type" is "Glossary", disable the input for "Model Type", "History" and "Use Mini Glossary". Set "Threads" to 1 and prevent chaanges. 
   - If "Config Type" is "QA", disable the input for "History". 
   - "Model Type" is mandatory for "Translation Task" and "QA Task". If it is empty, please display an error when "Save" is clicked.
   - Please use "12" as the default of "History"
   - Please enable "Use Mini Glossary", "Synchronize Quotes" and "Traditional Chinese" by default.
   - Please disable "Override System Prompt" for now.
   - What is the usage of "Set Default"? It seems that there is no implementation. For it to work properly:
     - Only one config of each type can be set as default
     - The default config has a solid star in this tab
     - When creating a new "Job", if a default config of that type is set, it will be populated by default
3. In the "Jobs" tab, 
   - Please add a Header like as in the "Task Definition" tab.
   - "Progress" is not updated while a job is running. It is supposed to show the finished chapter / total chapters, e.g. "0 / 1".
4. Test translation job end-to-end (create config, start job, verify `ItemTranslation` storage)
5. Test QA job end-to-end (create QA config, run multi-pass, verify `qa_round` increments)
6. Verify streaming metrics appear in backend terminal during LLM calls
7. Verify multi-threading works for QA jobs with `threads > 1`

==

Please fix the following issues:

1. On the Jobs tab, the buttone "Start" and "Pause" are no longer on the right hand side above the table. Please move them back, and make sure they are on the same row as the "Add Job" buttons.
2. In chapters.py, in "get_toc", the chapter title seems not mapped using Nav correctly. For example, the Nav file is called "OEBPS/Text/nav.xhtml". It has the following link:

    <li><a href="episode1.xhtml">无名</a></li>

In this case "OEBPS/Text/episode1.xhtml" should be replaced by "无名" in get_toc. However, in the Book Viewer, I still see "OEBPS/Text/episode1.xhtml" in the left panel.
3. In chapters.py, in "select_nav_file", the nav selection priority is wrong. If there are items in nav_candidates, it should be hte highest priority, followed by nav.xhtml and toc.xhtml.
4. The Translate Job still does not use multiple threads. Please implement the Thread Pool for the Translate Job.
5. Job Progress is not showing properly for the Translate Job. It is still "-" when the Job has started and is Running. If the Job has just started, before the first chapter has finished, the Progress should be 0 / number of chapters.
6. Please check if the Jobs page is using websockets properly. It is polling "GET /api/v1/jobs HTTP/1.1" every second. If websockets is working fully already and there is no need to do that, please remove this. 
7. The Traditional Chinese option seems not working for Translation Tasks. The translated text is still in Simplified Chinese.
8. The "Pause" button is not working. The jobs are still running in the background. 

**Do not use the main database for testing. Create a separate temporary database for testing.**

== 

# Phase 11 review comments

Book Viewer
- Model type/QA round dropdown filtered to Nav - let's not implement this any more. The current logic actually also seem to work.

Other Concerns & Suggestions
- Job progress persistence if server restarts - let's not implement this for now. When the server restarts, if the jobs are automatically rerun, it could be difficult to manage. Anyway, if I restart the server when a job is running, I mean to kill the jobs.
- Let's not add the "Cancel" button for the running job. To stop a running job cleanly, it is better to pause the job queue. If we add a "Cancel" button to the running job, there may be a confusion whether the next "Pending" job should be started automatically. I would like to have more control on this. After all, changing the job order and resuming the job queue is just a few clicks. It is cleaner that way.
- Let's not add "batch operations" for the job queue for now. It adds complexity, and I think there is not going to be many jobs in the queue anyway based on my use case.

Additional changes needed
- The "Export EPUB" button should be on the same line as the drop down for "Model" and "QA Round" in the Book Viewer. Remember that the "Export EPUB" function export the book based on the "Model" and "QA Round". 
- The "Export EPUB" function does not work properly. Here is the error:

INFO:     127.0.0.1:52633 - "GET /api/v1/projects/08e64eac-ebde-434a-ad52-20c4f750a68a/volumes/1/export?model_type=Qwen3.6-27B&qa_round=0 HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/uvicorn/protocols/http/httptools_impl.py", line 421, in run_asgi
    result = await app(  # type: ignore[func-returns-value]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/uvicorn/middleware/proxy_headers.py", line 62, in __call__
    return await self.app(scope, receive, send)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/fastapi/applications.py", line 1163, in __call__
    await super().__call__(scope, receive, send)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/applications.py", line 90, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/middleware/errors.py", line 186, in __call__
    raise exc
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/middleware/errors.py", line 164, in __call__
    await self.app(scope, receive, _send)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/middleware/cors.py", line 88, in __call__
    await self.app(scope, receive, send)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/middleware/exceptions.py", line 63, in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py", line 18, in __call__
    await self.app(scope, receive, send)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/routing.py", line 660, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/fastapi/routing.py", line 2543, in app
    await route.handle(scope, receive, send)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/fastapi/routing.py", line 1700, in handle
    await self.original_router.handle(scope, receive, send)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/fastapi/routing.py", line 2598, in handle
    await included_router._handle_selected(scope, receive, send)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/fastapi/routing.py", line 1720, in _handle_selected
    await original_route.handle(scope, receive, send)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/fastapi/routing.py", line 1239, in handle
    await app(scope, receive, send)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/fastapi/routing.py", line 150, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/fastapi/routing.py", line 136, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/fastapi/routing.py", line 690, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/fastapi/routing.py", line 346, in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/concurrency.py", line 34, in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/anyio/to_thread.py", line 63, in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/anyio/_backends/_asyncio.py", line 2596, in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/anyio/_backends/_asyncio.py", line 1029, in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/agentic/Projects/babelcity/babelcity/api/projects.py", line 305, in export_epub
    return Response(
           ^^^^^^^^^
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/responses.py", line 46, in __init__
    self.init_headers(headers)
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/responses.py", line 61, in init_headers
    raw_headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()]
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/agentic/Projects/babelcity/.venv/lib/python3.11/site-packages/starlette/responses.py", line 61, in <listcomp>
    raw_headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()]
                                                 ^^^^^^^^^^^^^^^^^^^
UnicodeEncodeError: 'latin-1' codec can't encode characters in position 23-39: ordinal not in range(256)

Please update @plan.md again based on the above comments and let me know if there are other concerns or suggestions.

==
I want you to take over this project, which was previously generated with another model. The requirements are in @requirements.md , there was an implementation plan in @plan.md  and technical specification in @tech_spec.md . This project is to build an application called "Babel City" which is a translation tool. Currently, there is a problem. I have uploaded an EPUB file ( @book.epub ) to the database but two of files (META-INF/container.xml and the OPF file) inside the EPUB was not imported to the database due to an earlier bug. That bug was only partially fixed - new EPUBs will have those two files imported, but if I want to re-upload a EPUB for an existing project, it does not add the missing files as I have expected. It is supposed to override all the imported files when a EPUB is re-uploaded. Can you please analyze the cause of that and suggest how to fix it?