import { useEffect } from "react";

/**
 * Installs three navigation guards while `isDirty === true`, cleans them
 * all up when `isDirty` flips to false or the component unmounts.
 *
 * 1. `beforeunload` — blocks browser tab close / reload (UX-01 part 2).
 * 2. Document-level capture-phase click on `a[href]` elements — catches
 *    NavBar Link clicks BEFORE wouter's own click handler so we can
 *    preventDefault and show the confirmation dialog. Capture phase is
 *    essential: wouter 3.9.0 has no useBlocker (06-RESEARCH.md Pitfall 3).
 * 3. `popstate` — catches browser back/forward buttons. Since popstate
 *    can't be cancelled, we push state back onto the stack immediately
 *    to keep the user on /settings, then fire the dialog with the
 *    sentinel "__back__" so the caller can decide what to do.
 *
 * Scope rule (D-20): the guard only intercepts navigation AWAY FROM
 * /settings. Clicks on the currently-visible /settings link itself, or
 * intra-page interactions (opening the Reset dialog, editing a picker),
 * MUST NOT fire the dialog. We enforce this by checking
 * `window.location.pathname === "/settings"` inside the click handler
 * and by comparing the target href against `/settings`.
 *
 * @param isDirty  Whether unsaved changes currently exist.
 * @param onShowDialog  Callback fired with the intended destination URL
 *                      (or the sentinel "__back__" for popstate). The
 *                      caller is responsible for rendering the dialog
 *                      and, on confirm, calling its own navigate() and
 *                      discarding the draft.
 *
 * Caller contract:
 * - Pass a stable `onShowDialog` via `useCallback` — otherwise the effect
 *   reinstalls on every render.
 * - The hook never tracks "pending navigation" internally — the caller
 *   tracks this in its own state when `onShowDialog` fires.
 * - On sentinel `"__back__"`, the caller should treat "confirm" as
 *   `window.history.back()` (or `back()` twice because we pushed state
 *   to keep the user on /settings) before discarding the draft.
 */
/**
 * Phase 40-01 extension: the guard's pathname checks previously hardcoded
 * `/settings`. Added an optional `scopePath` so /settings/sensors (SensorsSettingsPage)
 * can reuse this hook. Defaults to "/settings" to preserve the original
 * SettingsPage behavior 1:1. The scope is an exact-match path; clicks on
 * links pointing to that same scope are still ignored so intra-page
 * interactions do not fire the dialog.
 */
export function useUnsavedGuard(
  isDirty: boolean,
  onShowDialog: (to: string) => void,
  scopePath: string = "/settings",
): void {
  useEffect(() => {
    if (!isDirty) return;

    // --- 1. Tab close guard (beforeunload) ---
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // Legacy requirement for Chrome/Edge: returnValue must be set to
      // a truthy string to actually show the prompt. Value is ignored by
      // modern browsers — they show a generic message — but the assignment
      // is still required.
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);

    // --- 2. In-app nav click intercept ---
    const handleClick = (e: MouseEvent) => {
      // Only intercept if we are currently ON the scoped page
      if (window.location.pathname !== scopePath) return;

      // Only intercept primary (left) mouse clicks without modifier keys.
      // Ctrl/Cmd/Shift clicks open in new tab — the user is not leaving.
      if (e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

      const targetEl = e.target as Element | null;
      if (!targetEl) return;
      const anchor = targetEl.closest("a[href]");
      if (!anchor) return;

      const href = anchor.getAttribute("href");
      if (!href) return;

      // Ignore: fragment links, external links, mailto/tel, same-page
      if (href.startsWith("#")) return;
      if (href.startsWith("http://") || href.startsWith("https://")) return;
      if (href.startsWith("mailto:") || href.startsWith("tel:")) return;

      // Ignore clicks that land on the scope path itself (e.g. the NavBar
      // gear icon while already on the scoped page)
      if (href === scopePath) return;

      // Intercept: stop wouter + default navigation, show dialog
      e.preventDefault();
      e.stopPropagation();
      onShowDialog(href);
    };
    document.addEventListener("click", handleClick, { capture: true });

    // --- 3. Popstate (back/forward) guard ---
    const handlePopState = () => {
      if (window.location.pathname !== scopePath) {
        // User navigated away via back/forward. We can't cancel a
        // popstate, but we can immediately push the scope path back
        // onto the stack to keep them visually on the page, then show
        // the confirmation dialog with a sentinel destination.
        window.history.pushState(null, "", scopePath);
        onShowDialog("__back__");
      }
    };
    window.addEventListener("popstate", handlePopState);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      document.removeEventListener("click", handleClick, { capture: true });
      window.removeEventListener("popstate", handlePopState);
    };
  }, [isDirty, onShowDialog, scopePath]);
}
