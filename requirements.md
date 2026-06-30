Project Name: Babel City

# Objective

Build a local Web Novel & EPUB Translation Organizer with a clean GUI.

# Tech Stack

- Python 3.11 (ensure compatibility with newer versions)
- Reflex (reflex-dev/reflex) for Web UI
- SQLite for database
- Ensure compatibility with Apple Silicon (MacBook Pro)

# Core Features to Scaffold:

1. Database Schema: Create an SQLite backend to store:
   - Project metadata
   - Chapters (Original text linked 1-to-many with translated text) and Resources
   - LLM Task Configurations (Model name, temperature, system prompts, and custom parameters used).
2. EPUB Ingestion: A UI mechanism to upload or parse raw files into chapters.
3. Interactive UI: there are three areas:
   - Project management - organize projects (EPUBs), support import, update, read, and glossary management.
   - LLM task configuration management - organize the parameters for three type of LLM tasks: glossary, translation, QA
   - Job queue and execution - allow an LLM job to start and run in the background, and maintain a job queue

# Detailed Requirements

## Main Data Structure

1. Project - a translation project is used for translating a light novel series or a web novel. It contains these main attributes and data:
   - Project ID: automatically generated and assigned to uniquely identify the project
   - Project type: there are two types: "Light Novel" and "Web Novel". A Light Novel can have multiple volumes. A Web Novel is not separated into volumes (in other word, only one "web" volume.)
   - Project name: the name of the novel in the target language
   - Source title: the name of the novel in the source language
   - Source language: the original language of the source material (ISO code, defaults to "ja")
   - Target language: the language to translate to (defaults to "zh")
   - Glossary table: a JSON object containing the glossary (translated terms). The key in the JSON object is the original term in the source language. The value is an object with the following fields: translated_name, type, and gender.

2. Book_Volume - a volume of the light novel, an EPUB, or an entire web novel. A project can have one or multiple Book Volumes. Attributes:
   - Volume ID: automatically generated and assigned to uniquely identify the Book_Volume
   - Project ID: the Project which this Bool_Volume belongs to
   - Volume number: the volume number can be a number (e.g. "1") or an arbitrary string (e.g. "8.5"). The Project ID and the Volume number together is used to uniquely identify the volume. For "Web Novel" type project, the Volume number is fixed to "1" and cannot be changed.
   - Source volume title: optional. The volume may have an alternative title in the source language.
   - Target volume title: optional. The alternative title translated to the target language.

3. File_Item - a file item inside a Book_Volume. Data:
   - Item ID: automatically generated and assigned to uniquely identify the File_Item
   - Volume ID: the Book_Volume which this File_Item belongs to
   - Full path: the full path (folder and file name) of this file inside the EPUB. The Volume ID and the Full path together can uniquely identity a file.
   - Content: the entire content of the file in the original source EPUB
   - Item Type: there are 3 types. "Chapter" refers to a normal page in the EPUB, as defined in the spine and is not a "Nav" item. A "Nav" item type is used for the table of content, defined with the property "nav" in the manifest. All other items, including CSS, Image, metadata, etc are all classified as Item Type "Resource".
   - Glossary scanned: whether this file has been scanned for glossary already. (default: False)
   - Obsolete: whether this file has been removed after an updated EPUB has been uploaded (default: False)

4. Item_Translation - the translated version of a File_Item which has a type of "Chapter" or "Nav". A file can have multiple translations using different LLMs. Data:
   - Translation ID: automatically generated and assigned to uniquely identify the Item_Translation
   - Item ID: the File_Item which is translated by this Item_Translation.
   - Model type: a string identifying the LLM used in translating this file. 
   - QA Round: 0 for the original translation, 1 or above for the output of each QA round. The Item ID, Model type and the QA Round together uniquely identity an Item_Translation.
   - Content: the entire content of the file in the translated language
   - Status: defaults to "True" (Valid) but can be changed to "False" (Invalid). An "Invalid" item is marked for retranslation later.
   - Last Translation Start Time
   - Last Translation End Time
   - QA Model: If QA Round > 0, store a string identifying the LLM used in performing the QA for this file.

5. Glossary_Task_Definition - different configurations of the glossary tasks can be stored here, including:
   - Config Name: a unique name to identify this configuration
   - Base URL: the API URL for the LLM (default: "http://localhost:8080/v1")
   - API key: the API key of the LLM (default: "not-needed")
   - Model: the model name to pass to the API (default: "default")
   - Max tokens: the maximum number of tokens the model can generate (default: 8192)
   - Temperature, top_p, min_p, top_k, presence penalty, frequency penalty, repetition penalty: model parameters
   - Chunk size: the size for splitting the source text into chunks (default: 12)
   - Retry attempts: the number of retry attempts if the LLM did not respond correctly (default: 2)
   - Override system prompt: override the system prompt of the LLM request if provided (optional)

6. Translation_Task_Definition - different configurations of the translation tasks can be stored here, including:
   - Config Name: a unique name to identify this configuration
   - Base URL: the API URL for the LLM (default: "http://localhost:8080/v1")
   - API key: the API key of the LLM (default: "not-needed")
   - Model: the model name to pass to the API (default: "default")
   - Max tokens: the maximum number of tokens the model can generate (default: 8192)
   - Temperature, top_p, min_p, top_k, presence penalty, frequency penalty, repetition penalty: model parameters
   - Chunk size: the size for splitting the source text into chunks (default: 12)
   - History: the number of the previously translated paragraphs to be passed to the model as historical context (default: 5)
   - Use mini-glossary: Extract and use a smaller subset of the glossary for each chunk (default: True)
   - Threads: Number of threads to use for translating chapters in parallel (default: 1)
   - Synchronize quotes: synchronize the quotes and brackets between source and translated text in case the model has hallucinated them (default: True)
   - Tradiational Chinese: use OpenCC to convert the translated text to Traditional Chinese (default: True)
   - Model type: Each of the translated file is tagged with the model type for organization. The Model type can be specified here. If it is empty, then the Model name passed to the API is used as the Model type. (optional)
   - Retry attempts: the number of retry attempts if the LLM did not respond correctly (default: 2)
   - Override system prompt: override the system prompt of the LLM request if provided (optional)

7. QA_Task_Definition - different configurations of the QA tasks can be stored here, including:
   - Config Name: a unique name to identify this configuration
   - Base URL: the API URL for the LLM (default: "http://localhost:8080/v1")
   - API key: the API key of the LLM (default: "not-needed")
   - Model: the model name to pass to the API (default: "default")
   - Max tokens: the maximum number of tokens the model can generate (default: 8192)
   - Temperature, top_p, min_p, top_k, presence penalty, frequency penalty, repetition penalty: model parameters
   - Chunk size: the size for splitting the source text into chunks (default: 12)
   - Use mini-glossary: Extract and use a smaller subset of the glossary for each chunk (default: True)
   - Threads: Number of threads to use for QA in parallel (default: 1)
   - Synchronize quotes: synchronize the quotes and brackets between source and translated text in case the model has hallucinated them (default: True)
   - Tradiational Chinese: use OpenCC to convert the translated text to Traditional Chinese (default: True)
   - Model type: Used for recording the QA model type in the Item_Translation table. If it is empty, then the Model name passed to the API is used as the Model type. (optional)
   - Retry attempts: the number of retry attempts if the LLM did not respond correctly (default: 2)
   - Override system prompt: override the system prompt of the LLM request if provided (optional)

## Main Functions
1. Project Management
   - Browse the list of all projects
   - Create a new Project
   - Add a Book Volume into a Project ("Light novel" type only)
   - Update Book Volume in a Project (modify the attributes or upload a new version of the EPUB)
   - Remove a Book Volume in a Project ("Light novel" type only)
   - Remove an existing Project (warn and ask for confirmation before action)
2. Glossary Editing
   - Browse the glossary table
   - Modify an existing glossary entry
   - Add a new entry
   - Remove an entry
   - Save the updated glossary table
3. Book Viewer
   - Choose Project, Book Volume, QA Round and either the original language or a Model type to start
   - Browse the table of content for a list of chapters
   - Display the source chapters or the translated chapters on the web UI in an iFrame
   - Toggle a file item as True/False for Obsolete 
   - Toggle a translated chapter as Valid/Invalid
   - Download the selected book as an EPUB file
4. Task Definition Management
   - For each type of task definition:
     - Create a new definition
     - Modify an existing definition
     - Default a definition
5. Job Management
   - View the statuses and progress of the pending, running and finished jobs
   - Start the job queue. If the job queue is started, it will start listening for new jobs.
   - Add a job to the job queue. If a job is already running, the next job in the queue will be executed automatically after the current one is finished. The jobs will run on the server in the background.
   - Remove a pending job in the job queue, or remove all jobs in the job queue
   - Modify the order of pending jobs in the job queue (move up, move down, move to top and move to bottom)
   - Pause the job queue. The running job will be stopped and moved to the top of the job queue.
   - Remove a finished job from the job status list, or remove all finished jobs
6. Add Glossary Task to Job Queue
   - Parameters
     - Project: specify the Project 
     - Book Volume: specify the Volume number of the Book Volume to scan for glossary
     - Configuation: specify the Glossary Task Definition to be used
     - Resume: if True, only scan the File items with Glossary scanned = False (Default: True)
     - Add only: if True, only add additional glossary. If False, then remove glossary and start from scratch (Resume needs to be set to False in this case as well.) (Default: False)
     - Pre-translated term: provide a list of pre-translated terms in the format of "Source => Translation # Comment". The pre-translated name will be used if the glossary is encountered during the scanning and added to the final glossary table.
   - Process
     - The selected Book Volume in the selected Project will be broken down into chunks based on the chunk size.
     - Each chunk is scanned for glossary terms by the LLM based on the logic of the PoC python code
     - If the LLM did not respond with valid JSON, or if the returned JSON is not an object (e.g. an Array), then the request will be retried up to the number of attempts.
     - If the source language is Japanese, original terms not containing Japanese hiragana or katakana characters will be discarded
     - Original terms with a length of more than 30 characters will be discarded
     - If the original term has a pre-translated name, then the pre-translated name is used instead.
     - Obsolete file items are excluded.
   - Output
     - The updated glossary table will be saved in the Project table.
7. Add Translation Task to Job Queue
   - Parameters
     - Project: specify the Project 
     - Book Volume: specify the Volume number of the Book Volume to translate
     - Configuation: specify the Translation Task Definition to be used
     - Resume: if True, only translate the File items which has not been translated yet, or which has been marked as "Invalid". If False, all File items are retranslated even if they have been translated before.  (Default: True)
   - Process
     - Each "Chapter" in the Book Volume is translated individually by a separate thread in the thread pool if the number of threads is more than 1
     - The chapter is broken down into chunks based on the given chunk size.
     - Each chunk is translated by calling the LLM based on the logic of the PoC python code. For the next chunk, the previously translated paragraphs are also provided as the historical context.
     - If the LLM did not generate the delimiters or the correct number of paragraphs as the result, or if some known hallucinations are detected, then some recovery logic may be used. For example, if the delimiters are missing but the number of paragraphs matches, we can also just split using line feeds. Source text repeated in the results can be simply removed.
     - If the hallucination cannot be resolved using the above method, such as empty results, the request will be retried as per the logic in the PoC python code. If the maximum number of retries has been reached, the translation process switch to "line-by-line translation". The result of that will be used as-is without further checks. 
     - After the source text has been translated, some additional handled would be done on the result to fix some common issues from LLM hallucination, e.g. the replacement of quotes or brackets. Also, if configured,  Simplified Chinese will be converted into Traditional Chinese using OpenCC.
     - The translated text is injected into the chapter XHTML document as a new paragrah below the original text. The original text will be dimmed by added style=\"opacity:0.4;\" to the tag in the XHTML document.
     - When all the chapters of the Book Volume has been translated, the "Nav" type files (table of contents) will need to be translated. However, before that, the translated headers will be loaded from each of the translated chapters first. If an item in the "Nav" contains part of a chapter header, then the previous translation of the chapter header will be used instead.
     - Obsolete file items are excluded.
   - Output
     - The results are stored in the Item_Translation table with QA Round = 0.
8. Add QA Task to Job Queue
   - Parameters
     - Project: specify the Project 
     - Book Volume: specify the Volume number of the Book Volume to translate
     - Configuation: specify the QA Task Definition to be used
     - Start version: specify the QA Round to use as the starting point. 0 is the original translated version. Subsequent QA versions will be overwritten.
     - Number of passes: specify how many round of QA to be performed
   - Process
    - Each "Chapter" in the Book Volume is handled individually by a separate thread in the thread pool if the number of threads is more than 1
     - The chapter is broken down into chunks based on the given chunk size.
     - QA for each chunk is performed by calling the LLM based on the logic of the PoC python code to return a set of corrected text. 
     - If the LLM did not respond with valid JSON, or if the returned JSON is not an object (e.g. an Array), then the request will be retried up to the number of attempts.
     - After the translated text has been corrected, some additional handled would be done on the result to fix some common issues from LLM hallucination, e.g. the replacement of quotes or brackets. Also, if configured,  Simplified Chinese will be converted into Traditional Chinese using OpenCC.
     - The corrected text is injected into the chapter XHTML document as a new paragrah below the original text. 
     - When all the chapters of the Book Volume has been checked or corrected, the "Nav" type files (table of contents) may need to be updated. However, before that, the translated headers will be loaded from each of the checked chapters first. If an item in the "Nav" contains part of a chapter header, then the previous translation of the chapter header will be used instead.
     - Obsolete file items are excluded.
   - Output
     - The results are stored in the Item_Translation table with QA Round > 0 (starting from Start version + 1).
9. Import EPUB
   - Parameters
     - Project: specify the Project 
     - Book Volume: specify the Volume number of the Book Volume to upload. For a "Web Novel" project, the volume number will be always "1".
     - EPUB: the file to upload
   - Process
     - If the Book Volume does not have any File Items, *all* the files in the uploaded EPUB file are extracted and stored in the File_Item table, including the "Chapter", "Nav" and other "Resource" like CSS, cover image, metadata files, OPF, etc.
     - If there are already existing File Items, then the existing File Items with the same Full path will have the contents replaced. The new files will be added.
     - If an existing File_Item is not included in the uploaded EPUB, then it is marked as Obsolete = True.
     - There should be only one "Nav" in the manifest of the EPUB. However, if it is missing, but we can find a file with a name like nav.xhtml or toc.xhtml or with a media type of application/x-dtbncx+xml, then we will use it as the "Nav". If we cannot find a single "Nav", the import should be rejected.
   - Output
     - All the files in the uploaded EPUB are stored in the File_Item table.
10. Export EPUB
   - Parameters
     - Project: specify the Project 
     - Book Volume: specify the Volume number of the Book Volume to upload. For a "Web Novel" project, the volume number will be always "1".
     - Model type: the translation model type as specified in the Translation Task Definition and stored in Item_Translation.
     - QA Round: 0 for the original translation, 1 or more for the QA version.
   - Process
     - Create an EPUB with the following file name:
       - If "Target volume title" is not empty, use \(Target volume title\)\_\(model type\)\_\(QA Round\).epub 
       - If "Target volume title" is empty, use \(Project name\)\_\(volume number\)\_\(model type\)\_\(QA Round\).epub 
     - For eac File Item:
       - If the Item Type is "Chapter" or "Nav":
         - If an Item_Translation for the given QA Round and Model type exists, use it
         - Otherwise, if an Item_Translation for the given Model type and QA Round = 0 exists, use it
         - Otherwise, use the original content in the source language in File_Item
       - If the Item Type is "Resource":
         - Include the original content in the source language in File_Item
   - Output
     - An EPUB file ready for download

## User Interface

1. The user interface is a single page HTML5 applicatin intended for personal use. The style is modern, elegant and minimalist.
2. Create a modern, simplistic logo icon for this project with transparent background in SVG format
3. The main user interface has a navigation bar at the top. It contains:
   - Show the logo icon and the title of the project "Babel City" on the left. 
   - In the center of the navigation bar, it allows the user to switch between 3 tabs: Projects, Tasks and Jobs.
   - On the right, there is a toggle for Light/Dark theme
3. The Projects tab (Project Management)
   - The main view of the Projects page display the list of existing projects in a table form.
     - The first few columns are the Project ID, Project name and Project type. Clicking on the Project ID or Project name will open the Project Editor.
     - The column after that contains a drop down box for the Book Volumes. Selecting one of them will navigate to the Book View. 
     - After that, there are icon buttons for Glossary (with a table icon), Modify (a pen icon), Delete (a trash can icon). Clicking the Glossary icon open the Glossary Editor. Clicking the Modify icon opens the Project Editor. Clicking the Delete button will pops up a warning box asking user for confirmation.
   - Above the table on the left hand side, there is an "Add" button (with a plus icon) to open a form to create a new project.
   - When the user select a Volume to "View Book", the Book Viewer is displayed.
     - This view has an option bar on the top. Below it, there are two panels, one of the left and one on the right. 
     - The bar on top that contains a drop down box for selecting the Model type and the QA Round ("Source" is shown as a "Model Type"). Only the available Model type and QA Rounds for the "Nav" Item_Translation are shown. 
     - The left panel shows the list of chapters, sorted according to the "Nav" of the EPUB.  
     - The right panel is an IFrame showing the contents of the Book chapter.
     - At the bottom of the right panel, below the IFrame, there is a bar should the following information in smaller fonts: Obsolete flag (a checkbox), Status (a checkbox), Last Translation Start Time, Last Translation End Time, and QA Model. If the checkbox are clicked, a pop-up dialog is displayed asking the user for confirmation before updating.
   - When the user choose to Modify a Project, the Project Editor is opened.
     - The first part of the Project Editor allows the Project Name, Source title, Source language and Target language to be updated. The Project type cannot be modified.
     - The second part of the Project Editor contains two buttons on the left hand side: "Add Book Volume" (with a plus icon) and "Glossary" (with a table icon)
     - Below the buttons, there is a table showing the list of Book Volumes
       - The first two columns are the Volume ID and the Volumn Number. Clicking on the Volume ID or the Volume Number open the Book Viewer above.
       - After that, there is a column with the following icon buttons: "View" (with a book icon) and "Upload" (with an upload icon). Clicking the "View" button open the Book Viewer. Clicking "Upload" opens a dialog box to allow user to upload a file. If there is already a file uploaded for this Book Volume, a warning is displayed to ask for confirmation below proceeding.
       - After that, there are two columns allow the Source and Target volume titles to be updated.
   - When the user choose to modify the Glossary, the Glossary Editor is displayed.
       - It has a table with the following columns:
         - Original term in the source language
         - Translated_name
         - Type
         - Gender
       - There is a button on the left above the table: "Save" (with a disk icon)
4. The Task Definition tab
   - The page contains two parts: the button bar and a table
   - The button bar has 3 buttons on the left: "Glossary Config", "Translation Config" and "QA Config". All 3 buttons have a plus icon on the left.
     - "Glossary Config": open a Glossary Task Definition form to allow all the fields in the Glossary_Task_Definition table to be entered.
     - "Translation Config": open a Translation Task Definition form to allow all the fields in the Translation_Task_Definition table to be entered.
     - "QA Config": open a QA Task Definition form to allow all the fields in the QA_Task_Definition table to be entered.
   - Below the button bar, there is a table listed the tasks defined. It has the following columns:
     - Config Name: the name of the configuration
     - Config type: Glossary, Translation or QA
     - Model: the model name for the LLM API
     - Icon buttons: "Edit" (with a pen icon) and "Delete" (with a trash can icon)
5. The Job Management tab
   - The page contains two parts: the button bar and a table
   - The button bar has 3 button on the left: "Glossary Job", "Translation Job" and "QA Job". All 3 buttons have a plus icon on the left.
     - "Glossary Job": Refer to the "Add Translation Task to Job Queue" function. Open a Glossary Job form which has drop down boxes for choosing a Project, a Book Volume and a Glossary Task Definition, as well as a checkbox for entering the value for Resume and Add only. Finally, there is a large, resizable multi-line text box for the user to paste or enter the pre-translated terms.
     - "Translation Job": Refer to the "Add Translation Task to Job Queue" function. Open a Translation Job form which has drop down boxes for choosing a Project, a Book Volume and a Translation Task Definition, as well as a checkbox for changing the value for Resume.
     - "QA Job": Refer to the "Add QA Task to Job Queue" function. Open a QA Job form which have drop down boxes for choosing a Project, a Book Volume, a QA Task Definition, the Start version and an input box for Number of passes.
   - The button bar also has 2 buttons on the right: "Start" (with a play button) and "Pause" (with a pause button). These buttons control the job queue.
   - There is a Job Status table which includes the following columns:
     - Job type: Glossary, Translation or QA
     - Project Name
     - Volume Number
     - Job Status: Running, Completed, or Pending
     - Progress: if the Job Status is Running, show the completed chapters / total chapters.
     - Buttons: "Up" (with a up icon), "Down" (with a down icon), "Top" (with a top icon), "Bottom" (with a bottom icon), "Repeat" (with a repeat icon) and "Delete" (with a trash can icon). The Up/Down/Top/Bottom buttons are only available for Pending Jobs only. The Report button is only available for Completed Jobs only.
6. Other general guidelines
   - When dangerous or irreversible functions are performed, the user should be asked for confirmation.
   - Meaningful error messages should be returned if the process cannot proceed as expected.
   - Tables should scale with the width of the page
   - Each button should have a matching icon on the left of the text
   - Items in any drop down boxes should be sorted
   - Items in tables should be sorted (e.g. by Project Name or Volume Number)

# Workflow

Read the provided PoC python code (translate_epubs_new.py) to understand the detailed logic but treat is as reference only, Generate the task list, provide the implementation plan, build the files, handle dependencies locally, and run the app to verify the UI functionality.

## Appendix A: Structural & Architectural Constraints

1. **Backend & Backend Alignment:**
   - The new application should not be a wrapper around the provide translate_epubs_new.py script. Rather, it should copy and enhance the following applicable functions and integrate within the new application. 
     - _build_mini_glossary: create a mini-glossary using a subset of the global glossary which only contains words given in the given text
     - _remove_think_tags: remove the thinking context from the given text to prevent reasoning artifacts from leaking into final outputs.
     - _sync_quotes: synchronize the quote and brackets from the source text to the translated text
     - _finalize_text: process the translation results
     - _load_dictionary: load the pre-translated terms
     - _ask_llm: use for calling the LLM for translation and other tasks
     - _extract_text_with_ruby: convert ruby tags to (ruby)
     - _extract_json: extract json from LLM output
     - _has_japanese: check if there are Japanese text
     - _parse_xml: parse XHTML into a tree
     - _serialize_xml: convert an XML tree into string
     - _get_epub_metadata: read the EPUB metadata and extract the spine and table of contents.
     - scan_for_entities: scan the given text chunk for glossary terms
     - translate_single_line: translate one line of novel text using the glossary and historical paragraphs
     - translate_chunk: translate one chunk of novel text using the glossary and historical paragraphs
     - _translate_toc_content: translate the TOC, but reuse pre-translated headers if possible
     - _apply_translation_to_chunk: add translated text below the original text
     - _process_toc: translate a table of content (Nav) file
     - _process_document: translate a chapter of the novel
     - _process_qa_document: QA a chapter of the novel
   - Please use the Chinese system and user prompts from the provided translate_epubs_new.py script in the new application. Although we want to allow the user to override the system prompts later, at the moment please do not implement this yet. Just leave the fields for override system prompts empty and unused.
   - The provided translate_epubs_new.py script was heavily hardcoded to be used for Japanese to Chinese translation. For now, all the special logic related to the handling of Japanese should still be retained and enabled by default in the new application.
   - Specifically, ensure the background worker ports the exact behavior of the following algorithmic loops from `translate_epubs_new.py`:
     * Text Chunking & Sliding Context Window: Match how paragraphs are grouped by `chunk_size` and how the `history` parameter appends previous blocks as context.
     * Delimiter & Paragraph Recovery: Port the exact validation checks that verify if the LLM output matches the expected input paragraph count. Preserve the fallback routine that switches to line-by-line translation if multiple recovery attempts fail.
   - No need to implement resolve_contextual_names. This function is not needed as it is not too useful.
   
2. **Data Storage & EPUB Extraction Integration:**
   - When an EPUB is uploaded via the UI, it must be parsed using the `_get_epub_metadata` approach from the script.
   - Individual files must be stored into the `File_Item` database table, keeping the original XML structures intact so that formatting (<ruby> tags, styles) is preserved when mapping chunks back together.

## Appendix B: Development Environment & Execution Policy

1. **Isolated Environment Creation:**
   - Before installing any dependencies or generating code, create a dedicated Python 3.11 virtual environment named `.venv` in the project root directory: `python3.11 -m venv .venv`.
   - All subsequent library installations, testing scripts, and database initialization tools MUST explicitly target this virtual environment's executables directly via `./.venv/bin/pip` and `./.venv/bin/python`. Do not rely on loose shell activation hooks.
   - Generate a strict `requirements.txt` file containing pinned dependencies. 
