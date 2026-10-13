import type { DatasetSummary } from "./types";

export const isPotentialIssue = (issue: string) => ["STATISTICAL_ANOMALY", "POTENTIAL_TYPO", "SEMANTIC_MISMATCH"].includes(issue);

export function datasetAssessmentLabel(item: DatasetSummary): string {
  if (item.status === "FAILED") return "Gagal";
  if (item.status === "PROCESSING") return "Diproses";
  if (item.assessment_status === "NEEDS_CORRECTION") return "Perlu koreksi";
  return item.finding_count > 0 ? "Perlu pemeriksaan" : "Tanpa temuan";
}

export function datasetAssessmentTone(item: DatasetSummary): string {
  if (item.status === "FAILED") return "danger";
  if (item.status === "PROCESSING") return "neutral";
  return item.finding_count > 0 ? "warning" : "success";
}

export const displayOriginalValue = (value: unknown): string => value === undefined ? "Tidak tersedia" : value === null ? "NULL" : value === "" ? '""' : typeof value === "string" && !value.trim() ? "␠".repeat(value.length) : typeof value === "object" ? JSON.stringify(value) : String(value);
