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
