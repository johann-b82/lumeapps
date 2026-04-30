/**
 * Theme persistence helpers shared between `ThemeToggle` (desktop) and
 * `UserMenu` (mobile). Single source of truth for what "switch theme" means:
 * toggle the `.dark` class on `<html>` and write `localStorage.theme`.
 *
 * Extracted v1.25 review — the mobile menu item used to inline this logic
 * and would silently drift from `ThemeToggle` if the canonical flip ever
 * changed (e.g. a third "system" mode landing).
 */
export type ThemeMode = "light" | "dark";

export function getTheme(): ThemeMode {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function applyTheme(next: ThemeMode, persist = true): void {
  const root = document.documentElement;
  if (next === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
  if (persist) localStorage.setItem("theme", next);
}

export function toggleTheme(): ThemeMode {
  const next: ThemeMode = getTheme() === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}
