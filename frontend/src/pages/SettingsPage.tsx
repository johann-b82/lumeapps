import { Redirect } from "wouter";

/**
 * Bare /settings is a redirect to /settings/general (v1.28). The body that
 * used to live here was extracted into GeneralSettingsPage + HrSettingsPage
 * and the link to the Sensors page is now implicit via the SubHeader picker.
 *
 * Kept as a named export at this path so existing imports (App.tsx route
 * registration) and bookmarks to `/settings` continue to work.
 */
export function SettingsPage() {
  return <Redirect to="/settings/general" />;
}
