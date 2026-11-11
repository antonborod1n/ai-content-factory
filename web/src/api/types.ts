export type ArticleStatus = "pending" | "processing" | "completed" | "failed";

export type ReviewStatus = "pending" | "approved" | "rejected";

export type HealthResponse = {
  status: string;
  database: string;
};

export type ArticleListItem = {
  id: string;
  status: ArticleStatus;
  topic: string;
  title: string;
  url_slug: string | null;
  language: string;
  word_count: number;
  review_status: ReviewStatus;
  created_at: string;
  updated_at: string;
};

export type ArticleListResponse = {
  items: ArticleListItem[];
  total: number;
};

export type ArticleDetail = {
  id: string;
  status: ArticleStatus;
  title: string;
  meta_description: string;
  url_slug: string | null;
  content_markdown: string;
  word_count: number;
  pipeline: unknown;
  assets: unknown;
  internal_links: unknown;
  dzen: unknown;
  quality: unknown;
  competitor_sources: unknown;
  review_status: ReviewStatus;
};
