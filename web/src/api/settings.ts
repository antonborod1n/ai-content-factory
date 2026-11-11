import { apiGet, apiPatchJson } from "./client";
import type { Project } from "./projects";

export type RuntimeStatus = {
  openai_configured: boolean;
  openai_model: string;
  serp_configured: boolean;
  yandex_configured: boolean;
  images_enabled: boolean;
  discovery_enabled: boolean;
  image_model: string;
  article_target_word_count: number;
  app_env: string;
  openai_temperature: number;
  openai_max_tokens: number | null;
  openai_base_url_configured: boolean;
  embedding_model: string;
  embedding_dimensions: number;
  rag_enabled: boolean;
  rag_top_k: number;
  rag_chunk_size: number;
  rag_chunk_overlap: number;
  serp_provider: string;
  research_enabled: boolean;
  research_top_n: number;
  research_search_n: number;
  discovery_max_topics: number;
  discovery_search_n: number;
  yandex_serp_provider: string;
  competitor_topics_enabled: boolean;
  competitor_topics_max_topics: number;
  multi_agent_enabled: boolean;
  image_size: string;
  internal_links_enabled: boolean;
  internal_link_max: number;
  internal_link_prefix: string;
  dzen_enabled: boolean;
  dzen_target_char_count: number;
  quality_enabled: boolean;
  detector_ai_review_threshold: number;
  detector_uniqueness_floor: number;
  summary_target_char_count: number;
  article_min_word_ratio: number;
  article_expand_attempts: number;
  articles_output_dir: string;
};

export type PromptFile = {
  filename: string;
};

export type PromptDetail = {
  filename: string;
  content: string;
};

export function fetchRuntimeStatus(): Promise<RuntimeStatus> {
  return apiGet<RuntimeStatus>("/api/v1/settings/runtime");
}

export function fetchPrompts(): Promise<PromptFile[]> {
  return apiGet<PromptFile[]>("/api/v1/prompts");
}

export function fetchPrompt(filename: string): Promise<PromptDetail> {
  return apiGet<PromptDetail>(`/api/v1/prompts/${encodeURIComponent(filename)}`);
}

export function updateProject(
  projectId: string,
  body: { name: string; domain: string | null; language: "ru" | "en" },
): Promise<Project> {
  return apiPatchJson<Project>(`/api/v1/projects/${projectId}`, body);
}
