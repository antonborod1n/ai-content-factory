import { currentProjectId } from "./api/client";

/** Map markdown image paths like ``images/cover.png`` to the API media URL.
 *
 * External, data, and blob URLs are dropped so model-written markdown cannot
 * load attacker-controlled images in the operator UI.
 */
export function articleMediaUrl(
  articleId: string,
  src: string | undefined,
): string | undefined {
  if (!src) {
    return undefined;
  }
  const relative = src.replace(/^\.\//, "").replace(/^\/+/, "");
  if (!relative.startsWith("images/") || relative.includes("..")) {
    return undefined;
  }
  const project = currentProjectId();
  const query = project ? `?project=${encodeURIComponent(project)}` : "";
  return `/api/v1/articles/${articleId}/media/${relative}${query}`;
}

/** Allow only http(s), in-app paths, and hash links in article markdown. */
export function safeMarkdownHref(href: string | undefined): string | undefined {
  if (!href) {
    return undefined;
  }
  const trimmed = href.trim();
  if (
    trimmed.startsWith("/") ||
    trimmed.startsWith("#") ||
    trimmed.startsWith("http://") ||
    trimmed.startsWith("https://")
  ) {
    return trimmed;
  }
  return undefined;
}
