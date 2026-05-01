import { lazy, Suspense } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { Redirect, Route, Switch, useLocation } from "wouter";
import { Loader2 } from "lucide-react";
import { UploadPage } from "./pages/UploadPage";
import { DashboardPage } from "./pages/DashboardPage";
import { HRPage } from "./pages/HRPage";
import { SensorsPage } from "./pages/SensorsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SensorsSettingsPage } from "./pages/SensorsSettingsPage";
import { GeneralSettingsPage } from "@/pages/GeneralSettingsPage";
import { HrSettingsPage } from "@/pages/HrSettingsPage";
import { LoginPage } from "./pages/LoginPage";
import { LauncherPage } from "./pages/LauncherPage";
import { SignagePage } from "./signage/pages/SignagePage";
import { PairPage } from "./signage/pages/PairPage";
import { PlaylistEditorPage } from "./signage/pages/PlaylistEditorPage";
import { NavBar } from "./components/NavBar";
import { AdminOnly } from "./auth/AdminOnly";

const DocsPage = lazy(() => import("./pages/DocsPage"));
import { SubHeader } from "./components/SubHeader";
import { ThemeProvider } from "./components/ThemeProvider";
import { SettingsDraftProvider } from "./contexts/SettingsDraftContext";
import { SensorDraftProvider } from "./contexts/SensorDraftContext";
import { SensorTimeWindowProvider } from "./components/sensors/SensorTimeWindow";
import { DateRangeProvider } from "./contexts/DateRangeContext";
import { AuthProvider } from "./auth/AuthContext";
import { AuthGate } from "./auth/AuthGate";
import { queryClient } from "./queryClient";

function AppShell() {
  const [location] = useLocation();
  const isLogin = location === "/login";
  const isLauncher = location === "/";
  return (
    <AuthGate>
      {!isLogin && (
        <>
          <NavBar />
          <SubHeader />
        </>
      )}
      <main className={isLogin ? "" : isLauncher ? "pt-16" : "pt-28"}>
        <Switch>
          <Route path="/login" component={LoginPage} />
          <Route path="/sales" component={DashboardPage} />
          <Route path="/" component={LauncherPage} />
          <Route path="/upload" component={UploadPage} />
          <Route path="/hr" component={HRPage} />
          <Route path="/sensors" component={SensorsPage} />
          {/* Phase 46 — signage routes (specific → general per wouter first-match). */}
          {/* Plan 46-05 — /signage/playlists/:id MUST precede /signage/playlists (Pitfall 1). */}
          <Route path="/signage/playlists/:id">
            <AdminOnly><PlaylistEditorPage /></AdminOnly>
          </Route>
          <Route path="/signage/playlists">
            <AdminOnly><SignagePage initialTab="playlists" /></AdminOnly>
          </Route>
          <Route path="/signage/devices">
            <AdminOnly><SignagePage initialTab="devices" /></AdminOnly>
          </Route>
          <Route path="/signage/media">
            <AdminOnly><SignagePage initialTab="media" /></AdminOnly>
          </Route>
          <Route path="/signage/schedules">
            <AdminOnly><SignagePage initialTab="schedules" /></AdminOnly>
          </Route>
          <Route path="/signage/pair">
            <AdminOnly><PairPage /></AdminOnly>
          </Route>
          <Route path="/signage">
            <AdminOnly><Redirect to="/signage/media" /></AdminOnly>
          </Route>
          {/* /settings/sensors MUST appear before /settings so wouter's first-match wins */}
          <Route path="/settings/sensors" component={SensorsSettingsPage} />
          <Route path="/settings/general" component={GeneralSettingsPage} />
          <Route path="/settings/hr" component={HrSettingsPage} />
          <Route path="/settings" component={SettingsPage} />
          <Route path="/docs/:section/:slug">
            <Suspense fallback={
              <div className="flex h-64 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin" aria-label="Loading documentation" />
              </div>
            }>
              <DocsPage />
            </Suspense>
          </Route>
          <Route path="/docs">
            <Suspense fallback={
              <div className="flex h-64 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin" aria-label="Loading documentation" />
              </div>
            }>
              <DocsPage />
            </Suspense>
          </Route>
        </Switch>
      </main>
    </AuthGate>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider>
          <SettingsDraftProvider>
            <SensorDraftProvider>
              <DateRangeProvider>
                <SensorTimeWindowProvider>
                  <AppShell />
                </SensorTimeWindowProvider>
              </DateRangeProvider>
            </SensorDraftProvider>
          </SettingsDraftProvider>
        </ThemeProvider>
      </AuthProvider>
      <Toaster position="top-right" />
    </QueryClientProvider>
  );
}

export default App;
