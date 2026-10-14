import type { DatasetSummary } from "./types";

export const isPotentialIssue = (issue: string) => ["STATISTICAL_ANOMALY", "POTENTIAL_TYPO", "SEMANTIC_MISMATCH"].includes(issue);

export function datasetAssessmentLabel(item: DatasetSummary): string {
  if (item.status === "FAILED") return "Gagal";
  if (item.status === "PROCESSING") return "Diproses";
  if (item.assessment_status === "NEEDS_CORRECTION") return "Perlu koreksi";
  if ((item.pending_column_count ?? 0) > 0) return "Belum diperiksa penuh";
  return item.finding_count > 0 ? "Perlu pemeriksaan" : "Tanpa temuan";
}

export function datasetAssessmentTone(item: DatasetSummary): string {
  if (item.status === "FAILED") return "danger";
  if (item.status === "PROCESSING") return "neutral";
  return item.finding_count > 0 || (item.pending_column_count ?? 0) > 0 ? "warning" : "success";
}

export type ColumnAssessment = { column: string; status: "ready" | "needs_role" | "needs_header"; suggested_role: string; effective_role: string; source: string; reason: string | null };
export function readColumnAssessment(metadata: Record<string, unknown>): ColumnAssessment[] | null {
  const coverage = metadata.column_assessment;
  if (!coverage || typeof coverage !== "object" || !("columns" in coverage) || !Array.isArray(coverage.columns)) return null;
  const valid = coverage.columns.filter((column): column is ColumnAssessment => !!column && typeof column === "object" && typeof column.column === "string" && ["ready", "needs_role", "needs_header"].includes(column.status) && typeof column.effective_role === "string" && typeof column.suggested_role === "string" && typeof column.source === "string" && (column.reason === null || typeof column.reason === "string"));
  return valid.length === coverage.columns.length ? valid : null;
}

export const displayOriginalValue = (value: unknown): string => value === undefined ? "Tidak tersedia" : value === null ? "NULL" : value === "" ? '""' : typeof value === "string" && !value.trim() ? "␠".repeat(value.length) : typeof value === "object" ? JSON.stringify(value) : String(value);
