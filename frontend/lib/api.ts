import { CreateJobInput, JobResponse, ResultsResponse } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "API request failed");
  }
  return (await response.json()) as T;
}

export function createJob(payload: CreateJobInput): Promise<JobResponse> {
  return request<JobResponse>("/api/jobs", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getJob(id: string): Promise<JobResponse> {
  return request<JobResponse>(`/api/jobs/${id}`);
}

export function getResults(id: string): Promise<ResultsResponse> {
  return request<ResultsResponse>(`/api/jobs/${id}/results?page=1&pageSize=500`);
}
