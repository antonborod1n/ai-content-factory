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
import Typography from "@mui/material/Typography";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { currentProjectId } from "../api/client";
import {
  deleteDocument,
  fetchDocuments,
  searchDocuments,
  uploadDocument,
  type DocumentSearchHit,
} from "../api/documents";
import { statusLabel } from "../statusLabels";

export function KnowledgePage() {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<DocumentSearchHit[] | null>(null);

  const documents = useQuery({
    queryKey: ["documents", currentProjectId()],
    queryFn: fetchDocuments,
  });

  const upload = useMutation({
    mutationFn: async () => {
      if (!file) {
        throw new Error("Выберите файл .md, .txt или .pdf.");
      }
      return uploadDocument(file, title);
    },
    onSuccess: async () => {
      setFile(null);
      setTitle("");
      setHits(null);
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const search = useMutation({
    mutationFn: async () => {
      const trimmed = query.trim();
      if (!trimmed) {
        throw new Error("Введите запрос для поиска.");
      }
      return searchDocuments(trimmed);
    },
    onSuccess: (result) => {
      setHits(result.chunks);
    },
  });

  const remove = useMutation({
    mutationFn: deleteDocument,
    onSuccess: async () => {
      setHits(null);
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const busy = upload.isPending || search.isPending || remove.isPending;
  const errorText =
    (upload.error instanceof Error ? upload.error.message : "") ||
    (search.error instanceof Error ? search.error.message : "") ||
    (remove.error instanceof Error ? remove.error.message : "") ||
    (documents.error instanceof Error ? documents.error.message : "");

  return (
    <Stack spacing={2}>
      <Typography variant="h4" component="h1">
        База знаний
      </Typography>
      <Typography color="text.secondary">
        Файлы .md, .txt и .pdf режутся на чанки и участвуют в generate, когда у
        темы включена база знаний.
      </Typography>

      <Stack
        spacing={2}
        component="form"
        onSubmit={(event) => {
          event.preventDefault();
          upload.mutate();
        }}
      >
        <Button variant="outlined" component="label" disabled={busy}>
          {file ? file.name : "Выбрать файл"}
          <input
            hidden
            type="file"
            accept=".md,.txt,.pdf,text/plain,text/markdown,application/pdf"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
            }}
          />
        </Button>
        <TextField
          label="Название"
          value={title}
          onChange={(event) => {
            setTitle(event.target.value);
          }}
        />
        <Button type="submit" variant="contained" disabled={busy}>
          Загрузить
        </Button>
      </Stack>

      <Stack
        direction="row"
        spacing={1}
        component="form"
        onSubmit={(event) => {
          event.preventDefault();
          search.mutate();
        }}
      >
        <TextField
          label="Поиск по базе"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
          }}
          fullWidth
        />
        <Button type="submit" variant="outlined" disabled={busy}>
          Найти
        </Button>
      </Stack>

      {busy ? <CircularProgress size={22} /> : null}
      {errorText ? <Alert severity="error">{errorText}</Alert> : null}

      {hits ? (
        hits.length === 0 ? (
          <Alert severity="info">Близких фрагментов нет.</Alert>
        ) : (
          <Stack spacing={1}>
            {hits.map((hit) => (
              <Alert key={hit.chunk_id} severity="success" icon={false}>
                <Typography variant="subtitle2">{hit.document_title}</Typography>
                <Typography variant="body2">{hit.content}</Typography>
              </Alert>
            ))}
          </Stack>
        )
      ) : null}

      {documents.isPending ? <CircularProgress size={22} /> : null}
      {documents.data && documents.data.total === 0 ? (
        <Alert severity="info">База пуста.</Alert>
      ) : null}
      {documents.data && documents.data.total > 0 ? (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Название</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell align="right">Чанки</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {documents.data.items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>{item.title || item.source}</TableCell>
                <TableCell>{statusLabel(item.status)}</TableCell>
                <TableCell align="right">{item.chunk_count}</TableCell>
                <TableCell align="right">
                  <Button
                    size="small"
                    color="error"
                    disabled={busy}
                    onClick={() => {
                      remove.mutate(item.id);
                    }}
                  >
                    Удалить
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
    </Stack>
  );
}
