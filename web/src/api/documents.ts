import { apiDelete, apiGet, apiPostForm, apiPostJson } from "./client";

export type KnowledgeDocument = {
  id: string;
  title: string;
  source: string;
  content_type: string;
  status: string;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
};

export type DocumentSearchHit = {
  chunk_id: string;
  document_id: string;
  document_title: string;
  content: string;
  score: number;
};

export function fetchDocuments(): Promise<{
  items: KnowledgeDocument[];
  total: number;
}> {
  return apiGet("/api/v1/documents");
}

export function uploadDocument(file: File, title: string): Promise<KnowledgeDocument> {
  const body = new FormData();
  body.append("file", file);
  body.append("title", title);
  return apiPostForm<KnowledgeDocument>("/api/v1/documents/upload", body);
}

export function searchDocuments(query: string): Promise<{
  query: string;
  chunks: DocumentSearchHit[];
}> {
  return apiPostJson("/api/v1/documents/search", { query });
}

export function deleteDocument(documentId: string): Promise<void> {
  return apiDelete(`/api/v1/documents/${documentId}`);
}
