import { apiGet, apiPatchJson, apiPostJson } from "./client";
import type {
  ArticleDetail,
  ArticleListResponse,
  ArticleStatus,
  ReviewStatus,
} from "./types";

export function fetchArticles(options?: {
  status?: ArticleStatus | "";
  reviewStatus?: ReviewStatus | "";
  limit?: number;
  offset?: number;
}): Promise<ArticleListResponse> {
  const params = new URLSearchParams();
  if (options?.status) {
    params.set("status", options.status);
  }
  if (options?.reviewStatus) {
    params.set("review_status", options.reviewStatus);
  }
  if (options?.limit != null) {
    params.set("limit", String(options.limit));
  }
  if (options?.offset != null) {
    params.set("offset", String(options.offset));
  }
  const query = params.toString();
  return apiGet<ArticleListResponse>(
    `/api/v1/articles${query ? `?${query}` : ""}`,
  );
}

export function fetchArticle(articleId: string): Promise<ArticleDetail> {
  return apiGet<ArticleDetail>(`/api/v1/articles/${articleId}`);
}

export type GenerateArticleInput = {
  topic: string;
  language: string;
  audience: string;
  keywords: string[];
  use_knowledge_base: boolean;
  use_competitor_research: boolean;
  use_multi_agent: boolean;
  use_images: boolean;
  use_internal_links: boolean;
  use_dzen: boolean;
  use_detectors: boolean;
  use_humanizer: boolean;
  use_summary: boolean;
};

export type TopicBrief = GenerateArticleInput & Record<string, unknown>;

export function fetchTopicBriefs(): Promise<TopicBrief[]> {
  return apiGet<TopicBrief[]>("/api/v1/topics");
}

export function generateArticle(
  input: object,
  projectId?: string,
): Promise<ArticleDetail> {
  return apiPostJson<ArticleDetail>("/api/v1/articles/generate", input, projectId);
}

export function setReview(
  articleId: string,
  reviewStatus: ReviewStatus,
): Promise<ArticleDetail> {
  return apiPatchJson<ArticleDetail>(`/api/v1/articles/${articleId}/review`, {
    review_status: reviewStatus,
  });
}

export function regenerateImages(articleId: string): Promise<ArticleDetail> {
  return apiPostJson<ArticleDetail>(`/api/v1/articles/${articleId}/images`, {});
}
