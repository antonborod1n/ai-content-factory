import { apiGet, apiPostForm, apiPostJson } from "./client";

export type TopicBriefRow = {
  topic: string;
  keywords: string;
  goal: string;
};

export type TopicPlanResult = {
  kind: "discovery" | "competitor";
  id: string;
  status: string;
  topics: TopicBriefRow[];
};

export type TopicExportResult = {
  path: string;
  added: number;
  skipped: number;
};

type BriefPayload = {
  topic?: string;
  primary_keywords?: string[];
  article_goal?: string;
};

type PlanTopic = {
  brief?: BriefPayload;
};

type PlanResponse = {
  id: string;
  status: string;
  topics?: PlanTopic[];
};

type PlanListResponse = {
  items: PlanResponse[];
  total: number;
};

function rowsFromPlan(plan: PlanResponse): TopicBriefRow[] {
  return (plan.topics ?? []).map((item) => ({
    topic: item.brief?.topic ?? "",
    keywords: (item.brief?.primary_keywords ?? []).join(", "),
    goal: item.brief?.article_goal ?? "",
  }));
}

function toPlanResult(
  kind: TopicPlanResult["kind"],
  plan: PlanResponse,
): TopicPlanResult {
  return {
    kind,
    id: plan.id,
    status: plan.status,
    topics: rowsFromPlan(plan),
  };
}

/** Latest saved plan that still has topics. Null when this project has none. */
export async function fetchLatestTopicPlan(
  kind: TopicPlanResult["kind"],
): Promise<TopicPlanResult | null> {
  const path =
    kind === "discovery"
      ? "/api/v1/discovery?limit=20"
      : "/api/v1/competitor-topics?limit=20";
  const list = await apiGet<PlanListResponse>(path);
  const found = list.items.find(
    (item) => item.status === "completed" && (item.topics?.length ?? 0) > 0,
  );
  return found ? toPlanResult(kind, found) : null;
}

export async function runDiscovery(input: {
  seeds: string[];
  niche: string;
  audience: string;
  language: string;
}): Promise<TopicPlanResult> {
  const plan = await apiPostJson<PlanResponse>("/api/v1/discovery", {
    seeds: input.seeds,
    niche: input.niche,
    audience: input.audience || "general",
    language: input.language || "ru",
  });
  return toPlanResult("discovery", plan);
}

export async function uploadCompetitorDumps(input: {
  files: File[];
  domain: string;
  niche: string;
  audience: string;
  language: string;
}): Promise<TopicPlanResult> {
  const body = new FormData();
  for (const file of input.files) {
    body.append("files", file);
  }
  body.append("domain", input.domain);
  body.append("niche", input.niche);
  body.append("audience", input.audience);
  body.append("language", input.language || "ru");
  const plan = await apiPostForm<PlanResponse>(
    "/api/v1/competitor-topics/sources",
    body,
  );
  return toPlanResult("competitor", plan);
}

export async function uploadCompetitorPlan(file: File): Promise<TopicPlanResult> {
  const body = new FormData();
  body.append("file", file);
  const plan = await apiPostForm<PlanResponse>(
    "/api/v1/competitor-topics/upload",
    body,
  );
  return toPlanResult("competitor", plan);
}

export function exportTopicPlan(
  plan: Pick<TopicPlanResult, "kind" | "id">,
): Promise<TopicExportResult> {
  const prefix =
    plan.kind === "discovery"
      ? "/api/v1/discovery"
      : "/api/v1/competitor-topics";
  return apiPostJson<TopicExportResult>(`${prefix}/${plan.id}/export`, {});
}
