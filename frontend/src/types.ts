export type DatasetStatus = "PROCESSING" | "COMPLETED" | "FAILED";
export type FindingIssueType = "DUPLICATE" | "MISSING_VALUE" | "INVALID_PLACEHOLDER" | "INVALID_CASE" | "INVALID_REFERENCE" | "INVALID_HIERARCHY" | "INVALID_DATE_FORMAT" | "INVALID_COORDINATE" | "FORMAT_ERROR" | "CALCULATION_MISMATCH" | "CROSS_FIELD_MISMATCH" | "STATISTICAL_ANOMALY" | "POTENTIAL_TYPO" | "SEMANTIC_MISMATCH" | "MISSING_COLUMN_HEADER" | "INVALID_IDENTIFIER_FORMAT";
export type FindingSeverity = "HIGH" | "MEDIUM";

export const ISSUE_LABELS: Record<FindingIssueType, string> = {
  MISSING_COLUMN_HEADER: "Kolom tanpa header",
  INVALID_IDENTIFIER_FORMAT: "Format identifier tidak valid",
  DUPLICATE: "Duplikat penuh",
  MISSING_VALUE: "Nilai kosong",
  INVALID_PLACEHOLDER: "Placeholder tidak valid",
  INVALID_CASE: "Teks belum uppercase",
  INVALID_REFERENCE: "Referensi wilayah tidak valid",
  INVALID_HIERARCHY: "Hierarki wilayah tidak valid",
  INVALID_DATE_FORMAT: "Format tanggal tidak valid",
  INVALID_COORDINATE: "Koordinat tidak valid",
  FORMAT_ERROR: "Format numerik tidak valid",
  CALCULATION_MISMATCH: "Perhitungan tidak sesuai",
  CROSS_FIELD_MISMATCH: "Nilai lintas kolom tidak sesuai",
  STATISTICAL_ANOMALY: "Potensi anomali",
  POTENTIAL_TYPO: "Potensi typo",
  SEMANTIC_MISMATCH: "Ketidaksesuaian semantik",
};

export function formatIssueLabel(issue: string): string {
  if (issue in ISSUE_LABELS) {
    return ISSUE_LABELS[issue as FindingIssueType];
  }
  return issue
    .toLowerCase()
    .split("_")
    .map((part) => (part[0] ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ");
}

export interface PublicConfig {
  max_upload_mb: number;
  backoffice_enabled: boolean;
}

export interface LocalUser {
  id: string;
  username: string;
  display_name: string;
  is_admin: boolean;
}

export interface AuthSession {
  user: LocalUser;
  csrf_token: string;
}

export type AccountRole = "Admin" | "Pemeriksa";
export interface UserAccount {
  id: string;
  username: string;
  display_name: string;
  role: AccountRole;
  is_active: boolean;
}

export interface ColumnProfile {
  original_name: string;
  display_name: string;
  position: number;
  inferred_type: string;
  candidate_role: string;
  null_count: number;
  empty_count: number;
  unique_count: number;
  sample_values: unknown[];
  distribution: { value: unknown; count: number }[] | null;
}

export interface AssessmentPreview {
  filename: string;
  worksheet_name: string | null;
  row_count: number;
  column_count: number;
  duplicate_row_count: number;
  rows: PreviewRow[];
  columns: ColumnProfile[];
  checks: string[];
}

export interface Finding {
  id: string;
  row: number;
  column: string | null;
  issue_type: FindingIssueType;
  severity: FindingSeverity;
  original_value: unknown;
  expected_value: unknown;
  evidence: string;
  recommendation: string;
  confidence: number;
  detector: string;
}

export interface FindingSummary {
  by_issue_type: Partial<Record<FindingIssueType, number>>;
  by_severity: Partial<Record<FindingSeverity, number>>;
}

export interface DatasetSummary {
  pending_column_count?: number | null;
  id: string;
  original_filename: string;
  source_type: string;
  file_type: string;
  worksheet_name: string | null;
  status: DatasetStatus;
  row_count: number;
  column_count: number;
  duplicate_row_count: number;
  finding_count: number;
  failure_message: string | null;
  assessment_status: "PASSED" | "NEEDS_CORRECTION" | null;
  parent_dataset_id: string | null;
  owner_id?: string | null;
  owner_display_name?: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface DatasetPage {
  items: DatasetSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface DatasetDetail extends DatasetSummary {
  preview: Record<string, unknown>[];
  source_metadata: Record<string, unknown>;
  column_profiles: ColumnProfile[];
  finding_summary: FindingSummary;
  findings: Finding[];
}

export interface FindingPage {
  items: Finding[];
  total: number;
  total_rows: number;
  page: number;
  page_size: number;
  by_issue_type: Partial<Record<FindingIssueType, number>>;
  row_groups: {
    row: number;
    source_record?: PreviewRow | null;
    findings: Finding[];
    action_summary: string;
    action_summary_source: "ai" | "fallback";
    action_summary_confidence: number | null;
  }[];
}

export interface GlobalFinding extends Finding {
  dataset_id: string;
  dataset_name: string;
  dataset_completed_at: string | null;
}

export interface GlobalFindingPage {
  items: GlobalFinding[];
  total: number;
  page: number;
  page_size: number;
}

export interface ReferenceRow {
  city_code: string;
  city_name: string;
  district_code: string;
  district_name: string;
  village_code: string;
  village_name: string;
}

export interface ReferencePage {
  items: ReferenceRow[];
  total: number;
  page: number;
  page_size: number;
  summary: { cities: number; districts: number; villages: number; sha256: string };
}

export interface SystemSettings {
  limits: { upload_mb: number; rows: number; columns: number; cells: number; findings: number };
  formats: { upload: string[]; report: string[] };
  semantic: { enabled: boolean; max_columns: number; max_candidates: number };
  backoffice_enabled: boolean;
  reference: { sha256: string; cities: number; districts: number; villages: number };
  authentication: { type: "local_account"; session_hours: number };
}

export interface PreviewRow {
  _source_row: number;
  [key: string]: unknown;
}

export interface PreviewPage {
  items: PreviewRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface Dashboard {
  total_assessments: number;
  passed_assessments: number;
  needs_correction_assessments: number;
  latest_findings: number;
  latest_assessment: {
    id: string;
    original_filename: string;
    source_type: string;
    completed_at: string;
    finding_count: number;
    issue_counts: Record<string, number>;
  } | null;
}
