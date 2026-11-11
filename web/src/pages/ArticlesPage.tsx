import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { fetchArticles } from "../api/articles";
import { currentProjectId } from "../api/client";
import type { ArticleStatus, ReviewStatus } from "../api/types";
import { isArticleBusy } from "../hooks/useArticlesInProgress";

const REVIEW_LABEL: Record<ReviewStatus, string> = {
  pending: "на ревью",
  approved: "принято",
  rejected: "отклонено",
};

const STATUS_LABEL: Record<ArticleStatus, string> = {
  pending: "ожидает",
  processing: "в работе",
  completed: "готово",
  failed: "ошибка",
};

export function ArticlesPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<ArticleStatus | "">("");
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus | "">("");
  const articles = useQuery({
    queryKey: ["articles", status, reviewStatus, currentProjectId()],
    queryFn: () => fetchArticles({ status, reviewStatus }),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((item) => isArticleBusy(item.status)) ? 2000 : false;
    },
  });

  return (
    <Stack spacing={2}>
      <Typography variant="h4" component="h1">
        Статьи
      </Typography>
      <Stack direction="row" spacing={2} sx={{ flexWrap: "wrap" }}>
      <FormControl sx={{ minWidth: 180, flexShrink: 0 }} size="small">
        <InputLabel id="article-status-label">Статус</InputLabel>
        <Select
          labelId="article-status-label"
          label="Статус"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value as ArticleStatus | "");
          }}
        >
          <MenuItem value="">Все</MenuItem>
          <MenuItem value="completed">Готово</MenuItem>
          <MenuItem value="failed">Ошибка</MenuItem>
          <MenuItem value="processing">В работе</MenuItem>
          <MenuItem value="pending">Ожидает</MenuItem>
        </Select>
      </FormControl>
      <FormControl sx={{ minWidth: 180, flexShrink: 0 }} size="small">
        <InputLabel id="review-status-label">Ревью</InputLabel>
        <Select
          labelId="review-status-label"
          label="Ревью"
          value={reviewStatus}
          onChange={(event) => {
            setReviewStatus(event.target.value as ReviewStatus | "");
          }}
        >
          <MenuItem value="">Все</MenuItem>
          <MenuItem value="pending">На ревью</MenuItem>
          <MenuItem value="approved">Принято</MenuItem>
          <MenuItem value="rejected">Отклонено</MenuItem>
        </Select>
      </FormControl>
      </Stack>
      {articles.isPending ? <CircularProgress /> : null}
      {articles.isError ? (
        <Alert severity="error">
          {articles.error instanceof Error
            ? articles.error.message
            : "Не удалось загрузить статьи"}
        </Alert>
      ) : null}
      {articles.data && articles.data.total === 0 ? (
        <Alert severity="info">
          Статей ещё нет. Их можно написать на экране «Генерация».
        </Alert>
      ) : null}
      {articles.data && articles.data.total > 0 ? (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Тема</TableCell>
              <TableCell>Заголовок</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>Ревью</TableCell>
              <TableCell align="right">Слова</TableCell>
              <TableCell>Создана</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {articles.data.items.map((item) => {
              const busy = isArticleBusy(item.status);
              return (
              <TableRow
                key={item.id}
                hover
                sx={{
                  cursor: "pointer",
                  ...(busy
                    ? {
                        color: "text.secondary",
                        animation: "acf-busy-pulse 1.6s ease-in-out infinite",
                        "@keyframes acf-busy-pulse": {
                          "0%, 100%": { opacity: 0.45 },
                          "50%": { opacity: 1 },
                        },
                      }
                    : null),
                }}
                onClick={() => {
                  void navigate(`/articles/${item.id}`);
                }}
              >
                <TableCell>{item.topic}</TableCell>
                <TableCell>{item.title || "—"}</TableCell>
                <TableCell>
                  <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                    {busy ? (
                      <CircularProgress size={14} thickness={5} aria-label="в работе" />
                    ) : null}
                    <span>{STATUS_LABEL[item.status]}</span>
                  </Stack>
                </TableCell>
                <TableCell>{REVIEW_LABEL[item.review_status]}</TableCell>
                <TableCell align="right">{item.word_count}</TableCell>
                <TableCell>
                  {new Date(item.created_at).toLocaleString("ru-RU")}
                </TableCell>
              </TableRow>
              );
            })}
          </TableBody>
        </Table>
      ) : null}
    </Stack>
  );
}
