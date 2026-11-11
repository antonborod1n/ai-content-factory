import { apiGet } from "./client";

export type RunStatus = "running" | "completed" | "failed" | "skipped";

export type RunStep = {
  id: string;
  step: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  error: string | null;
  detail_json: Record<string, unknown> | null;
  attempt: number;
};

export type RunRecord = {
  id: string;
  project_id: string;
  task_type: string;
  status: string;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown> | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  steps: RunStep[];
};

export type RunListResponse = {
  items: RunRecord[];
  total: number;
};

export function fetchRuns(): Promise<RunListResponse> {
  return apiGet<RunListResponse>("/api/v1/runs");
}
