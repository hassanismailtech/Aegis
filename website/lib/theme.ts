export type Theme = "light" | "dark";

export const THEME_KEY = "seclume-theme";

export function readTheme(storage: Pick<Storage, "getItem">): Theme {
  try {
    return storage.getItem(THEME_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function applyTheme(root: Pick<HTMLElement, "classList">, storage: Pick<Storage, "setItem">, theme: Theme) {
  root.classList.toggle("dark", theme === "dark");
  try {
    storage.setItem(THEME_KEY, theme);
  } catch {
    // The current page still changes when browser storage is unavailable.
  }
}

export const themeBootstrap = `try{document.documentElement.classList.toggle('dark',localStorage.getItem('${THEME_KEY}')==='dark')}catch{}`;
