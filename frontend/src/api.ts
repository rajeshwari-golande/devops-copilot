const API_BASE = import.meta.env.VITE_API_URL ?? "";

export type Failure = {
  id: number;
  repo: string;
  workflow_name: string;
  job_name: string;
  branch: string;
  status: string;
  classification: string | null;
  root_cause: string | null;
  suggested_fix: string | null;
  confidence: number | null;
  remediation_action: string;
  auto_applied: boolean;
  agent_reasoning: string | null;
  created_at: string | null;
};

export type DashboardStats = {
  total_failures: number;
  diagnosed: number;
  auto_remediated: number;
  awaiting_approval: number;
  feedback_count: number;
  accuracy_estimate: number | null;
  by_classification: Record<string, number>;
  recent_failures: Failure[];
};

export type SampleLog = {
  id: string;
  filename: string;
  title: string;
  description: string;
  expected_classification: string | null;
  content: string;
};

export type Health = {
  status: string;
  mock_mode: boolean;
  llm_ready: boolean;
  llm_backend?: string;
  knowledge_docs?: number;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/health"),
  stats: () => request<DashboardStats>("/api/v1/dashboard/stats"),
  samples: () => request<SampleLog[]>("/api/v1/samples"),
  diagnose: (raw_logs: string) =>
    request<Failure>("/api/v1/failures/diagnose", {
      method: "POST",
      body: JSON.stringify({
        repo: "demo/devops-copilot",
        workflow_name: "CI",
        job_name: "build",
        branch: "main",
        raw_logs,
      }),
    }),
  getFailure: (id: number) => request<Failure>(`/api/v1/failures/${id}`),
  approveRemediation: (id: number) =>
    request<Failure>(`/api/v1/failures/${id}/approve-remediation`, { method: "POST" }),
  feedback: (failure_id: number, is_correct: boolean, notes?: string) =>
    request("/api/v1/feedback", {
      method: "POST",
      body: JSON.stringify({ failure_id, is_correct, engineer_notes: notes }),
    }),
};
