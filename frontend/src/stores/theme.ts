import { create } from "zustand";

export type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "hike.theme"; // also read by public/theme-init.js before first paint

function readPreference(): ThemePreference {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function systemDark(): boolean {
  return (
    typeof window !== "undefined" && !!window.matchMedia?.("(prefers-color-scheme: dark)").matches
  );
}

function apply(pref: ThemePreference) {
  const dark = pref === "dark" || (pref === "system" && systemDark());
  document.documentElement.classList.toggle("dark", dark);
  return dark;
}

interface ThemeState {
  preference: ThemePreference;
  dark: boolean;
  setPreference: (pref: ThemePreference) => void;
  toggle: () => void;
}

const initial = readPreference();

export const useTheme = create<ThemeState>((set, get) => ({
  preference: initial,
  dark: typeof document !== "undefined" ? apply(initial) : false,
  setPreference: (preference) => {
    try {
      localStorage.setItem(STORAGE_KEY, preference);
    } catch {
      /* storage unavailable: the choice lasts for this tab only */
    }
    set({ preference, dark: apply(preference) });
  },
  toggle: () => get().setPreference(get().dark ? "light" : "dark"),
}));

// Follow the OS setting while the preference is "system".
if (typeof window !== "undefined" && window.matchMedia) {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => {
    const { preference } = useTheme.getState();
    if (preference === "system") useTheme.setState({ dark: apply("system") });
  });
}
