import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { ApiError, currentProjectId, setCurrentProjectId } from "../api/client";
import { deleteProject, fetchProjects, type Project } from "../api/projects";
import {
  fetchPrompt,
  fetchPrompts,
  fetchRuntimeStatus,
  updateProject,
} from "../api/settings";
import { LanguageSelect } from "../components/LanguageSelect";
import {
  loadGenerateDefaults,
  saveGenerateDefaults,
  type GenerateDefaults,
} from "../generateDefaults";

const DEFAULT_FLAGS: { key: keyof GenerateDefaults; label: string }[] = [
  { key: "use_knowledge_base", label: "База знаний" },
  { key: "use_competitor_research", label: "Конкуренты / SEO" },
  { key: "use_multi_agent", label: "Мультиагенты" },
  { key: "use_images", label: "Картинки" },
  { key: "use_dzen", label: "Дзен" },
  { key: "use_detectors", label: "Детекторы" },
  { key: "use_humanizer", label: "Хьюманайзер" },
  { key: "use_summary", label: "Краткое содержание" },
];

function yesNo(value: boolean): string {
  return value ? "включено" : "нет";
}

function ConnectionGroup({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <Stack spacing={0.5}>
      <Typography variant="subtitle1">{title}</Typography>
      {children}
    </Stack>
  );
}

function ConnectionRow({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
      <Stack
        direction="row"
        spacing={0.5}
        sx={{ width: 240, alignItems: "center", flexShrink: 0 }}
      >
        <Typography sx={{ color: "text.secondary", fontSize: "14px" }}>{label}</Typography>
        <Tooltip title={hint} arrow>
          <IconButton size="small" aria-label={hint} sx={{ p: 0.25 }}>
            <InfoOutlinedIcon sx={{ fontSize: 16, color: "text.secondary" }} />
          </IconButton>
        </Tooltip>
      </Stack>
      <Typography sx={{ fontSize: "14px" }}>{value}</Typography>
    </Stack>
  );
}

export function SettingsPage() {
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  const runtime = useQuery({ queryKey: ["runtime"], queryFn: fetchRuntimeStatus });
  const prompts = useQuery({ queryKey: ["prompts"], queryFn: fetchPrompts });
  const projectRows = projects.data ?? [];
  const [editingId, setEditingId] = useState(currentProjectId);
  const [pendingDeleteId, setPendingDeleteId] = useState("");
  const project =
    projectRows.find((item) => item.id === editingId) ??
    projectRows.find((item) => item.slug === "default");

  const [name, setName] = useState(project?.name ?? "");
  const [domain, setDomain] = useState(project?.domain ?? "");
  const [language, setLanguage] = useState<"ru" | "en">(
    project?.language === "en" ? "en" : "ru",
  );
  const [defaults, setDefaults] = useState<GenerateDefaults>(loadGenerateDefaults);
  const [defaultsSaved, setDefaultsSaved] = useState(false);
  const [selectedPrompt, setSelectedPrompt] = useState("");
  const [tab, setTab] = useState("connections");

  function openProject(item: Project) {
    setEditingId(item.id);
    setName(item.name);
    setDomain(item.domain ?? "");
    setLanguage(item.language === "en" ? "en" : "ru");
  }

  const promptText = useQuery({
    queryKey: ["prompt", selectedPrompt],
    queryFn: () => fetchPrompt(selectedPrompt),
    enabled: Boolean(selectedPrompt),
  });

  const removeProject = useMutation({
    mutationFn: (item: Project) => deleteProject(item.id),
    onSuccess: (_result, item) => {
      setPendingDeleteId("");
      const remaining = (projects.data ?? []).filter((row) => row.id !== item.id);
      queryClient.setQueryData(["projects"], remaining);
      const next = remaining[0];
      if (currentProjectId() === item.id) {
        setCurrentProjectId(next?.id ?? "");
      }
      if (editingId === item.id) {
        if (next) {
          openProject(next);
        } else {
          setEditingId("");
          setName("");
          setDomain("");
        }
      }
    },
  });

  const saveProject = useMutation({
    mutationFn: () => {
      if (!project) {
        throw new Error("Проект не выбран");
      }
      return updateProject(project.id, {
        name: name.trim(),
        domain: domain.trim() || null,
        language,
      });
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["projects"], (current: typeof projects.data) =>
        (current ?? []).map((item) => (item.id === updated.id ? updated : item)),
      );
    },
  });

  return (
    <Stack spacing={3}>
      <Typography variant="h4" component="h1">
        Настройки
      </Typography>
      <Tabs
        value={tab}
        onChange={(_event, value: string) => {
          setTab(value);
        }}
      >
        <Tab value="connections" label="Подключения" />
        <Tab value="project" label="Проект" />
        <Tab value="article" label="Одна статья" />
        <Tab value="prompts" label="Промпты" />
      </Tabs>

      {tab === "project" ? (
      <Stack spacing={2}>
      <Stack spacing={1}>
        <Typography variant="subtitle1">Проекты</Typography>
        {projectRows.map((item) => (
          <Stack key={item.id} direction="row" spacing={2} sx={{ alignItems: "center" }}>
            <Button
              size="small"
              variant={item.id === project?.id ? "contained" : "text"}
              onClick={() => {
                openProject(item);
              }}
              sx={{ width: 180, justifyContent: "flex-start" }}
            >
              {item.name}
            </Button>
            <Typography sx={{ width: 160, color: "text.secondary", fontSize: "14px" }}>
              {item.slug}
            </Typography>
            <Typography sx={{ width: 32, fontSize: "14px" }}>{item.language}</Typography>
            {item.slug === "default" ? (
              <Typography sx={{ color: "text.secondary", fontSize: "14px" }}>
                остаётся всегда
              </Typography>
            ) : (
              <Button
                size="small"
                color="error"
                onClick={() => {
                  setPendingDeleteId(item.id);
                }}
              >
                Удалить
              </Button>
            )}
          </Stack>
        ))}
        {pendingDeleteId ? (
          <Alert
            severity="warning"
            action={
              <Stack direction="row" spacing={1}>
                <Button
                  color="inherit"
                  size="small"
                  onClick={() => {
                    setPendingDeleteId("");
                  }}
                >
                  Отмена
                </Button>
                <Button
                  color="error"
                  size="small"
                  disabled={removeProject.isPending}
                  onClick={() => {
                    const item = projectRows.find((row) => row.id === pendingDeleteId);
                    if (item) {
                      removeProject.mutate(item);
                    }
                  }}
                >
                  Удалить
                </Button>
              </Stack>
            }
          >
            Удалить проект «{projectRows.find((row) => row.id === pendingDeleteId)?.name}»?
            Его статьи, база и темы тоже удалятся.
          </Alert>
        ) : null}
        {removeProject.error instanceof ApiError ? (
          <Alert severity="error">{removeProject.error.message}</Alert>
        ) : null}
      </Stack>
      <Stack spacing={1.5} component="form" onSubmit={(event) => {
        event.preventDefault();
        saveProject.mutate();
      }}>
        <TextField label="Название" value={name} required onChange={(event) => {
          setName(event.target.value);
        }} />
        <TextField
          label="Slug"
          value={project?.slug ?? ""}
          disabled
          helperText="Папка тем и статей от slug не меняется"
        />
        <TextField label="Домен" value={domain} onChange={(event) => {
          setDomain(event.target.value);
        }} />
        <LanguageSelect value={language} onChange={setLanguage} />
        <Button type="submit" variant="contained" disabled={saveProject.isPending || !project}>
          Сохранить проект
        </Button>
        {saveProject.isSuccess ? <Alert severity="success">Проект сохранён</Alert> : null}
        {saveProject.error instanceof Error ? (
          <Alert severity="error">{saveProject.error.message}</Alert>
        ) : null}
      </Stack>
      </Stack>
      ) : null}

      {tab === "article" ? (
      <Stack spacing={1}>
        <Typography variant="body2" color="text.secondary">
          Эти галочки и объём подставляются на экране «Генерация», режим «Одна статья», для текущего проекта.
        </Typography>
        {DEFAULT_FLAGS.map((item) => (
          <FormControlLabel
            key={item.key}
            control={
              <Checkbox
                checked={Boolean(defaults[item.key])}
                onChange={(event) => {
                  setDefaultsSaved(false);
                  setDefaults((current) => ({
                    ...current,
                    [item.key]: event.target.checked,
                  }));
                }}
              />
            }
            label={item.label}
          />
        ))}
        <TextField
          label="Объём, слов"
          type="number"
          value={defaults.word_count ?? ""}
          helperText={
            runtime.data
              ? `Если пусто, сервер целится в ${runtime.data.article_target_word_count}`
              : "Если пусто, берётся объём сервера"
          }
          onChange={(event) => {
            setDefaultsSaved(false);
            const next = event.target.value.trim();
            setDefaults((current) => ({
              ...current,
              word_count: next ? Number(next) : null,
            }));
          }}
        />
        <Button
          variant="contained"
          onClick={() => {
            saveGenerateDefaults(defaults);
            setDefaultsSaved(true);
          }}
        >
          Сохранить значения
        </Button>
        {defaultsSaved ? <Alert severity="success">Значения сохранены для текущего проекта в этом браузере</Alert> : null}
      </Stack>
      ) : null}

      {tab === "connections" ? (
      <Stack spacing={1}>
        {runtime.isError ? (
          <Alert severity="error">Не удалось прочитать статус</Alert>
        ) : null}
        {runtime.data ? (
          <Stack spacing={2}>
            <ConnectionGroup title="Основные">
              <ConnectionRow
                label="OpenAI"
                hint="Ключ и модель для текста статей. Сам ключ здесь не показывается."
                value={`${yesNo(runtime.data.openai_configured)}, модель ${runtime.data.openai_model}`}
              />
              <ConnectionRow
                label="Поиск"
                hint="Ключ выдачи Google. Без него не работают разбор конкурентов и поиск тем по выдаче."
                value={yesNo(runtime.data.serp_configured)}
              />
              <ConnectionRow
                label="Яндекс"
                hint="Ключ выдачи Яндекса для поиска тем. «Нет» значит ключ не задан."
                value={yesNo(runtime.data.yandex_configured)}
              />
              <ConnectionRow
                label="Картинки"
                hint="Разрешена ли генерация изображений и какая модель её делает."
                value={`${yesNo(runtime.data.images_enabled)}, модель ${runtime.data.image_model}`}
              />
              <ConnectionRow
                label="Поиск тем"
                hint="Разрешён ли поиск новых тем по запросам. Переключается в .env."
                value={yesNo(runtime.data.discovery_enabled)}
              />
            </ConnectionGroup>
            <ConnectionGroup title="Модель">
              <ConnectionRow
                label="Свой адрес API"
                hint="Задан ли отдельный адрес API модели. Сам адрес не показывается."
                value={yesNo(runtime.data.openai_base_url_configured)}
              />
              <ConnectionRow
                label="Температура"
                hint="Насколько свободны ответы. Ниже — стабильнее, выше — разнообразнее."
                value={String(runtime.data.openai_temperature)}
              />
              <ConnectionRow
                label="Лимит токенов"
                hint="Максимальная длина одного ответа модели."
                value={runtime.data.openai_max_tokens == null ? "нет" : String(runtime.data.openai_max_tokens)}
              />
              <ConnectionRow
                label="Эмбеддинги"
                hint="Модель, которая превращает документы базы знаний в векторы."
                value={runtime.data.embedding_model}
              />
              <ConnectionRow
                label="Размер вектора"
                hint="Длина вектора эмбеддинга. Должна совпадать с выбранной моделью."
                value={String(runtime.data.embedding_dimensions)}
              />
            </ConnectionGroup>
            <ConnectionGroup title="База знаний">
              <ConnectionRow
                label="Поиск по базе"
                hint="Можно ли подмешивать фрагменты базы знаний в статью."
                value={yesNo(runtime.data.rag_enabled)}
              />
              <ConnectionRow
                label="Фрагментов в контекст"
                hint="Сколько подходящих фрагментов попадает в запрос к модели."
                value={String(runtime.data.rag_top_k)}
              />
              <ConnectionRow
                label="Размер фрагмента"
                hint="На сколько символов режется документ при загрузке в базу."
                value={String(runtime.data.rag_chunk_size)}
              />
              <ConnectionRow
                label="Перекрытие"
                hint="Сколько символов соседние фрагменты делят между собой."
                value={String(runtime.data.rag_chunk_overlap)}
              />
            </ConnectionGroup>
            <ConnectionGroup title="Поиск и темы">
              <ConnectionRow
                label="Провайдер"
                hint="Сервис, через который читается выдача Google."
                value={runtime.data.serp_provider}
              />
              <ConnectionRow
                label="Research"
                hint="Разрешён ли разбор статей конкурентов по уже выбранной теме."
                value={yesNo(runtime.data.research_enabled)}
              />
              <ConnectionRow
                label="Статей в топе"
                hint="Сколько статей конкурентов разбирается для плана."
                value={String(runtime.data.research_top_n)}
              />
              <ConnectionRow
                label="Строк выдачи"
                hint="Сколько результатов поиска забирается до отбора топа."
                value={String(runtime.data.research_search_n)}
              />
              <ConnectionRow
                label="Тем за прогон"
                hint="Сколько новых тем поиск по выдаче сохраняет за один запуск."
                value={String(runtime.data.discovery_max_topics)}
              />
              <ConnectionRow
                label="Запросов при поиске тем"
                hint="Сколько строк выдачи читается на один поисковый запрос."
                value={String(runtime.data.discovery_search_n)}
              />
              <ConnectionRow
                label="Провайдер Яндекса"
                hint="Сервис, через который читается выдача Яндекса."
                value={runtime.data.yandex_serp_provider}
              />
              <ConnectionRow
                label="Разбор выгрузок"
                hint="Разрешена ли сборка тем из файлов конкурентов."
                value={yesNo(runtime.data.competitor_topics_enabled)}
              />
              <ConnectionRow
                label="Тем из выгрузок"
                hint="Сколько тем можно получить из одной выгрузки."
                value={String(runtime.data.competitor_topics_max_topics)}
              />
            </ConnectionGroup>
            <ConnectionGroup title="Статья">
              <ConnectionRow
                label="Мультиагенты"
                hint="Разрешена ли цепочка SEO, проверки фактов и редактора."
                value={yesNo(runtime.data.multi_agent_enabled)}
              />
              <ConnectionRow
                label="Размер картинки"
                hint="Размер генерируемого изображения в пикселях."
                value={runtime.data.image_size}
              />
              <ConnectionRow
                label="Перелинковка"
                hint="Разрешены ли ссылки на другие готовые статьи этого проекта."
                value={yesNo(runtime.data.internal_links_enabled)}
              />
              <ConnectionRow
                label="Ссылок в статье"
                hint="Сколько внутренних ссылок можно вставить в одну статью."
                value={String(runtime.data.internal_link_max)}
              />
              <ConnectionRow
                label="Префикс ссылки"
                hint="Начало адреса внутренней ссылки."
                value={runtime.data.internal_link_prefix}
              />
              <ConnectionRow
                label="Дзен"
                hint="Разрешена ли короткая версия той же статьи для Дзена."
                value={yesNo(runtime.data.dzen_enabled)}
              />
              <ConnectionRow
                label="Дзен, символов"
                hint="Целевой объём версии для Дзена."
                value={String(runtime.data.dzen_target_char_count)}
              />
              <ConnectionRow
                label="Качество"
                hint="Разрешены ли детекторы, хьюманайзер и краткое содержание."
                value={yesNo(runtime.data.quality_enabled)}
              />
              <ConnectionRow
                label="Порог детектора"
                hint="С какой оценки «похоже на ИИ» статья помечается на проверку."
                value={String(runtime.data.detector_ai_review_threshold)}
              />
              <ConnectionRow
                label="Порог уникальности"
                hint="Ниже этой оценки уникальность считается слабой."
                value={String(runtime.data.detector_uniqueness_floor)}
              />
              <ConnectionRow
                label="Краткое, символов"
                hint="Целевой объём краткого содержания."
                value={String(runtime.data.summary_target_char_count)}
              />
            </ConnectionGroup>
            <ConnectionGroup title="Среда">
              <ConnectionRow
                label="Окружение"
                hint="Режим сервера: local, test или production."
                value={runtime.data.app_env}
              />
              <ConnectionRow
                label="Папка статей"
                hint="Куда на сервере пишутся файлы готовых статей."
                value={runtime.data.articles_output_dir || "выключена"}
              />
              <ConnectionRow
                label="Цель, слов"
                hint="На какой объём целится генерация, если в статье объём не задан."
                value={String(runtime.data.article_target_word_count)}
              />
              <ConnectionRow
                label="Минимум от цели"
                hint="Доля цели, после которой дописывание останавливается."
                value={String(runtime.data.article_min_word_ratio)}
              />
              <ConnectionRow
                label="Попыток дописать"
                hint="Сколько раз короткий черновик отправляется на расширение."
                value={String(runtime.data.article_expand_attempts)}
              />
            </ConnectionGroup>
          </Stack>
        ) : null}
      </Stack>
      ) : null}

      {tab === "prompts" ? (
      <Stack spacing={1}>
        <Typography variant="body2" color="text.secondary">
          Только просмотр. Текст промпта не меняется из интерфейса.
        </Typography>
        <List dense>
          {(prompts.data ?? []).map((item) => (
            <ListItemButton
              key={item.filename}
              selected={item.filename === selectedPrompt}
              onClick={() => {
                setSelectedPrompt(item.filename);
              }}
            >
              <ListItemText primary={item.filename} />
            </ListItemButton>
          ))}
        </List>
        {promptText.data ? (
          <Typography
            component="pre"
            sx={{
              whiteSpace: "pre-wrap",
              fontSize: "13px",
              bgcolor: "action.hover",
              p: 2,
              borderRadius: 1,
              maxHeight: 480,
              overflow: "auto",
            }}
          >
            {promptText.data.content}
          </Typography>
        ) : null}
      </Stack>
      ) : null}
    </Stack>
  );
}
