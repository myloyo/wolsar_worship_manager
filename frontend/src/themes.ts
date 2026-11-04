import { theme as antdTheme, type ThemeConfig } from "antd";

export const themeStorageKey = "wolsar.interface-theme";
export const palettes = {
  light: {
    name: "Светлая",
    dark: false,
    page: "#F5F5F3",
    surface: "#FFFFFF",
    raised: "#F8F8F6",
    text: "#222222",
    muted: "#737373",
    line: "#E7E7E3",
    accent: "#37A69F",
    onAccent: "#102F2D",
    soft: "#E7F4F1",
    heading: "#D84B2C",
    sidebar: "#222222",
    sidebarText: "#FFFFFF",
    sidebarMuted: "#A6A6A6",
  },
  dark: {
    name: "Тёмная",
    dark: true,
    page: "#191919",
    surface: "#222222",
    raised: "#2C2C2C",
    text: "#FFFFFF",
    muted: "#A6A6A6",
    line: "#3C3C3C",
    accent: "#37A69F",
    onAccent: "#0A2321",
    soft: "#253D3A",
    heading: "#F86846",
    sidebar: "#222222",
    sidebarText: "#FFFFFF",
    sidebarMuted: "#A6A6A6",
  },
  mint: {
    name: "Мята",
    dark: false,
    page: "#EDF5F2",
    surface: "#FFFFFF",
    raised: "#F1F7F4",
    text: "#183330",
    muted: "#657C75",
    line: "#D7E6DF",
    accent: "#37A69F",
    onAccent: "#102F2D",
    soft: "#DFF0EA",
    heading: "#D84B2C",
    sidebar: "#183330",
    sidebarText: "#FFFFFF",
    sidebarMuted: "#A8C2B8",
  },
  indigo: {
    name: "Индиго",
    dark: false,
    page: "#F0F2FC",
    surface: "#FFFFFF",
    raised: "#F3F5FC",
    text: "#20263C",
    muted: "#6E7790",
    line: "#DEE2F0",
    accent: "#3554D2",
    onAccent: "#FFFFFF",
    soft: "#E8EDFF",
    heading: "#D84B2C",
    sidebar: "#20263C",
    sidebarText: "#FFFFFF",
    sidebarMuted: "#ADB5D1",
  },
  plum: {
    name: "Слива",
    dark: true,
    page: "#201B22",
    surface: "#2C2430",
    raised: "#352C39",
    text: "#FFFFFF",
    muted: "#BDAFC2",
    line: "#4A3B50",
    accent: "#F5CE85",
    onAccent: "#241A27",
    soft: "#46364A",
    heading: "#F5CE85",
    sidebar: "#222222",
    sidebarText: "#FFFFFF",
    sidebarMuted: "#B7A5BD",
  },
} as const;
export type ThemeId = keyof typeof palettes;
export const themeIds = Object.keys(palettes) as ThemeId[];
export function isThemeId(value: string | null): value is ThemeId {
  return value !== null && Object.hasOwn(palettes, value);
}
export function initialTheme(): ThemeId {
  try {
    const saved = localStorage.getItem(themeStorageKey);
    if (isThemeId(saved)) return saved;
  } catch {}
  return typeof matchMedia === "function" &&
    matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}
export function themeConfig(id: ThemeId): ThemeConfig {
  const p = palettes[id];
  return {
    algorithm: p.dark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: p.accent,
      colorText: p.text,
      colorTextSecondary: p.muted,
      colorTextLightSolid: p.onAccent,
      colorBgBase: p.surface,
      colorBgContainer: p.surface,
      colorBgLayout: p.page,
      colorBgElevated: p.raised,
      colorBorder: p.line,
      colorBorderSecondary: p.line,
      colorInfo: p.accent,
      colorSuccess: "#37A69F",
      colorWarning: "#F5CE85",
      colorError: p.dark ? "#FF9E87" : "#B33E25",
      colorLink: p.text,
      fontFamily: "Stolzl, Arial, sans-serif",
      borderRadius: 12,
      fontSize: 13,
      controlHeight: 40,
    },
    components: {
      Button: { primaryShadow: "none", defaultShadow: "none", fontWeight: 500 },
      Table: {
        headerBg: p.raised,
        headerColor: p.muted,
        borderColor: p.line,
        rowHoverBg: p.soft,
      },
      Tabs: {
        itemSelectedColor: p.text,
        itemColor: p.muted,
        inkBarColor: p.accent,
      },
      Tag: { defaultBg: p.raised, defaultColor: p.text },
      Input: { activeBorderColor: p.accent },
      Modal: { borderRadiusLG: 16 },
    },
  };
}
