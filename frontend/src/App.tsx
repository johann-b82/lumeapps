import { lazy, Suspense } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { Redirect, Route, Switch, useLocation } from "wouter";
import { Loader2 } from "lucide-react";
import { UploadPage } from "./pages/UploadPage";
import { DashboardPage } from "./pages/DashboardPage";
import { HRPage } from "./pages/HRPage";
import { KpiDashboardHomePage } from "./pages/KpiDashboardHomePage";
import { HrHomePage } from "./pages/HrHomePage";
import { OrganigrammPage } from "./pages/OrganigrammPage";
import { SchulungenPage } from "./pages/SchulungenPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { KompetenzenPage } from "./pages/KompetenzenPage";
import { EmbedBirthdaysPage } from "./pages/EmbedBirthdaysPage";
import { EmbedJoinersPage } from "./pages/EmbedJoinersPage";
import { EmbedWorldCupPage } from "./pages/EmbedWorldCupPage";
import { EmbedWorldCupStandingsPage } from "./pages/EmbedWorldCupStandingsPage";
import { EmbedWorldCupMatchesPage } from "./pages/EmbedWorldCupMatchesPage";
import { EmbedWorldCupKnockoutPage } from "./pages/EmbedWorldCupKnockoutPage";
import { EmbedWorldCupScorersPage } from "./pages/EmbedWorldCupScorersPage";
import { EmbedWorldCupTippspielPage } from "./pages/EmbedWorldCupTippspielPage";
import { QualityPage } from "./pages/QualityPage";
import { ProcurementPage } from "./pages/ProcurementPage";
import { ProductionPage } from "./pages/ProductionPage";
import { ProductionHomePage } from "./pages/ProductionHomePage";
import { MaintenanceMachinesPage } from "./pages/MaintenanceMachinesPage";
import { MaintenanceMachineDetailPage } from "./pages/MaintenanceMachineDetailPage";
import { FinancePage } from "./pages/FinancePage";
import { SensorsPage } from "./pages/SensorsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SensorsSettingsPage } from "./pages/SensorsSettingsPage";
import { GeneralSettingsPage } from "@/pages/GeneralSettingsPage";
import { HrSettingsPage } from "@/pages/HrSettingsPage";
import { QualitySettingsPage } from "@/pages/QualitySettingsPage";
import { FinanceSettingsPage } from "@/pages/FinanceSettingsPage";
import { ProductionSettingsPage } from "@/pages/ProductionSettingsPage";
import { SalesSettingsPage } from "@/pages/SalesSettingsPage";
import { WorldCupSettingsPage } from "@/pages/WorldCupSettingsPage";
import { AtrSettingsPage } from "@/pages/AtrSettingsPage";
import { EmailSettingsPage } from "@/pages/EmailSettingsPage";
import { LoginPage } from "./pages/LoginPage";
import { LauncherPage } from "./pages/LauncherPage";
import { AtrPartsPage } from "./pages/AtrPartsPage";
import { AtrImportPage } from "./pages/AtrImportPage";
import { AtrTemplatePage } from "./pages/AtrTemplatePage";
import { AtrDeliveryReviewPage } from "./pages/AtrDeliveryReviewPage";
import { AuditsPage } from "./pages/AuditsPage";
import { AuditDetailPage } from "./pages/AuditDetailPage";
import { QualityHomePage } from "./pages/QualityHomePage";
import { SignagePage } from "./signage/pages/SignagePage";
import { PairPage } from "./signage/pages/PairPage";
import { PlaylistEditorPage } from "./signage/pages/PlaylistEditorPage";
import { NavBar } from "./components/NavBar";
import { AdminOnly } from "./auth/AdminOnly";
import { RoleGate } from "./auth/RoleGate";
import { useRole } from "./auth/useAuth";

const DocsPage = lazy(() => import("./pages/DocsPage"));
// v1.73 FAIR — lazy so the signage /embed pages (and the rest of the app) don't
// load the heavy OCR (tesseract) / PDF (pdf-lib) modules until /fair is opened.
const FairPage = lazy(() =>
  import("./pages/FairPage").then((m) => ({ default: m.FairPage })),
);
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
  const role = useRole();
  const isLogin = location === "/login";
  const isLauncher = location === "/";
  // The interim QS role is confined to the launcher + FAIR + ATR modules.
  // Any other in-app route redirects to /atr (the backend also 403s those
  // routes; this keeps the UX clean and removes the whole guard in one place
  // when the AD-based rights system lands).
  const qsOutOfScope =
    role === "qs" &&
    !(
      isLogin ||
      isLauncher ||
      location.startsWith("/atr") ||
      location.startsWith("/fair")
    );
  if (qsOutOfScope) {
    return (
      <AuthGate>
        <Redirect to="/atr" />
      </AuthGate>
    );
  }
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
          <Route path="/kpi" component={KpiDashboardHomePage} />
          <Route path="/sales" component={DashboardPage} />
          <Route path="/" component={LauncherPage} />
          <Route path="/upload" component={UploadPage} />
          <Route path="/hr" component={HRPage} />
          <Route path="/hr/home" component={HrHomePage} />
          <Route path="/hr/organigramm" component={OrganigrammPage} />
          {/* Schulungen: der Backend-Router ist komplett admin-gated. */}
          <Route path="/hr/schulungen">
            <AdminOnly><SchulungenPage /></AdminOnly>
          </Route>
          {/* Kompetenzen: Qualifikationsmatrix je Abteilung, HR-intern. */}
          <Route path="/hr/kompetenzen">
            <AdminOnly><KompetenzenPage /></AdminOnly>
          </Route>
          {/* Onboarding: der Backend-Router ist komplett admin-gated. */}
          <Route path="/hr/onboarding">
            <AdminOnly><OnboardingPage /></AdminOnly>
          </Route>
          {/* Qualität hub + Audit-Modul (v1.84). Specific routes precede
              /quality; the :id detail precedes its list (wouter first-match).
              The Qualitäts-KPI dashboard stays at /quality and keeps its own
              (viewer-accessible) gating. */}
          <Route path="/quality/audit/:id">
            <AdminOnly><AuditDetailPage /></AdminOnly>
          </Route>
          <Route path="/quality/audit">
            <AdminOnly><AuditsPage /></AdminOnly>
          </Route>
          <Route path="/quality/home">
            <AdminOnly><QualityHomePage /></AdminOnly>
          </Route>
          <Route path="/quality" component={QualityPage} />
          <Route path="/procurement" component={ProcurementPage} />
          {/* Produktion hub + Maschinen-Wartung (admin-only). Specific routes
              precede /production; the :id detail precedes its list (wouter
              first-match). The Verzug KPI stays at /production (KPI dashboard). */}
          <Route path="/production/maintenance/:id">
            <AdminOnly><MaintenanceMachineDetailPage /></AdminOnly>
          </Route>
          <Route path="/production/maintenance">
            <AdminOnly><MaintenanceMachinesPage /></AdminOnly>
          </Route>
          <Route path="/production/home">
            <AdminOnly><ProductionHomePage /></AdminOnly>
          </Route>
          <Route path="/production" component={ProductionPage} />
          {/* v1.73 FAIR — /fair/:id (editor) MUST precede /fair (list). Admin-only.
              Lazy-loaded (Suspense) so the heavy OCR/PDF modules stay out of the
              main bundle used by the signage /embed pages. */}
          <Route path="/fair/:id">
            <RoleGate allow={["admin", "qs"]}>
              <Suspense fallback={<div className="flex h-64 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin" aria-label="Loading FAIR" /></div>}>
                <FairPage />
              </Suspense>
            </RoleGate>
          </Route>
          <Route path="/fair">
            <RoleGate allow={["admin", "qs"]}>
              <Suspense fallback={<div className="flex h-64 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin" aria-label="Loading FAIR" /></div>}>
                <FairPage />
              </Suspense>
            </RoleGate>
          </Route>
          <Route path="/finance" component={FinancePage} />
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
          <Route path="/atr/template"><RoleGate allow={["admin", "qs"]}><AtrTemplatePage /></RoleGate></Route>
          <Route path="/atr/import"><RoleGate allow={["admin", "qs"]}><AtrImportPage /></RoleGate></Route>
          <Route path="/atr/deliveries/:id"><RoleGate allow={["admin", "qs"]}><AtrDeliveryReviewPage /></RoleGate></Route>
          <Route path="/atr/teilekatalog"><RoleGate allow={["admin", "qs"]}><AtrPartsPage /></RoleGate></Route>
          <Route path="/atr"><RoleGate allow={["admin", "qs"]}><AtrPartsPage /></RoleGate></Route>
          {/* /settings/sensors MUST appear before /settings so wouter's first-match wins */}
          <Route path="/settings/sensors" component={SensorsSettingsPage} />
          <Route path="/settings/general" component={GeneralSettingsPage} />
          <Route path="/settings/hr" component={HrSettingsPage} />
          <Route path="/settings/quality" component={QualitySettingsPage} />
          <Route path="/settings/finance" component={FinanceSettingsPage} />
          <Route path="/settings/production" component={ProductionSettingsPage} />
          <Route path="/settings/sales" component={SalesSettingsPage} />
          <Route path="/settings/worldcup" component={WorldCupSettingsPage} />
          <Route path="/settings/atr" component={AtrSettingsPage} />
          <Route path="/settings/email" component={EmailSettingsPage} />
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

/** Top-level router that lets a few public routes short-circuit before the
 *  Auth-gated AppShell. /embed/* paths are the kiosk/signage views — they
 *  need to render without a Directus session. */
function RootRouter() {
  return (
    <Switch>
      <Route path="/embed/birthdays" component={EmbedBirthdaysPage} />
      <Route path="/embed/joiners" component={EmbedJoinersPage} />
      <Route path="/embed/worldcup/standings" component={EmbedWorldCupStandingsPage} />
      <Route path="/embed/worldcup/matches" component={EmbedWorldCupMatchesPage} />
      <Route path="/embed/worldcup/knockout" component={EmbedWorldCupKnockoutPage} />
      <Route path="/embed/worldcup/scorers" component={EmbedWorldCupScorersPage} />
      <Route path="/embed/worldcup/tippspiel" component={EmbedWorldCupTippspielPage} />
      <Route path="/embed/worldcup" component={EmbedWorldCupPage} />
      <Route>
        <AuthProvider>
          <SettingsDraftProvider>
            <SensorDraftProvider>
              <DateRangeProvider>
                <SensorTimeWindowProvider>
                  <AppShell />
                </SensorTimeWindowProvider>
              </DateRangeProvider>
            </SensorDraftProvider>
          </SettingsDraftProvider>
        </AuthProvider>
      </Route>
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <RootRouter />
      </ThemeProvider>
      <Toaster position="top-right" />
    </QueryClientProvider>
  );
}

export default App;
