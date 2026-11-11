import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";

import { fetchHealth } from "../api/health";
import { RunHistory } from "../components/RunHistory";
import { statusLabel } from "../statusLabels";

export function HomePage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
  });

  return (
    <Stack
      spacing={2}
      sx={{
        height: "calc(100vh - 48px)",
        maxHeight: "calc(100vh - 48px)",
        overflow: "hidden",
      }}
    >
      <Typography variant="h4" component="h1">
        Панель оператора
      </Typography>
      <Typography color="text.secondary">
        Состояние сервиса и история запусков текущего проекта. Ключи
        провайдеров хранятся только на сервере.
      </Typography>
      {health.isPending ? <CircularProgress size={24} /> : null}
      {health.isError ? (
        <Alert severity="error">
          API недоступен. Поднимите Compose (`make up`) и откройте панель
          через Vite на порту 15173.
        </Alert>
      ) : null}
      {health.data ? (
        <Stack direction="row" spacing={1}>
          <Chip
            label={`приложение: ${statusLabel(health.data.status)}`}
            color={health.data.status === "ok" ? "success" : "warning"}
          />
          <Chip
            label={`база: ${statusLabel(health.data.database)}`}
            color={health.data.database === "ok" ? "success" : "error"}
          />
        </Stack>
      ) : null}
      <Box sx={{ flex: 1, minHeight: 0, overflowY: "auto", pr: 0.5 }}>
        <RunHistory />
      </Box>
    </Stack>
  );
}
