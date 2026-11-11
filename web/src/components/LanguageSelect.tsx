import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import { useId } from "react";

type UiLanguage = "ru" | "en";

function asUiLanguage(value: string): UiLanguage {
  return value === "en" ? "en" : "ru";
}

export function LanguageSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (language: UiLanguage) => void;
}) {
  const labelId = useId();
  return (
    <FormControl fullWidth>
      <InputLabel id={labelId}>Язык</InputLabel>
      <Select
        labelId={labelId}
        label="Язык"
        value={asUiLanguage(value)}
        onChange={(event) => {
          onChange(asUiLanguage(event.target.value));
        }}
      >
        <MenuItem value="ru">ru</MenuItem>
        <MenuItem value="en">en</MenuItem>
      </Select>
    </FormControl>
  );
}
