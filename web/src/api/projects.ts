import { apiDelete, apiGet, apiPostJson } from "./client";

export type Project = {
  id: string;
  slug: string;
  name: string;
  domain: string | null;
  language: string;
  created_at: string;
};

export function fetchProjects(): Promise<Project[]> {
  return apiGet<Project[]>("/api/v1/projects");
}

export function deleteProject(projectId: string): Promise<void> {
  return apiDelete(`/api/v1/projects/${projectId}`);
}

export function createProject(body: {
  name: string;
  slug: string;
  language: "ru" | "en";
}): Promise<Project> {
  return apiPostJson<Project>("/api/v1/projects", body);
}
