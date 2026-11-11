import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Link from "@mui/material/Link";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { Link as RouterLink } from "react-router-dom";

import { currentProjectId } from "../api/client";
import { fetchRuns, type RunRecord, type RunStep } from "../api/runs";

const TASK_LABEL: Record<string, string> = {
  article: "Статья",
  images: "Картинки",
  competitor: "Конкуренты",
  discovery: "Темы из выдачи",
  competitor_topics: "Файлы конкурентов",
  competitor_plan: "Контент-план",
  topics_export: "Экспорт тем",
  document: "База знаний",
  document_delete: "Удаление документа",
  review: "Ревью",
};

const STATUS_LABEL: Record<string, string> = {
  running: "идёт",
  completed: "готово",
  failed: "ошибка",
  skipped: "пропущен",
};

const STEP_LABEL: Record<string, string> = {
  research: "Исследование",
  knowledge: "База знаний",
  writer: "Текст",
  images: "Картинки",
  links: "Перелинковка",
  quality: "Качество",
  dzen: "Дзен",
  save: "Сохранение",
  search: "Поиск",
  fetch: "Страницы",
  outline: "Структура",
  seo: "SEO",
  fact_checker: "Проверка фактов",
  editor: "Редактор",
  snapshots: "Выдача",
  candidates: "Кандидаты",
  briefs: "Темы",
  parse: "Разбор файлов",
  analyze: "Анализ",
  embed: "Эмбеддинги",
};

const KIND_LABEL: Record<string, string> = {
  discovery: "поиск по выдаче",
  competitor: "файлы конкурентов",
  cover: "обложка",
  image: "фото",
  infographic: "схема",
  dzen: "Дзен",
};

const FIELD_LABEL: Record<string, string> = {
  id: "Идентификатор",
  started: "Начало",
  finished: "Конец",
  topic: "Тема",
  language: "Язык",
  audience: "Аудитория",
  keywords: "Ключевые слова",
  article_id: "Статья",
  research_id: "Исследование",
  use_multi_agent: "Мультиагент",
  use_competitor_research: "Разбор конкурентов",
  use_images: "Картинки",
  use_internal_links: "Перелинковка",
  use_dzen: "Дзен",
  use_detectors: "Детекторы",
  use_humanizer: "Хьюманайзер",
  use_summary: "Краткое содержание",
  top_n: "Сколько конкурентов взять",
  query: "Поисковый запрос",
  word_count: "Слов",
  words: "Слов",
  images: "Картинок готово",
  images_failed: "Картинок с ошибкой",
  dzen_images: "Картинок Дзена",
  links: "Внутренние ссылки",
  dzen: "Дзен",
  title: "Заголовок",
  url_slug: "Адрес",
  slug: "Адрес",
  ai_likelihood: "Похожесть на ИИ, %",
  uniqueness: "Уникальность, %",
  detector_verdict: "Вердикт детектора",
  competitors: "Конкурентов",
  outline: "Пунктов структуры",
  sections: "Разделов",
  goal: "Цель",
  results: "Результатов поиска",
  articles: "Подходящих статей",
  attached: "Контекст базы подключён",
  note: "Заметка",
  intent: "Интент",
  verdict: "Вердикт",
  issues: "Замечаний",
  completed: "Готово",
  failed: "Ошибок",
  slots: "Слоты картинок",
  count: "Количество",
  files: "Файлов",
  chars: "Символов",
  status: "Статус",
  detector: "Детектор",
  humanizer: "Хьюманайзер",
  humanizer_applied: "Текст переписан",
  summary_chars: "Символов в кратком содержании",
  kind: "Тип",
  placeholder: "Место",
  path: "Файл",
  seeds: "Запросы",
  niche: "Ниша",
  plan_id: "План",
  topics: "Тем",
  titles: "Темы",
  engines: "Поисковики",
  snapshots: "Снимков выдачи",
  candidates: "Кандидатов",
  added: "Добавлено в файл",
  skipped: "Уже были в файле",
  chunks: "Фрагментов",
  document_id: "Документ",
  domain: "Домен",
  source: "Источник",
  hits: "Строк в файлах",
  review_status: "Ревью",
};

function labelOf(map: Record<string, string>, value: string): string {
  return map[value] ?? value;
}

function formatWhen(value: string | null): string {
  if (!value) {
    return "—";
  }
  return new Date(value).toLocaleString("ru-RU", {
    dateStyle: "short",
    timeStyle: "medium",
  });
}

function formatDuration(ms: number | null): string {
  if (ms == null || Number.isNaN(ms)) {
    return "—";
  }
  const safe = Math.max(0, ms);
  if (safe < 1000) {
    return `${safe} мс`;
  }
  const seconds = Math.round(safe / 1000);
  if (seconds < 60) {
    return `${seconds} с`;
  }
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest === 0 ? `${minutes} мин` : `${minutes} мин ${rest} с`;
}

function stepDuration(step: RunStep): string {
  if (!step.finished_at) {
    return "—";
  }
  const ms =
    new Date(step.finished_at).getTime() - new Date(step.started_at).getTime();
  return formatDuration(ms);
}

function runSubject(run: RunRecord): string {
  const topic = run.input_json.topic;
  if (typeof topic === "string" && topic.trim()) {
    return topic;
  }
  const title = run.input_json.title;
  if (typeof title === "string" && title.trim()) {
    return title;
  }
  const seeds = run.input_json.seeds;
  if (Array.isArray(seeds) && seeds.length > 0) {
    return seeds.map((item) => String(item)).join(", ");
  }
  const niche = run.input_json.niche;
  if (typeof niche === "string" && niche.trim()) {
    return niche;
  }
  const domain = run.input_json.domain;
  if (typeof domain === "string" && domain.trim()) {
    return domain;
  }
  const articleId = run.input_json.article_id;
  if (typeof articleId === "string" && articleId) {
    return `статья ${articleId}`;
  }
  return run.id;
}

function articleIdOf(run: RunRecord): string | null {
  const sources = [run.output_json, run.input_json];
  for (const source of sources) {
    const value = source?.article_id;
    if (typeof value === "string" && value) {
      return value;
    }
  }
  return null;
}

function FieldValue({ name, value }: { name: string; value: unknown }) {
  if (typeof value === "boolean") {
    return <span>{value ? "да" : "нет"}</span>;
  }
  if (value == null || value === "") {
    return <span>—</span>;
  }
  if (name === "article_id" && typeof value === "string") {
    return (
      <Link component={RouterLink} to={`/articles/${value}`}>
        {value}
      </Link>
    );
  }
  if (name === "status" && typeof value === "string") {
    return <span>{labelOf(STATUS_LABEL, value)}</span>;
  }
  if (name === "kind" && typeof value === "string") {
    return <span>{labelOf(KIND_LABEL, value)}</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span>—</span>;
    }
    if (value.every((item) => item && typeof item === "object")) {
      return (
        <Stack spacing={0.5} sx={{ py: 0.5 }}>
          {value.map((item, index) => (
            <Box
              key={index}
              sx={{
                pl: 1,
                borderLeft: 2,
                borderColor: "divider",
              }}
            >
              <FactList data={item as Record<string, unknown>} />
            </Box>
          ))}
        </Stack>
      );
    }
    return <span>{value.map((item) => String(item)).join(", ")}</span>;
  }
  if (typeof value === "object") {
    return <FactList data={value as Record<string, unknown>} />;
  }
  return <span>{String(value)}</span>;
}

function FactList({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data);
  if (entries.length === 0) {
    return <span>—</span>;
  }
  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: "minmax(140px, 220px) 1fr",
        columnGap: 2,
        rowGap: 0.5,
        alignItems: "start",
      }}
    >
      {entries.map(([key, value]) => (
        <Box key={key} sx={{ display: "contents" }}>
          <Typography variant="body2" color="text.secondary">
            {labelOf(FIELD_LABEL, key)}
          </Typography>
          <Typography variant="body2" component="div">
            <FieldValue name={key} value={value} />
          </Typography>
        </Box>
      ))}
    </Box>
  );
}

function statusColor(
  status: string,
): "success" | "error" | "warning" | "default" {
  if (status === "completed") {
    return "success";
  }
  if (status === "failed") {
    return "error";
  }
  if (status === "running") {
    return "warning";
  }
  return "default";
}

function RunCard({ run }: { run: RunRecord }) {
  const busy = run.status === "running";
  const articleId = articleIdOf(run);
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        ...(busy
          ? {
              animation: "acf-busy-pulse 1.6s ease-in-out infinite",
              "@keyframes acf-busy-pulse": {
                "0%, 100%": { opacity: 0.55 },
                "50%": { opacity: 1 },
              },
            }
          : null),
      }}
    >
      <Stack spacing={1.5}>
        <Stack
          direction="row"
          spacing={1}
          sx={{ alignItems: "center", flexWrap: "wrap" }}
        >
          {busy ? <CircularProgress size={16} thickness={5} aria-label="идёт" /> : null}
          <Chip size="small" label={labelOf(TASK_LABEL, run.task_type)} />
          <Chip
            size="small"
            color={statusColor(run.status)}
            label={labelOf(STATUS_LABEL, run.status)}
          />
          <Typography variant="body2" color="text.secondary">
            {formatDuration(run.duration_ms)}
          </Typography>
        </Stack>
        <Typography variant="subtitle1">{runSubject(run)}</Typography>
        <FactList
          data={{
            id: run.id,
            started: formatWhen(run.started_at),
            finished: formatWhen(run.finished_at),
          }}
        />
        {articleId ? (
          <Link component={RouterLink} to={`/articles/${articleId}`}>
            Открыть статью
          </Link>
        ) : null}
        {run.error ? <Alert severity="error">{run.error}</Alert> : null}
        <Typography variant="subtitle2">Параметры</Typography>
        <FactList data={run.input_json} />
        <Typography variant="subtitle2">Результат</Typography>
        {run.output_json ? (
          <FactList data={run.output_json} />
        ) : (
          <Typography variant="body2" color="text.secondary">
            Результата ещё нет.
          </Typography>
        )}
        <Typography variant="subtitle2">Этапы</Typography>
        {run.steps.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Этапов пока нет.
          </Typography>
        ) : (
          <Stack spacing={1.5}>
            {run.steps.map((step, index) => (
              <Box key={step.id}>
                <Stack
                  direction="row"
                  spacing={1}
                  sx={{ alignItems: "center", flexWrap: "wrap" }}
                >
                  <Typography variant="body2">
                    {index + 1}. {labelOf(STEP_LABEL, step.step)}
                    {step.attempt > 1 ? `, попытка ${step.attempt}` : ""}
                  </Typography>
                  <Chip
                    size="small"
                    variant="outlined"
                    color={statusColor(step.status)}
                    label={labelOf(STATUS_LABEL, step.status)}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {formatWhen(step.started_at)} — {formatWhen(step.finished_at)} (
                    {stepDuration(step)})
                  </Typography>
                </Stack>
                {step.error ? (
                  <Typography variant="body2" color="error" sx={{ mt: 0.5 }}>
                    {step.error}
                  </Typography>
                ) : null}
                {step.detail_json ? (
                  <Box sx={{ mt: 0.5 }}>
                    <FactList data={step.detail_json} />
                  </Box>
                ) : null}
              </Box>
            ))}
          </Stack>
        )}
      </Stack>
    </Paper>
  );
}

export function RunHistory() {
  const runs = useQuery({
    queryKey: ["runs", currentProjectId()],
    queryFn: fetchRuns,
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((item) => item.status === "running") ? 2000 : 5000;
    },
  });

  return (
    <Stack spacing={1.5}>
      <Typography variant="h6" component="h2">
        История запусков
      </Typography>
      {runs.isPending ? <CircularProgress size={24} /> : null}
      {runs.isError ? (
        <Alert severity="error">
          {runs.error instanceof Error
            ? runs.error.message
            : "Не удалось загрузить историю"}
        </Alert>
      ) : null}
      {runs.data && runs.data.total === 0 ? (
        <Alert severity="info">
          Запусков ещё нет. Здесь появятся сбор тем, экспорт, база знаний,
          генерация и остальные действия этого проекта.
        </Alert>
      ) : null}
      {runs.data?.items.map((run) => (
        <RunCard key={run.id} run={run} />
      ))}
    </Stack>
  );
}
