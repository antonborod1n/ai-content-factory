import { currentProjectId } from "./api/client";

/** Map markdown image paths like ``images/cover.png`` to the API media URL. */
export function articleMediaUrl(
  articleId: string,
  src: string | undefined,
): string | undefined {
  if (!src) {
    return src;
  }
  if (
    src.startsWith("http://") ||
    src.startsWith("https://") ||
    src.startsWith("data:") ||
    src.startsWith("blob:")
  ) {
    return src;
  }
  const relative = src.replace(/^\.\//, "").replace(/^\/+/, "");
  if (!relative.startsWith("images/")) {
    return src;
  }
  const project = currentProjectId();
  const query = project ? `?project=${encodeURIComponent(project)}` : "";
  return `/api/v1/articles/${articleId}/media/${relative}${query}`;
}
