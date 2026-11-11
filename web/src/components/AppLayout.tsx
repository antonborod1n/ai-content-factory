import ArticleIcon from "@mui/icons-material/Article";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import HomeIcon from "@mui/icons-material/Home";
import MenuBookIcon from "@mui/icons-material/MenuBook";
import SettingsIcon from "@mui/icons-material/Settings";
import TopicIcon from "@mui/icons-material/Topic";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import {
  currentProjectId,
  rememberProjectId,
  setCurrentProjectId,
} from "../api/client";
import { createProject, fetchProjects } from "../api/projects";
import { useGenerationActive } from "../generationActivity";
import { useArticlesInProgress } from "../hooks/useArticlesInProgress";
import { LanguageSelect } from "./LanguageSelect";

const DRAWER_WIDTH = 260;

const NAV = [
  { to: "/", label: "Обзор", icon: HomeIcon, end: true },
  { to: "/articles", label: "Статьи", icon: ArticleIcon, end: false },
  { to: "/topics", label: "Темы", icon: TopicIcon, end: false },
  { to: "/knowledge", label: "База знаний", icon: MenuBookIcon, end: false },
  { to: "/generate", label: "Генерация", icon: AutoAwesomeIcon, end: false },
] as const;

export function AppLayout() {
  const queryClient = useQueryClient();
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
  });
  const inProgress = useArticlesInProgress();
  const articlesBusy =
    useGenerationActive("articles") || (inProgress.data?.length ?? 0) > 0;
  const topicsBusy = useGenerationActive("topics");
  const [projectId, setProjectId] = useState(currentProjectId);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [language, setLanguage] = useState<"ru" | "en">("ru");
  const [createError, setCreateError] = useState("");

  useEffect(() => {
    function onProject(event: Event) {
      setProjectId((event as CustomEvent<string>).detail);
    }
    window.addEventListener("acf:project", onProject);
    return () => {
      window.removeEventListener("acf:project", onProject);
    };
  }, []);

  const rows = projects.data ?? [];
  const selected = rows.some((item) => item.id === projectId)
    ? projectId
    : (rows[0]?.id ?? "");
  if (selected && selected !== currentProjectId()) {
    rememberProjectId(selected);
  }

  function chooseProject(nextId: string) {
    setCurrentProjectId(nextId);
  }

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          "& .MuiDrawer-paper": {
            width: DRAWER_WIDTH,
            boxSizing: "border-box",
            display: "flex",
            flexDirection: "column",
          },
        }}
      >
        <Toolbar>
          <Typography variant="h6" component="div">
            Фабрика контента
          </Typography>
        </Toolbar>
        <Divider />
        <Stack spacing={1} sx={{ px: 2, py: 1.5 }}>
          <TextField
            select
            size="small"
            label="Проект"
            value={selected}
            disabled={rows.length === 0}
            onChange={(event) => {
              chooseProject(event.target.value);
            }}
          >
            {rows.map((item) => (
              <MenuItem key={item.id} value={item.id}>
                {item.name}
              </MenuItem>
            ))}
          </TextField>
          {creating ? (
            <Stack spacing={1} component="form" onSubmit={(event) => {
              event.preventDefault();
              setCreateError("");
              void createProject({ name, slug, language })
                .then((created) => {
                  queryClient.setQueryData(
                    ["projects"],
                    (current: typeof rows) => [...current.filter((item) => item.id !== created.id), created],
                  );
                  setName("");
                  setSlug("");
                  setCreating(false);
                  chooseProject(created.id);
                })
                .catch((error: unknown) => {
                  setCreateError(
                    error instanceof Error ? error.message : "Не удалось создать проект",
                  );
                });
            }}>
              <TextField
                size="small"
                label="Название"
                value={name}
                required
                onChange={(event) => {
                  setName(event.target.value);
                }}
              />
              <TextField
                size="small"
                label="Slug"
                placeholder="my-site"
                value={slug}
                required
                onChange={(event) => {
                  setSlug(event.target.value);
                }}
              />
              <LanguageSelect value={language} onChange={setLanguage} />
              {createError ? <Alert severity="error">{createError}</Alert> : null}
              <Button type="submit" size="small" variant="contained">
                Создать
              </Button>
            </Stack>
          ) : (
            <Button size="small" onClick={() => { setCreating(true); }}>
              Новый проект
            </Button>
          )}
        </Stack>
        <Divider />
        <List>
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <ListItemButton
                key={item.to}
                component={NavLink}
                to={item.to}
                end={item.end}
                sx={{
                  "&.active": {
                    bgcolor: "action.selected",
                  },
                }}
              >
                <ListItemIcon>
                  <Icon />
                </ListItemIcon>
                <ListItemText
                  primary={
                    (item.to === "/articles" && articlesBusy) ||
                    (item.to === "/topics" && topicsBusy) ? (
                      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                        <span>{item.label}</span>
                        <CircularProgress size={14} thickness={5} />
                      </Stack>
                    ) : (
                      item.label
                    )
                  }
                />
              </ListItemButton>
            );
          })}
        </List>
        <Box sx={{ flexGrow: 1 }} />
        <Divider />
        <List>
          <ListItemButton
            component={NavLink}
            to="/settings"
            sx={{
              "&.active": {
                bgcolor: "action.selected",
              },
            }}
          >
            <ListItemIcon>
              <SettingsIcon />
            </ListItemIcon>
            <ListItemText primary="Настройки" />
          </ListItemButton>
        </List>
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        {selected ? <Outlet key={selected} /> : null}
      </Box>
    </Box>
  );
}
