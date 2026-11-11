import { useQuery } from "@tanstack/react-query";

import { fetchArticles } from "../api/articles";
import { currentProjectId } from "../api/client";
import type { ArticleStatus } from "../api/types";

export function isArticleBusy(status: ArticleStatus): boolean {
  return status === "processing" || status === "pending";
}

/** Articles that are still being generated. Polls while any are busy. */
export function useArticlesInProgress() {
  return useQuery({
    queryKey: ["articles", "in-progress", currentProjectId()],
    queryFn: async () => {
      const [processing, pending] = await Promise.all([
        fetchArticles({ status: "processing", limit: 100 }),
        fetchArticles({ status: "pending", limit: 100 }),
      ]);
      return [...processing.items, ...pending.items];
    },
    refetchInterval: (query) => ((query.state.data?.length ?? 0) > 0 ? 2000 : 5000),
  });
}
