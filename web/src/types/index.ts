export interface Project {
  id: string
  project_name: string
  source_title: string
  project_type: string
  source_language: string
  target_language: string
  glossary: Record<string, any>
  created_at: string
  updated_at: string
  volumes: Volume[]
}

export interface Volume {
  id: string
  volume_number: string
  project_id: string
  source_volume_title: string | null
  target_volume_title: string | null
  created_at: string
  updated_at: string
}

export interface TaskDefinition {
  id: string
  config_name: string
  config_type: string
  base_url: string
  api_key: string
  model: string
  max_tokens: number
  temperature: number | null
  top_p: number | null
  min_p: number | null
  top_k: number | null
  presence_penalty: number | null
  frequency_penalty: number | null
  repetition_penalty: number | null
  chunk_size: number
  history: number | null
  use_mini_glossary: boolean | null
  threads: number
  synchronize_quotes: boolean
  traditional_chinese: boolean
  model_type: string | null
  retry_attempts: number
  override_system_prompt: string | null
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface Job {
  id: string
  job_type: string
  project_id: string
  project_name: string
  volume_number: string
  config_id: string
  status: string
  current: number
  total: number
  message: string
  result_message: string
  created_at: string
}

export interface FileItem {
  id: string
  volume_id: string
  full_path: string
  content: string
  item_type: string
  glossary_scanned: boolean
  obsolete: boolean
}

export interface ItemTranslation {
  id: string
  item_id: string
  model_type: string
  qa_round: number
  content: string
  status: boolean
  last_translation_start: string | null
  last_translation_end: string | null
  qa_model: string | null
}

export interface ChapterMeta {
  item_id: string
  full_path: string
  item_type: string
  obsolete: boolean
  glossary_scanned: boolean
  translations: ItemTranslation[]
}