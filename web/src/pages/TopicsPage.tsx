import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { currentProjectId } from "../api/client";
import { LanguageSelect } from "../components/LanguageSelect";
import { trackGeneration } from "../generationActivity";
import { statusLabel } from "../statusLabels";
import {
  exportTopicPlan,
  fetchLatestTopicPlan,
  runDiscovery,
  uploadCompetitorDumps,
  uploadCompetitorPlan,
} from "../api/topics";

type SourceMode = "discovery" | "competitor";
type CompetitorInput = "dumps" | "plan";

function splitSeeds(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function TopicsPage() {
  const [mode, setMode] = useState<SourceMode>("discovery");
  const [competitorInput, setCompetitorInput] = useState<CompetitorInput>("dumps");
  const [seeds, setSeeds] = useState("");
  const [niche, setNiche] = useState("");
  const [audience, setAudience] = useState("");
  const [language, setLanguage] = useState("ru");
  const [domain, setDomain] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [exportMessage, setExportMessage] = useState("");
  const projectId = currentProjectId();
  const queryClient = useQueryClient();
  const planKey = ["topic-plan", mode, projectId] as const;
  const saved = useQuery({
    queryKey: planKey,
    queryFn: () => fetchLatestTopicPlan(mode),
  });
  const plan = saved.data ?? null;
  const hasTopics = (plan?.topics.length ?? 0) > 0;

  const build = useMutation({
    mutationFn: () =>
      trackGeneration((async () => {
      setExportMessage("");
      if (mode === "discovery") {
        const parsed = splitSeeds(seeds);
        if (parsed.length === 0) {
          throw new Error("Укажите хотя бы одну тематику или запрос.");
        }
        return runDiscovery({
          seeds: parsed,
          niche,
          audience,
          language,
        });
      }
      if (files.length === 0) {
        throw new Error("Выберите файл конкурентов.");
      }
      if (competitorInput === "plan") {
        const jsonFile = files.find((file) =>
          file.name.toLowerCase().endsWith(".json"),
        );
        if (!jsonFile || files.length !== 1) {
          throw new Error("Для готового плана нужен один JSON-файл.");
        }
        return uploadCompetitorPlan(jsonFile);
      }
      return uploadCompetitorDumps({
        files,
        domain,
        niche,
        audience,
        language,
      });
    })(), "topics"),
    onSuccess: (result) => {
      queryClient.setQueryData(planKey, result);
    },
  });

  const exportPlan = useMutation({
    mutationFn: async () => {
      if (!plan) {
        throw new Error("Сначала соберите список тем.");
      }
      return exportTopicPlan(plan);
    },
    onSuccess: (result) => {
      setExportMessage(
        `В ${result.path} добавлено ${result.added}, пропущено ${result.skipped}. Статьи не генерировались.`,
      );
    },
  });

  const busy = build.isPending || exportPlan.isPending;
  const errorText =
    (build.error instanceof Error ? build.error.message : "") ||
    (exportPlan.error instanceof Error ? exportPlan.error.message : "");

  return (
    <Stack spacing={2}>
      <Typography variant="h4" component="h1">
        Темы
      </Typography>
      <Typography color="text.secondary">
        Здесь только список тем. Он сохраняется в текущем проекте и виден
        в истории на Обзоре. В файл для генерации список попадает кнопкой
        экспорта. Статья пишется позже. За один запуск работает один режим.
      </Typography>
      <ToggleButtonGroup
        exclusive
        value={mode}
        onChange={(_event, value: SourceMode | null) => {
          if (value) {
            setMode(value);
            setFiles([]);
            setExportMessage("");
            build.reset();
          }
        }}
      >
        <ToggleButton
          value="discovery"
          title="Есть направление, файлов конкурентов нет. Темы собираются из поисковой выдачи."
        >
          Только тематика
        </ToggleButton>
        <ToggleButton
          value="competitor"
          title="Темы или ключи уже лежат в файлах. Поиск по выдаче не запускается."
        >
          Файлы конкурентов
        </ToggleButton>
      </ToggleButtonGroup>
      <Alert severity="info">
        {mode === "discovery"
          ? "Поиск по выдаче: по запросам вроде «матрасы Минск» снимается выдача Google и, если есть ключ, Яндекса. Из неё собираются темы. Нужен ключ поиска в настройках сервера."
          : competitorInput === "plan"
            ? "Готовый план: JSON вроде content-plan уже содержит темы. Он сразу становится списком тем, без поиска и без нового разбора."
            : "Выгрузки: xlsx, csv или txt с ключами и темами конкурентов. По ним ищутся пробелы и собираются новые темы. Это не разбор топа статей по одной теме."}
      </Alert>

      {mode === "discovery" ? (
        <Stack spacing={2} component="form" onSubmit={(event) => {
          event.preventDefault();
          build.mutate();
        }}>
          <TextField
            label="Тематики и запросы"
            value={seeds}
            onChange={(event) => {
              setSeeds(event.target.value);
            }}
            multiline
            minRows={3}
            required
          />
          <Typography variant="body2" color="text.secondary">
            Через запятую или с новой строки. Например: матрасы Минск
          </Typography>
          <TextField
            label="Ниша"
            placeholder="например, товары для сна"
            value={niche}
            onChange={(event) => {
              setNiche(event.target.value);
            }}
          />
          <TextField
            label="Аудитория"
            placeholder="например, покупатели матрасов"
            value={audience}
            onChange={(event) => {
              setAudience(event.target.value);
            }}
          />
          <LanguageSelect value={language} onChange={setLanguage} />
          <Button type="submit" variant="contained" disabled={busy}>
            Собрать темы из выдачи
          </Button>
        </Stack>
      ) : (
        <Stack spacing={2} component="form" onSubmit={(event) => {
          event.preventDefault();
          build.mutate();
        }}>
          <ToggleButtonGroup
            exclusive
            size="small"
            value={competitorInput}
            onChange={(_event, value: CompetitorInput | null) => {
              if (value) {
                setCompetitorInput(value);
                setFiles([]);
              }
            }}
          >
            <ToggleButton
              value="dumps"
              title="Сырые таблицы и списки ключей. Их ещё нужно разобрать."
            >
              Выгрузки xlsx / csv / txt
            </ToggleButton>
            <ToggleButton
              value="plan"
              title="План уже собран. Импорт без поиска и без аналитика."
            >
              Готовый content-plan JSON
            </ToggleButton>
          </ToggleButtonGroup>
          <Button variant="outlined" component="label" disabled={busy}>
            {files.length > 0
              ? files.map((file) => file.name).join(", ")
              : "Выбрать файлы"}
            <input
              hidden
              type="file"
              multiple={competitorInput === "dumps"}
              accept={
                competitorInput === "plan"
                  ? ".json,application/json"
                  : ".xlsx,.csv,.txt,.json"
              }
              onChange={(event) => {
                setFiles(Array.from(event.target.files ?? []));
              }}
            />
          </Button>
          {competitorInput === "dumps" ? (
            <TextField
              label="Домен"
              value={domain}
              onChange={(event) => {
                setDomain(event.target.value);
              }}
            />
          ) : null}
          <TextField
            label="Ниша"
            placeholder="например, товары для сна"
            value={niche}
            onChange={(event) => {
              setNiche(event.target.value);
            }}
          />
          {competitorInput === "dumps" ? (
            <>
              <TextField
                label="Аудитория"
                placeholder="например, покупатели матрасов"
                value={audience}
                onChange={(event) => {
                  setAudience(event.target.value);
                }}
              />
              <LanguageSelect value={language} onChange={setLanguage} />
            </>
          ) : null}
          <Button type="submit" variant="contained" disabled={busy}>
            {competitorInput === "plan"
              ? "Импортировать план"
              : "Разобрать файлы конкурентов"}
          </Button>
        </Stack>
      )}

      {busy ? (
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <CircularProgress size={22} />
          <Typography>
            {exportPlan.isPending
              ? "Записываю темы в topics.json…"
              : "Собираю темы. Это может занять несколько минут."}
          </Typography>
        </Stack>
      ) : null}
      {errorText ? <Alert severity="error">{errorText}</Alert> : null}
      {exportMessage ? <Alert severity="success">{exportMessage}</Alert> : null}

      {hasTopics && plan ? (
        <Stack spacing={1}>
          <Typography>
            План {plan.id}: {plan.topics.length} тем, статус: {statusLabel(plan.status)}
          </Typography>
          <Button
            variant="outlined"
            disabled={busy}
            onClick={() => {
              exportPlan.mutate();
            }}
          >
            Экспорт в topics.json
          </Button>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Тема</TableCell>
                <TableCell>Ключи</TableCell>
                <TableCell>Цель</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {plan.topics.map((row, index) => (
                <TableRow key={`${row.topic}-${index}`}>
                  <TableCell>{row.topic}</TableCell>
                  <TableCell>{row.keywords || "—"}</TableCell>
                  <TableCell>{row.goal || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Stack>
      ) : null}
    </Stack>
  );
}
