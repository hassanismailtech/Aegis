"use client";

import { useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { applyTheme, readTheme } from "@/lib/theme";

function subscribe(notify: () => void) {
  function syncStorage() {
    try { document.documentElement.classList.toggle("dark", readTheme(window.localStorage) === "dark"); } catch { /* Browser storage may be blocked. */ }
    notify();
  }
  window.addEventListener("seclume-theme-change", notify);
  window.addEventListener("storage", syncStorage);
  return () => {
    window.removeEventListener("seclume-theme-change", notify);
    window.removeEventListener("storage", syncStorage);
  };
}

export function ThemeToggle() {
  const dark = useSyncExternalStore(subscribe, () => document.documentElement.classList.contains("dark"), () => false);
  function toggle() {
    let storage: Pick<Storage, "setItem">;
    try { storage = window.localStorage; } catch { storage = { setItem() {} }; }
    applyTheme(document.documentElement, storage, dark ? "light" : "dark");
    window.dispatchEvent(new Event("seclume-theme-change"));
  }
  return (
    <Button variant="ghost" size="icon-lg" onClick={toggle} aria-label="Dark mode" aria-pressed={dark}>
      <Sun className="hidden dark:block" aria-hidden="true" />
      <Moon className="dark:hidden" aria-hidden="true" />
    </Button>
  );
}
