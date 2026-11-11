import { useSyncExternalStore } from "react";

export type GenerationKind = "articles" | "topics";

const active: Record<GenerationKind, number> = { articles: 0, topics: 0 };
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) {
    listener();
  }
}

/** Keep the sidebar spinner on until this generation finishes. */
export function trackGeneration<T>(
  work: Promise<T>,
  kind: GenerationKind = "articles",
): Promise<T> {
  active[kind] += 1;
  emit();
  return work.finally(() => {
    active[kind] = Math.max(0, active[kind] - 1);
    emit();
  });
}

export function useGenerationActive(kind: GenerationKind = "articles"): boolean {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => active[kind] > 0,
  );
}
