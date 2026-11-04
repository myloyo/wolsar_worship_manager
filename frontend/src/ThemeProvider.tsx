import {
  createContext,
  useContext,
  useLayoutEffect,
  useState,
  type ReactNode,
} from "react";
import { ConfigProvider } from "antd";
import ruRU from "antd/locale/ru_RU";
import {
  initialTheme,
  isThemeId,
  palettes,
  themeConfig,
  themeStorageKey,
  type ThemeId,
} from "./themes";

const ThemeContext = createContext<{
  id: ThemeId;
  setTheme: (id: ThemeId) => void;
} | null>(null);
export function useInterfaceTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("ThemeProvider is required");
  return context;
}
export default function ThemeProvider({ children }: { children: ReactNode }) {
  const [id, setId] = useState<ThemeId>(initialTheme);
  const setTheme = (next: ThemeId) => {
    setId(next);
    try {
      localStorage.setItem(themeStorageKey, next);
    } catch {}
  };
  useLayoutEffect(() => {
    const p = palettes[id];
    document.documentElement.dataset.theme = id;
    document.documentElement.style.colorScheme = p.dark ? "dark" : "light";
    for (const [key, value] of Object.entries(p)) {
      if (typeof value === "string")
        document.documentElement.style.setProperty("--" + key, value);
    }
    const listener = (event: StorageEvent) => {
      if (event.key === themeStorageKey && isThemeId(event.newValue))
        setId(event.newValue);
    };
    window.addEventListener("storage", listener);
    return () => window.removeEventListener("storage", listener);
  }, [id]);
  return (
    <ThemeContext.Provider value={{ id, setTheme }}>
      <ConfigProvider locale={ruRU} theme={themeConfig(id)}>
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}
