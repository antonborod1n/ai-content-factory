const STATUS_LABELS: Record<string, string> = {
  pending: "ожидает",
  processing: "в работе",
  running: "в работе",
  completed: "готово",
  ready: "готово",
  failed: "ошибка",
  ok: "работает",
  error: "ошибка",
  approved: "принято",
  rejected: "отклонено",
  needs_revision: "нужна правка",
  warning: "замечание",
};

const REVIEW_LABELS: Record<string, string> = {
  pending: "на ревью",
  approved: "принято",
  rejected: "отклонено",
};

/** Russian label for a backend status; unknown values are shown as is. */
export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

/** Russian label for an article review status. */
export function reviewLabel(status: string): string {
  return REVIEW_LABELS[status] ?? status;
}
