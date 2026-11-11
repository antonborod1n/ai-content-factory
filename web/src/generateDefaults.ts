import { currentProjectId } from "./api/client";

const STORAGE_KEY = "acf.generateDefaults";

function projectKey(): string {
  return `${STORAGE_KEY}.${currentProjectId()}`;
}

export type GenerateDefaults = {
  use_knowledge_base: boolean;
  use_competitor_research: boolean;
  use_multi_agent: boolean;
  use_images: boolean;
  use_dzen: boolean;
  use_detectors: boolean;
  use_humanizer: boolean;
  use_summary: boolean;
  word_count: number | null;
};

export const EMPTY_GENERATE_DEFAULTS: GenerateDefaults = {
  use_knowledge_base: false,
  use_competitor_research: false,
  use_multi_agent: false,
  use_images: false,
  use_dzen: false,
  use_detectors: false,
  use_humanizer: false,
  use_summary: false,
  word_count: null,
};

export function loadGenerateDefaults(): GenerateDefaults {
  try {
    // Values saved before defaults became per-project apply until overwritten.
    const raw =
      localStorage.getItem(projectKey()) ?? localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return EMPTY_GENERATE_DEFAULTS;
    }
    const parsed = JSON.parse(raw) as Partial<GenerateDefaults>;
    return { ...EMPTY_GENERATE_DEFAULTS, ...parsed };
  } catch {
    return EMPTY_GENERATE_DEFAULTS;
  }
}

export function saveGenerateDefaults(value: GenerateDefaults): void {
  localStorage.setItem(projectKey(), JSON.stringify(value));
}
