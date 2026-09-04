import type { AuthSession, Dashboard, DatasetDetail, DatasetSummary, FindingPage, GlobalFindingPage, PreviewPage, PublicConfig, ReferencePage, SystemSettings } from "./types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export class ApiError extends Error {
  constructor(message: string, public requestId?: string) {
    super(message);
  }
}

let csrfToken = "";

async function request<T>(path: string, options?: RequestInit, notifyUnauthorized = true): Promise<T> {
  const method = (options?.method || "GET").toUpperCase();
  const headers = new Headers(options?.headers);
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrfToken) headers.set("x-csrf-token", csrfToken);
  const response = await fetch(`${API_URL}${path}`, { ...options, headers, credentials: "include" });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    if (response.status === 401 && notifyUnauthorized) window.dispatchEvent(new Event("auth-expired"));
    throw new ApiError(
      body?.detail?.message || "Layanan tidak dapat memproses permintaan.",
      body?.detail?.request_id || response.headers.get("x-request-id") || undefined,
    );
  }
  return response.json() as Promise<T>;
}

const rememberSession = (session: AuthSession) => { csrfToken = session.csrf_token; return session; };
export const getCurrentUser = () => request<AuthSession>("/auth/me", undefined, false).then(rememberSession);
export const loginLocal = (username: string, password: string) => request<AuthSession>("/auth/login", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ username, password }),
}, false).then(rememberSession);
export const logoutLocal = () => request<void>("/auth/logout", { method: "POST" }, false).finally(() => { csrfToken = ""; });

export const listDatasets = () => request<DatasetSummary[]>("/datasets");
export const getDataset = (id: string) => request<DatasetDetail>(`/datasets/${id}`);
export const getConfig = () => request<PublicConfig>("/config");
export const uploadDataset = (file: File, parentDatasetId?: string) => {
  const data = new FormData();
  data.append("file", file);
  if (parentDatasetId) data.append("parent_dataset_id", parentDatasetId);
  return request<DatasetDetail>("/datasets", { method: "POST", body: data });
};
export const getDashboard = () => request<Dashboard>("/dashboard");
export const listFindings = (id: string, options: { page: number; pageSize: number; search?: string; severity?: string; issueType?: string }) => {
  const query = new URLSearchParams({ page: String(options.page), page_size: String(options.pageSize) });
  if (options.search) query.set("search", options.search);
  if (options.severity) query.set("severity", options.severity);
  if (options.issueType) query.set("issue_type", options.issueType);
  return request<FindingPage>(`/datasets/${id}/findings?${query}`);
};
export const reportUrl = (id: string, format: "csv" | "xlsx" | "pdf") => `${API_URL}/datasets/${id}/report?format=${format}`;
export const getComparison = (id: string) => request<{ available: boolean; resolved: string[]; remaining: string[]; new: string[] }>(`/datasets/${id}/comparison`);
export const assessBackoffice = (parentDatasetId?: string) => request<DatasetDetail>("/backoffice-assessments" + (parentDatasetId ? `?parent_dataset_id=${encodeURIComponent(parentDatasetId)}` : ""), { method: "POST" });
export const getPreview = (id: string, page: number = 1, pageSize: number = 25) => request<PreviewPage>(`/datasets/${id}/preview?page=${page}&page_size=${pageSize}`);
export const listGlobalFindings = (options: { page: number; pageSize: number; search?: string; severity?: string }) => {
  const query = new URLSearchParams({ page: String(options.page), page_size: String(options.pageSize) });
  if (options.search) query.set("search", options.search);
  if (options.severity) query.set("severity", options.severity);
  return request<GlobalFindingPage>(`/findings?${query}`);
};
export const getReferenceData = (options: { page: number; pageSize: number; search?: string; cityCode?: string }) => {
  const query = new URLSearchParams({ page: String(options.page), page_size: String(options.pageSize) });
  if (options.search) query.set("search", options.search);
  if (options.cityCode) query.set("city_code", options.cityCode);
  return request<ReferencePage>(`/reference-data?${query}`);
};
export const getSystemSettings = () => request<SystemSettings>("/settings");
