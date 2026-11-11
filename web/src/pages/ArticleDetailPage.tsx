import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import Markdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import { useParams } from "react-router-dom";

import { fetchArticle, regenerateImages, setReview } from "../api/articles";
import type { ReviewStatus } from "../api/types";
import { ApiError, currentProjectId } from "../api/client";
import { articleMediaUrl, safeMarkdownHref } from "../articleMedia";
import { trackGeneration } from "../generationActivity";
import { isArticleBusy } from "../hooks/useArticlesInProgress";
import { reviewLabel, statusLabel } from "../statusLabels";

type ArticleView = "article" | "dzen";

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  return value as Record<string, unknown>;
}

function ArticleMarkdown({
  articleId,
  markdown,
}: {
  articleId: string;
  markdown: string;
}) {
  return (
    <Box
      sx={{
        "& h1, & h2, & h3": { mt: 2, mb: 1 },
        "& p": { mb: 1.5 },
        "& img": { maxWidth: "100%", height: "auto", display: "block", my: 2 },
      }}
    >
      <Markdown
        rehypePlugins={[rehypeSanitize]}
        components={{
          img: ({ src, alt }) => {
            const media = articleMediaUrl(articleId, src);
            return media ? <img src={media} alt={alt ?? ""} /> : null;
          },
          a: ({ href, children }) => {
            const safe = safeMarkdownHref(href);
            return safe ? <a href={safe}>{children}</a> : <>{children}</>;
          },
        }}
      >
        {markdown}
      </Markdown>
    </Box>
  );
}

export function ArticleDetailPage() {
  const { articleId } = useParams();
  const queryClient = useQueryClient();
  const [viewState, setViewState] = useState<{
    id: string | undefined;
    view: ArticleView;
  }>({ id: articleId, view: "article" });
  const view = viewState.id === articleId ? viewState.view : "article";
  const review = useMutation({
    mutationFn: (reviewStatus: ReviewStatus) =>
      setReview(articleId ?? "", reviewStatus),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["article", articleId] });
      await queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
  });
  const images = useMutation({
    mutationFn: () => trackGeneration(regenerateImages(articleId ?? "")),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["article", articleId] });
    },
  });
  const article = useQuery({
    queryKey: ["article", articleId, currentProjectId()],
    queryFn: () => fetchArticle(articleId ?? ""),
    enabled: Boolean(articleId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && isArticleBusy(status) ? 3000 : false;
    },
  });

  if (article.isPending) {
    return <CircularProgress />;
  }
  if (article.isError) {
    const notFound =
      article.error instanceof ApiError && article.error.status === 404;
    return (
      <Alert severity={notFound ? "warning" : "error"}>
        {notFound
          ? "Статья не найдена"
          : article.error instanceof Error
            ? article.error.message
            : "Не удалось загрузить статью"}
      </Alert>
    );
  }
  if (!article.data) {
    return null;
  }

  const data = article.data;
  const quality = asRecord(data.quality);
  const detectors = asRecord(quality?.detectors);
  const summary = asRecord(quality?.summary);
  const dzen = asRecord(data.dzen);
  const dzenMarkdown =
    typeof dzen?.content_markdown === "string" ? dzen.content_markdown : "";
  const dzenTitle = typeof dzen?.title === "string" ? dzen.title : "";
  const dzenStatus = typeof dzen?.status === "string" ? dzen.status : "";
  const dzenChars =
    typeof dzen?.char_count === "number" ? dzen.char_count : null;
  return (
    <Stack spacing={2}>
      <Typography variant="h4" component="h1">
        {data.title || "Без заголовка"}
      </Typography>
      <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }} useFlexGap>
        <Chip label={statusLabel(data.status)} size="small" />
        <Chip label={`ревью: ${reviewLabel(data.review_status)}`} size="small" />
        <Chip label={`${data.word_count} слов`} size="small" variant="outlined" />
        {data.url_slug ? (
          <Chip label={data.url_slug} size="small" variant="outlined" />
        ) : null}
      </Stack>
      {data.meta_description ? (
        <Typography color="text.secondary">{data.meta_description}</Typography>
      ) : null}
      {detectors ? (
        <Alert severity="info">
          Детектор: AI {String(detectors.ai_likelihood ?? "—")}, уникальность{" "}
          {String(detectors.uniqueness ?? "—")}, вердикт{" "}
          {statusLabel(String(detectors.verdict ?? "—"))}
        </Alert>
      ) : null}
      {typeof summary?.text === "string" && summary.text ? (
        <Alert severity="success" icon={false}>
          <Typography variant="subtitle2">Краткое содержание</Typography>
          <Typography variant="body2">{summary.text}</Typography>
        </Alert>
      ) : null}
      <Stack direction="row" spacing={1}>
        <Button
          variant="contained"
          disabled={review.isPending}
          onClick={() => {
            review.mutate("approved");
          }}
        >
          Принять
        </Button>
        <Button
          variant="outlined"
          color="warning"
          disabled={review.isPending}
          onClick={() => {
            review.mutate("rejected");
          }}
        >
          Отклонить
        </Button>
        <Button
          variant="text"
          disabled={review.isPending}
          onClick={() => {
            review.mutate("pending");
          }}
        >
          Сбросить ревью
        </Button>
      </Stack>
      {review.error instanceof Error ? (
        <Alert severity="error">{review.error.message}</Alert>
      ) : null}
      <Button
        variant="outlined"
        disabled={images.isPending || !data.content_markdown}
        onClick={() => {
          images.mutate();
        }}
      >
        Обновить картинки
      </Button>
      {images.isPending ? (
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <CircularProgress size={16} thickness={5} />
          <Typography>Генерирую картинки. Текст статьи не меняется.</Typography>
        </Stack>
      ) : null}
      {images.error instanceof Error ? (
        <Alert severity="error">{images.error.message}</Alert>
      ) : null}
      <Tabs
        value={view}
        onChange={(_event, value: ArticleView) => {
          setViewState({ id: articleId, view: value });
        }}
      >
        <Tab value="article" label="Статья" />
        <Tab value="dzen" label="Дзен" />
      </Tabs>
      {view === "article" ? (
        data.content_markdown ? (
          <ArticleMarkdown articleId={data.id} markdown={data.content_markdown} />
        ) : (
          <Alert severity="info">У этой записи ещё нет текста.</Alert>
        )
      ) : dzenMarkdown ? (
        <Stack spacing={1}>
          <Typography variant="h5" component="h2">
            Статья для Дзена
          </Typography>
          {dzenTitle ? (
            <Typography variant="h6" component="p">
              {dzenTitle}
            </Typography>
          ) : null}
          {dzenChars !== null ? (
            <Typography color="text.secondary">{dzenChars} символов</Typography>
          ) : null}
          <ArticleMarkdown articleId={data.id} markdown={dzenMarkdown} />
        </Stack>
      ) : (
        <Alert severity="info">
          {dzenStatus === "failed"
            ? "Версия для Дзена не записалась."
            : "Для этой статьи версии Дзена нет."}
        </Alert>
      )}
    </Stack>
  );
}
