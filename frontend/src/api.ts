import type { DatasetDetail, DatasetSummary, PublicConfig } from "./types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export class ApiError extends Error {
  constructor(message: string, public requestId?: string) {
    super(message);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      body?.detail?.message || "Layanan tidak dapat memproses permintaan.",
      body?.detail?.request_id || response.headers.get("x-request-id") || undefined,
    );
  }
  return response.json() as Promise<T>;
}

export const listDatasets = () => request<DatasetSummary[]>("/datasets");
export const getDataset = (id: string) => request<DatasetDetail>(`/datasets/${id}`);
export const getConfig = () => request<PublicConfig>("/config");
export const uploadDataset = (file: File) => {
  const data = new FormData();
  data.append("file", file);
  return request<DatasetDetail>("/datasets", { method: "POST", body: data });
};
