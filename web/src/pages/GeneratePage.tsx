import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import CircularProgress from "@mui/material/CircularProgress";
import FormControlLabel from "@mui/material/FormControlLabel";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";

import { fetchTopicBriefs, generateArticle, type TopicBrief } from "../api/articles";
import { ApiError, currentProjectId } from "../api/client";
import { LanguageSelect } from "../components/LanguageSelect";
import { trackGeneration } from "../generationActivity";
import { loadGenerateDefaults } from "../generateDefaults";

const FLAGS = [
  {
    name: "use_knowledge_base",
    label: "База знаний",
    hint: "В текст попадут фрагменты документов, загруженных в этот проект.",
  },
  {
    name: "use_competitor_research",
    label: "Конкуренты / SEO",
    hint: "По этой теме снимается топ выдачи, статья пишется по структуре этих страниц.",
  },
  {
    name: "use_multi_agent",
    label: "Мультиагенты",
    hint: "После черновика его правят SEO-агент, проверка фактов и редактор.",
  },
  {
    name: "use_images",
    label: "Картинки",
    hint: "Обложка и фото разделов заменяют метки в тексте.",
  },
  {
    name: "use_dzen",
    label: "Дзен",
    hint: "Дополнительно пишется короткая версия той же статьи: обложка и два фото в тексте.",
  },
  {
    name: "use_detectors",
    label: "Детекторы",
    hint: "После текста считаются свои оценки. Их видно на карточке статьи.",
  },
  {
    name: "use_humanizer",
    label: "Хьюманайзер",
    hint: "Текст переписывается ещё раз. Если детекторы включены, правка учитывает их оценки.",
  },
  {
    name: "use_summary",
    label: "Краткое содержание",
    hint: "В конце считается короткий пересказ готовой статьи.",
  },
] as const;

type FlagName = (typeof FLAGS)[number]["name"];
type FlagValues = Record<FlagName, boolean>;
type GenerateMode = "plan" | "single";
type PlanListFilter = "all" | "picked";

const FLAG_MINUTES: Record<FlagName, number> = {
  use_knowledge_base: 1,
  use_competitor_research: 3,
  use_multi_agent: 4,
  use_images: 3,
  use_dzen: 2,
  use_detectors: 1,
  use_humanizer: 2,
  use_summary: 1,
};

function hoursPhrase(hours: number): string {
  const mod10 = hours % 10;
  const mod100 = hours % 100;
  const word = mod10 === 1 && mod100 !== 11 ? "часа" : "часов";
  return `около ${hours} ${word}`;
}

/** Rough wait for the operator. The server keeps writing after a browser timeout. */
function estimateMinutes(flags: FlagValues, count = 1): string {
  const extra = FLAGS.reduce(
    (sum, flag) => sum + (flags[flag.name] ? FLAG_MINUTES[flag.name] : 0),
    0,
  );
  const total = (4 + extra) * Math.max(count, 1);
  if (total < 8) {
    return "около 5 минут";
  }
  if (total >= 90) {
    return hoursPhrase(Math.max(1, Math.round(total / 60)));
  }
  return `около ${total} минут`;
}

function sharedFlags(items: TopicBrief[]): FlagValues {
  const flags = {} as FlagValues;
  for (const flag of FLAGS) {
    flags[flag.name] =
      items.length > 0 && items.every((item) => item[flag.name] === true);
  }
  return flags;
}

function FlagSwitches({
  value,
  disabled,
  onChange,
}: {
  value: FlagValues;
  disabled?: boolean;
  onChange: (name: FlagName, checked: boolean) => void;
}) {
  return (
    <Stack>
      {FLAGS.map(({ name, label, hint }) => (
        <FormControlLabel
          key={name}
          sx={{ alignItems: "center", mr: 0 }}
          control={
            <Checkbox
              checked={value[name]}
              disabled={disabled}
              onChange={(event) => {
                onChange(name, event.target.checked);
              }}
            />
          }
          label={
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <span>{label}</span>
              <Typography
                component="span"
                sx={{ color: "text.secondary", fontSize: "12px", lineHeight: 1 }}
              >
                {hint}
              </Typography>
            </span>
          }
        />
      ))}
    </Stack>
  );
}

export function GeneratePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<GenerateMode>("single");
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  const [language, setLanguage] = useState("ru");
  const [keywords, setKeywords] = useState("");
  const savedDefaults = loadGenerateDefaults();
  const [flags, setFlags] = useState<Record<FlagName, boolean>>({
    use_knowledge_base: savedDefaults.use_knowledge_base,
    use_competitor_research: savedDefaults.use_competitor_research,
    use_multi_agent: savedDefaults.use_multi_agent,
    use_images: savedDefaults.use_images,
    use_dzen: savedDefaults.use_dzen,
    use_detectors: savedDefaults.use_detectors,
    use_humanizer: savedDefaults.use_humanizer,
    use_summary: savedDefaults.use_summary,
  });
  const [wordCount] = useState(savedDefaults.word_count);
  const [batchIndex, setBatchIndex] = useState(0);
  const [batchTotal, setBatchTotal] = useState(0);
  const [batchNote, setBatchNote] = useState("");
  const [skippedTopics, setSkippedTopics] = useState<{
    key: string;
    indexes: ReadonlySet<number>;
  }>({ key: "", indexes: new Set() });
  const [planView, setPlanView] = useState<{
    key: string;
    listFilter: PlanListFilter;
    search: string;
  }>({ key: "", listFilter: "all", search: "" });
  const [planFlagDraft, setPlanFlagDraft] = useState<{
    key: string;
    flags: FlagValues;
  } | null>(null);
  const stopBatch = useRef(false);

  const briefs = useQuery({
    queryKey: ["topic-briefs", currentProjectId()],
    queryFn: fetchTopicBriefs,
    enabled: mode === "plan",
  });

  function refreshArticleLists() {
    void queryClient.invalidateQueries({ queryKey: ["articles"] });
  }

  const generate = useMutation({
    mutationFn: async () => {
      const trimmed = topic.trim();
      if (!trimmed) {
        throw new Error("Укажите тему статьи.");
      }
      return trackGeneration(
        generateArticle({
          topic: trimmed,
          language,
          audience: audience.trim() || "general",
          keywords: keywords
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
          ...flags,
          use_internal_links: false,
          ...(wordCount ? { word_count: wordCount } : {}),
        }),
      );
    },
    onMutate: () => {
      // Row appears as pending/processing shortly after the request starts.
      window.setTimeout(refreshArticleLists, 1500);
    },
    onSuccess: async (article) => {
      refreshArticleLists();
      void navigate(`/articles/${article.id}`);
    },
    onSettled: () => {
      refreshArticleLists();
    },
  });

  const batch = useMutation({
    mutationFn: (queue: TopicBrief[]) =>
      trackGeneration((async () => {
      stopBatch.current = false;
      // Switching projects mid-batch must not move the remaining topics.
      const projectId = currentProjectId();
      setBatchTotal(queue.length);
      setBatchNote("");
      const failures: string[] = [];
      let written = 0;
      for (let index = 0; index < queue.length; index += 1) {
        if (stopBatch.current) {
          break;
        }
        const brief = queue[index];
        setBatchIndex(index + 1);
        try {
          await generateArticle(brief, projectId);
          written += 1;
          refreshArticleLists();
        } catch (error) {
          if (error instanceof ApiError && error.status === 0) {
            failures.push(
              `${brief.topic}: запрос оборвался, сервер может дописывать статью. Смотрите список «Статьи».`,
            );
            refreshArticleLists();
            continue;
          }
          const message = error instanceof Error ? error.message : "ошибка";
          failures.push(`${brief.topic}: ${message}`);
        }
      }
      refreshArticleLists();
      return {
        written,
        failures,
        stopped: stopBatch.current,
        total: queue.length,
      };
    })()),
    onMutate: () => {
      window.setTimeout(refreshArticleLists, 1500);
    },
    onSuccess: (result) => {
      const stopped = result.stopped ? " Очередь остановлена." : "";
      const failed =
        result.failures.length > 0
          ? ` Ошибки: ${result.failures.length}.`
          : "";
      setBatchNote(
        `Готово статей: ${result.written} из ${result.total}.${failed}${stopped}`,
      );
    },
  });

  const queue = briefs.data ?? [];
  const topicKey = `${currentProjectId()}\n${queue.map((item) => item.topic).join("\u0000")}`;
  const skipped =
    skippedTopics.key === topicKey ? skippedTopics.indexes : new Set<number>();
  const listFilter = planView.key === topicKey ? planView.listFilter : "all";
  const search = planView.key === topicKey ? planView.search : "";
  const fileFlags = sharedFlags(queue);
  const planFlags =
    planFlagDraft?.key === topicKey ? planFlagDraft.flags : fileFlags;

  function setPlanFlag(name: FlagName, checked: boolean) {
    setPlanFlagDraft({
      key: topicKey,
      flags: { ...planFlags, [name]: checked },
    });
  }

  function isPicked(index: number) {
    return !skipped.has(index);
  }

  const needle = search.trim().toLowerCase();
  const visible = queue.flatMap((brief, index) => {
    if (listFilter === "picked" && !isPicked(index)) {
      return [];
    }
    if (needle && !brief.topic.toLowerCase().includes(needle)) {
      return [];
    }
    return [{ brief, index }];
  });
  const visiblePicked = visible.filter((item) => isPicked(item.index)).length;
  const allVisible = visible.length > 0 && visiblePicked === visible.length;
  const selected = queue.filter((_, index) => isPicked(index));

  function rememberSkip(indexes: ReadonlySet<number>) {
    setSkippedTopics({ key: topicKey, indexes });
  }

  function toggleIndex(index: number) {
    const next = new Set(skipped);
    if (next.has(index)) {
      next.delete(index);
    } else {
      next.add(index);
    }
    rememberSkip(next);
  }

  function markVisible(checked: boolean) {
    const next = new Set(skipped);
    for (const item of visible) {
      if (checked) {
        next.delete(item.index);
      } else {
        next.add(item.index);
      }
    }
    rememberSkip(next);
  }

  return (
    <Stack spacing={2}>
      <Typography variant="h4" component="h1">
        Генерация
      </Typography>
      <Typography color="text.secondary">
        Одна статья пишется несколько минут. Пакет из контент-плана идёт по
        очереди, тема за темой. Если вкладка оборвёт ожидание, сервер всё
        равно дописывает статью — статус виден в «Статьях».
      </Typography>
      <ToggleButtonGroup
        exclusive
        value={mode}
        onChange={(_event, value: GenerateMode | null) => {
          if (value && !batch.isPending) {
            setMode(value);
          }
        }}
      >
        <ToggleButton value="single">Одна статья</ToggleButton>
        <ToggleButton value="plan">Контент-план</ToggleButton>
      </ToggleButtonGroup>

      {mode === "plan" ? (
        <Stack spacing={2}>
          <Alert severity="info">
            Список берётся из файла тем этого проекта. Переключатели ниже
            задают опции для выбранных тем в этом запуске.
          </Alert>
          {briefs.isPending ? <CircularProgress size={22} /> : null}
          {briefs.isError ? (
            <Alert severity="error">
              {briefs.error instanceof Error
                ? briefs.error.message
                : "Не удалось прочитать список тем"}
            </Alert>
          ) : null}
          {briefs.data && queue.length === 0 ? (
            <Alert severity="info">
              В файле тем пусто. Сначала соберите список на экране{" "}
              <RouterLink to="/topics">Темы</RouterLink>.
            </Alert>
          ) : null}
          {queue.length > 0 ? (
            <>
              <Typography>
                Выбрано {selected.length} из {queue.length}. Ориентир ожидания:{" "}
                {estimateMinutes(planFlags, selected.length)}. Повторный запуск
                напишет выбранные статьи ещё раз.
              </Typography>
              <FlagSwitches
                value={planFlags}
                disabled={batch.isPending}
                onChange={setPlanFlag}
              />
              <Stack
                direction={{ xs: "column", sm: "row" }}
                spacing={1}
                sx={{ alignItems: { sm: "center" } }}
              >
                <ToggleButtonGroup
                  exclusive
                  size="small"
                  value={listFilter}
                  onChange={(_event, value: PlanListFilter | null) => {
                    if (value) {
                      setPlanView({ key: topicKey, listFilter: value, search });
                    }
                  }}
                >
                  <ToggleButton value="all">Все</ToggleButton>
                  <ToggleButton value="picked">Выбранные</ToggleButton>
                </ToggleButtonGroup>
                <TextField
                  size="small"
                  label="Найти тему"
                  value={search}
                  onChange={(event) => {
                    setPlanView({
                      key: topicKey,
                      listFilter,
                      search: event.target.value,
                    });
                  }}
                  sx={{ flex: 1 }}
                />
              </Stack>
              <FormControlLabel
                sx={{ mr: 0 }}
                control={
                  <Checkbox
                    checked={allVisible}
                    indeterminate={visiblePicked > 0 && !allVisible}
                    disabled={batch.isPending || visible.length === 0}
                    onChange={(event) => {
                      markVisible(event.target.checked);
                    }}
                  />
                }
                label={needle ? "Отметить найденные" : "Отметить все"}
              />
              {visible.length === 0 ? (
                <Typography color="text.secondary">
                  {listFilter === "picked" && !needle
                    ? "Ничего не выбрано."
                    : "Ничего не найдено."}
                </Typography>
              ) : (
                <List
                  dense
                  sx={{
                    maxHeight: 420,
                    overflow: "auto",
                    border: 1,
                    borderColor: "divider",
                    borderRadius: 1,
                  }}
                >
                  {visible.map(({ brief, index }) => (
                    <ListItemButton
                      key={`${brief.topic}-${index}`}
                      dense
                      disabled={batch.isPending}
                      onClick={() => {
                        toggleIndex(index);
                      }}
                    >
                      <Checkbox
                        edge="start"
                        checked={isPicked(index)}
                        tabIndex={-1}
                        disableRipple
                        disabled={batch.isPending}
                      />
                      <ListItemText primary={brief.topic} />
                    </ListItemButton>
                  ))}
                </List>
              )}
              <Stack direction="row" spacing={1}>
                <Button
                  variant="contained"
                  disabled={batch.isPending || selected.length === 0}
                  onClick={() => {
                    batch.mutate(
                      selected.map((brief) => ({ ...brief, ...planFlags })),
                    );
                  }}
                >
                  {selected.length === queue.length
                    ? "Сгенерировать все"
                    : `Сгенерировать выбранные (${selected.length})`}
                </Button>
                {batch.isPending ? (
                  <Button
                    variant="outlined"
                    onClick={() => {
                      stopBatch.current = true;
                    }}
                  >
                    Остановить
                  </Button>
                ) : null}
              </Stack>
            </>
          ) : null}
          {batch.isPending ? (
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <CircularProgress size={22} />
              <Typography>
                Пишу {batchIndex} из {batchTotal}. Не закрывайте вкладку.
              </Typography>
            </Stack>
          ) : null}
          {batchNote ? <Alert severity="info">{batchNote}</Alert> : null}
          {batch.error instanceof Error ? (
            <Alert severity="error">{batch.error.message}</Alert>
          ) : null}
        </Stack>
      ) : (
        <Stack
          spacing={2}
          component="form"
          onSubmit={(event) => {
            event.preventDefault();
            generate.mutate();
          }}
        >
          <Alert severity="info">
            «Конкуренты / SEO» разбирает топ статей по уже выбранной теме.
            Список тем собирается раньше, на экране «Темы».
          </Alert>
          <TextField
            label="Тема"
            value={topic}
            required
            onChange={(event) => {
              setTopic(event.target.value);
            }}
          />
          <TextField
            label="Аудитория"
            value={audience}
            onChange={(event) => {
              setAudience(event.target.value);
            }}
          />
          <LanguageSelect value={language} onChange={setLanguage} />
          <TextField
            label="Ключевые слова"
            helperText="Через запятую"
            value={keywords}
            onChange={(event) => {
              setKeywords(event.target.value);
            }}
          />
          <FlagSwitches
            value={flags}
            disabled={generate.isPending}
            onChange={(name, checked) => {
              setFlags((current) => ({ ...current, [name]: checked }));
            }}
          />
          <Typography color="text.secondary">
            Ориентир ожидания: {estimateMinutes(flags)}.
          </Typography>
          <Button type="submit" variant="contained" disabled={generate.isPending}>
            Сгенерировать
          </Button>
          {generate.isPending ? (
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <CircularProgress size={22} />
              <Typography>Пишу статью. Не закрывайте вкладку.</Typography>
            </Stack>
          ) : null}
          {generate.error instanceof ApiError && generate.error.status === 0 ? (
            <Alert severity="warning">
              Ожидание оборвалось. Сервер может ещё писать статью — откройте{" "}
              <RouterLink to="/articles">Статьи</RouterLink>.
            </Alert>
          ) : generate.error instanceof Error ? (
            <Alert severity="error">{generate.error.message}</Alert>
          ) : null}
        </Stack>
      )}
    </Stack>
  );
}
