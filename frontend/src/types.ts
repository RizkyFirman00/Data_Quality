export type DatasetStatus = "PROCESSING" | "COMPLETED" | "FAILED";

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
  failure_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface DatasetDetail extends DatasetSummary {
  preview: Record<string, unknown>[];
  column_profiles: ColumnProfile[];
}
