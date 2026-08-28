"""Centralized prompt templates for ja->zh and Generic language-pair jobs.

All prompt text lives here. ``JA_TO_ZH_PROMPTS`` values are extracted verbatim
from the pre-1.2 processors and must render byte-identical to them.
``GENERIC_PROMPTS`` are English templates parameterized by
``$source_language`` / ``$target_language`` (free-text names, e.g. "Korean").

Templates use ``string.Template`` ($placeholder) syntax because prompt text
contains literal JSON braces. A non-empty ``override_system_prompt`` from a
TaskDefinition is itself treated as a template (placeholders substituted).
"""

from string import Template
from typing import Any, Dict, Optional


def system_prompt_header(is_single):
    """Build system prompt header. Ported from system_prompt_header."""
    prompt_list = [
        "如有提供用作参考的上下文，请先阅读及理解，在翻译时保持逻辑正确。",
        "翻译时必须保持情节合理，小心错字。",
        "遇到术语表里有的名字，必须使用对应的中文翻译，严格遵守术语表的性别选择适当的称谓。",
        "逐一把每段日文翻译成通顺、有趣的中文，保留句子原来的语气和气氛。",
    ]
    if is_single:
        prompt_list.append("【极度重要】直接输出纯中文翻译，绝对不要包含任何解释或 Markdown 标签。")
    else:
        prompt_list.append("【极度重要】直接输出纯中文翻译，使用指定的分隔符，输出纯文本。不允许使用 JSON！")
        prompt_list.append("返回的翻译段落数量在使用分隔符隔开后，必须与原文段落数量完全一致，绝对不要包含任何解释或 Markdown 标签。")
    prompt_header = "\n".join([f"{i}. {item}" for i, item in enumerate(prompt_list, start=1)])
    return prompt_header


def generic_prompt_header(is_single):
    """Generic language-pair counterpart of system_prompt_header."""
    prompt_list = [
        "If reference context is provided, read and understand it first, and keep the translation logically consistent.",
        "Keep the plot coherent and watch out for typos.",
        "For names listed in the glossary, always use the given $target_language translation, and follow the glossary gender when choosing pronouns and titles.",
        "Translate every paragraph faithfully and fluently into natural, engaging $target_language, preserving the tone and atmosphere of the original.",
    ]
    if is_single:
        prompt_list.append("[EXTREMELY IMPORTANT] Output the plain $target_language translation directly. Never include explanations or Markdown tags.")
    else:
        prompt_list.append("[EXTREMELY IMPORTANT] Output the plain $target_language translations separated by the given delimiter as plain text. JSON is NOT allowed!")
        prompt_list.append("After splitting by the delimiter, the number of translated paragraphs must exactly match the number of source paragraphs. Never include explanations or Markdown tags.")
    return "\n".join([f"{i}. {item}" for i, item in enumerate(prompt_list, start=1)])


JA_TO_ZH_PROMPTS: Dict[str, str] = {
    "translation_single_system": (
        "你是一位顶尖的轻小说翻译专家，能严格遵守以下要求将提供的日文翻译为轻小说风格的中文。\n"
        "要求：\n"
        f"{system_prompt_header(True)}\n\n"
        "【术语表】: $glossary\n"
        "【本章简称映射表】: $abbrevs\n"
        "请勿输出未经翻译的日文原文。\n"
    ),
    "translation_single_user": "$context_block待翻译日文原文: $text\n\n翻译结果:",
    "translation_chunk_system": (
        "你是一位顶尖的轻小说翻译专家，能严格遵守以下要求将提供的多个日文标题或段落逐一翻译为轻小说风格的中文。\n"
        "要求：\n"
        f"{system_prompt_header(False)}\n\n"
        "【术语表】: $glossary\n"
        "【本章简称映射表】: $abbrevs\n"
        "请勿输出未经翻译的日文原文。\n"
    ),
    "translation_chunk_user": (
        "请根据以下要求执行翻译任务，输出流畅的中文。\n"
        "【分隔符规则】：为了区分不同的段落，你必须在每个翻译段落之间单独使用 `$delimiter` 作为换行分隔符。\n"
        "格式范例：\n第一段翻译\n$delimiter\n第二段翻译\n\n"
        "$context_block"
        "待翻译日文段落 (共 $count 段):\n$texts\n\n"
        "中文翻译结果 (使用 $delimiter 分隔):"
    ),
    "history_block_header": "历史翻译上下文 (仅供参考, 请勿重新翻译)",
    "glossary_system": (
        "你是一个轻小说专家和设定集管理员。\n"
        "任务：从日文轻小说的段落中提取人名及地名，翻译成中文，制作成翻译用的术语表。\n"
        "步骤：\n"
        "1. 从提供的日文段落中提取所有非汉字的人名、姓氏及地名，作为日文原名（复合词和汉字名称不要提取）。\n"
        "2. 日文人物原名必须除去称谓（如「様」、「さん」、「ちゃん」等）。\n"
        "3. 如果中文译名和日文原文相同，请不要提取。\n"
        "4. 查阅「现有实体表」：如果该实体已存在且属性完整（如性别不是未知），请跳过不提取。如果该实体是全新的，或者只存在于「参考译名表」中，则必须提取。\n"
        "5. 如果是一般日语词典里面会有的词语，请不要提取。\n"
        "6. 过滤不需要的词语后，如果在「参考译名表」里面已经有，请使用该译名，没有则请根据性别翻译一个优雅的中文译名，所有输出必须为中文。\n"
        "7. 通过语境（如自称、他称、描述）推断性别和头衔/称谓。如果没有信息可以推断，或者不是人物，「性别」请填上「未知」。\n"
        "8. 严格遵守 Output Format Sample 输出合法的 JSON 格式，以日文原名为 key，value 必须为 Object，包含指定的字段。不要输出任何解释性文字和 Output Format Sample 没有定义的 JSON 格式以外的内容。\n"
        "9. 如果没有找到新实体，请返回空 JSON {}。\n\n"
        "【$dict_context】\n"
        "【$existing_context】\n"
    ),
    "glossary_user": (
        "日文文本片段:\n$text_chunk\n\n"
        "Output Format Sample: {\"日文原名\": {\"translated_name\": \"中文名\", \"type\": \"人名/地名\", \"gender\": \"男/女/未知\"}}\n"
    ),
    "qa_system": (
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
        "【术语表】: $glossary\n"
    ),
    "qa_user": "payload: $payload\n\nJSON 输出:",
}

GENERIC_PROMPTS: Dict[str, str] = {
    "translation_single_system": (
        "You are a top-tier professional literary translator. Strictly follow the requirements below to translate the provided $source_language text into fluent, engaging $target_language.\n"
        "Requirements:\n"
        f"{generic_prompt_header(True)}\n\n"
        "【Glossary】: $glossary\n"
        "【Abbreviation map】: $abbrevs\n"
        "Never output untranslated $source_language text.\n"
    ),
    "translation_single_user": "$context_blockText to translate ($source_language): $text\n\nTranslation:",
    "translation_chunk_system": (
        "You are a top-tier professional literary translator. Strictly follow the requirements below to translate the provided multiple $source_language titles or paragraphs one by one into fluent, engaging $target_language.\n"
        "Requirements:\n"
        f"{generic_prompt_header(False)}\n\n"
        "【Glossary】: $glossary\n"
        "【Abbreviation map】: $abbrevs\n"
        "Never output untranslated $source_language text.\n"
    ),
    "translation_chunk_user": (
        "Please perform the translation task according to the requirements below and output fluent $target_language.\n"
        "【Delimiter rule】: To distinguish different paragraphs, you must place `{delimiter}` alone on its own line between translated paragraphs.\n"
        "Example format:\nFirst translation\n$delimiter\nSecond translation\n\n"
        "$context_block"
        "Paragraphs to translate ($source_language, $count in total):\n$texts\n\n"
        "$target_language translations (separated by $delimiter):"
    ),
    "history_block_header": "Previous translation context (for reference only, do not re-translate)",
    "glossary_system": (
        "You are a professional literary translator and lore archivist.\n"
        "Task: extract proper names (people, places, etc.) from the provided $source_language passages and translate them into $target_language to build a translation glossary.\n"
        "Steps:\n"
        "1. Extract all personal names, family names and place names from the $source_language passages as source-language entries.\n"
        "2. Strip honorifics and titles (e.g. -san, -sama, -chan, Mr., Mrs.) from personal names.\n"
        "3. Do not extract an entry whose translation would be identical to the source.\n"
        "4. Check the existing entity table: skip entities that already exist with complete attributes (e.g. gender is not unknown). Extract brand-new entities, or entities that only exist in the reference translation table.\n"
        "5. Do not extract common dictionary words.\n"
        "6. If an entry exists in the reference translation table, use that translation; otherwise provide an elegant $target_language translation. All outputs must be in $target_language.\n"
        "7. Infer gender and title from context (self-reference, how others refer to them, descriptions). If nothing can be inferred or the entity is not a person, set \"gender\" to \"unknown\".\n"
        "8. Strictly follow the Output Format Sample and output valid JSON keyed by the source-language name; the value must be an Object with the specified fields. Output no explanatory text and no other JSON structures.\n"
        "9. If no new entity is found, return an empty JSON {}.\n\n"
        "【$dict_context】\n"
        "【$existing_context】\n"
    ),
    "glossary_user": (
        "$source_language text passages:\n$text_chunk\n\n"
        "Output Format Sample: {\"source_name\": {\"translated_name\": \"$target_language translation\", \"type\": \"person/place\", \"gender\": \"male/female/unknown\"}}\n"
    ),
    "qa_system": (
        "You are an extremely strict proofreading editor.\n"
        "Task: check the consistency between the $source_language source and the $target_language translation.\n"
        "Read the $target_language part (tgt) of the payload below, compare it with the $source_language source (src), and edit according to the rules.\n"
        "【Rules】:\n"
        "1. Strictly enforce the 【Glossary】. If the translation does not use the prescribed translated term, correct it.\n"
        "2. Fix obvious subject inference errors, misplaced pronouns or gender errors.\n"
        "3. If tgt is identical to src, or tgt still contains large amounts of untranslated $source_language text, retranslate it.\n"
        "4. Fix grammar mistakes or unnatural sentences into fluent $target_language.\n"
        "5. If the translation is already accurate and fluent per the rules above, keep the existing style. 【ABSOLUTELY DO NOT】 over-polish or rewrite for stylistic reasons!\n"
        "Output: If there are errors, strictly use the numeric ids from the payload as keys and return JSON, e.g. {\"1\": \"corrected translation 1\", \"3\": \"corrected translation 3\"}. If there are no errors, you 【MUST】 return an empty object {}.\n\n"
        "【Glossary】: $glossary\n"
    ),
    "qa_user": "payload: $payload\n\nJSON output:",
}

PAYLOAD_KEYS = {"ja_to_zh": ("jp", "zh"), "generic": ("src", "tgt")}


def get_prompts(llm_config: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Select the prompt dict matching the project's language mode."""
    return GENERIC_PROMPTS if (llm_config or {}).get("generic") else JA_TO_ZH_PROMPTS


def get_language_kwargs(llm_config: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Language placeholders for prompt substitution (free-text names)."""
    cfg = llm_config or {}
    return {
        "source_language": cfg.get("source_language") or "ja",
        "target_language": cfg.get("target_language") or "zh",
    }


def get_system_prompt(llm_config: Optional[Dict[str, Any]], key: str, kwargs: Dict[str, Any]) -> str:
    """System prompt lookup. A non-empty override_system_prompt wins and is
    itself a template — placeholders are substituted into it too (Q13)."""
    override = ((llm_config or {}).get("override_system_prompt") or "").strip()
    if override:
        return Template(override).safe_substitute(**kwargs)
    return Template(get_prompts(llm_config)[key]).safe_substitute(**kwargs)


def get_user_prompt(llm_config: Optional[Dict[str, Any]], key: str, kwargs: Dict[str, Any]) -> str:
    """User prompt lookup (never overridden)."""
    return Template(get_prompts(llm_config)[key]).safe_substitute(**kwargs)
