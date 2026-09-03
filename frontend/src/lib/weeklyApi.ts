/**
 * Weekly Report — Mehrarbeit/Überstunden + Krankheit je Kalenderwoche.
 *
 * Admin-gated (personenbezogene Leistungs-/Gesundheitsdaten). Mehrarbeit/
 * Überstunden aus erfassten Anwesenheiten; Krankheit aus Personio-Abwesenheiten
 * (aktuell datenseitig noch nicht freigegeben → leer, `meta` meldet es).
 */
import { apiClient } from "./apiClient";

export interface WeeklyMeta {
  hat_anwesenheit: boolean;
  hat_krankheitsdaten: boolean;
  anwesenheit_bis: string | null;
  wochen_verfuegbar: string[];
  letzte_woche: string | null;
}

export interface WeeklyPerson {
  name: string;
  stunden: number;
  /** Nur bei Krankheit gesetzt — für den Tage/Stunden-Umschalter. */
  tage?: number | null;
}

export interface WochenKennzahl {
  aktuell: number | null;
  vorwoche: number | null;
}

export interface WeeklyReport {
  kw_label: string;
  kw_prev_label: string;
  saldo_mehrarbeit: WochenKennzahl;
  krankheit_tage: WochenKennzahl;
  krankheit_std: WochenKennzahl;
  ueberstunden_top: WeeklyPerson[];
  krankheit_top: WeeklyPerson[];
  meta: WeeklyMeta;
}

export function fetchWeeklyMeta(): Promise<WeeklyMeta> {
  return apiClient<WeeklyMeta>("/api/hr/weekly-report/meta");
}

export function fetchWeeklyReport(year: number, week: number): Promise<WeeklyReport> {
  return apiClient<WeeklyReport>(`/api/hr/weekly-report?year=${year}&week=${week}`);
}
