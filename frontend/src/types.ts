export type DatasetStatus = "PROCESSING" | "COMPLETED" | "FAILED";
export type FindingIssueType = "DUPLICATE" | "MISSING_VALUE" | "INVALID_PLACEHOLDER" | "INVALID_CASE" | "INVALID_REFERENCE" | "INVALID_HIERARCHY";
export type FindingSeverity = "HIGH" | "MEDIUM";

export interface PublicConfig {
  max_upload_mb: number;
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
  status: "OPEN";
}

export interface FindingSummary {
  by_issue_type: Partial<Record<FindingIssueType, number>>;
  by_severity: Partial<Record<FindingSeverity, number>>;
}

export interface DatasetSummary {
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
  created_at: string;
  completed_at: string | null;
}

export interface DatasetDetail extends DatasetSummary {
  preview: Record<string, unknown>[];
  column_profiles: ColumnProfile[];
  finding_summary: FindingSummary;
  findings: Finding[];
}
