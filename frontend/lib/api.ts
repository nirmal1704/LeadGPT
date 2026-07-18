const BASE_URL = "/api/backend";

// ─── Data types ──────────────────────────────────────────────────────────────

export interface JobBrief {
  user_context: string;
  offering: string;
  lead_category: string;
  location: string;
  lead_count: number;
  additional_notes: string;
}

export interface Job {
  id: string;
  objective: string;
  status: string;
  current_stage: string;
  leads_found_so_far: number;
  leads_requested: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  celery_task_id: string | null;
}

export interface JobLog {
  id: string;
  job_id: string;
  message: string;
  level: string;
  created_at: string;
}

export interface JobDetails {
  job: Job;
  logs: JobLog[];
}

export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
}

export interface IntakeResponse {
  status: "needs_info" | "ready";
  // status === "needs_info"
  question?: string;
  partial_brief?: Record<string, unknown>;
  round_number?: number;
  // status === "ready"
  brief?: JobBrief;
  assumptions?: string[];
}

// ─── Request helpers ─────────────────────────────────────────────────────────

function authHeaders(token: string): HeadersInit {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

// ─── Intake ──────────────────────────────────────────────────────────────────

export async function submitIntake(
  message: string,
  partialBrief: Record<string, unknown> | null,
  roundNumber: number,
  token: string
): Promise<IntakeResponse> {
  const res = await fetch(`${BASE_URL}/intake`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      message,
      partial_brief: partialBrief ?? {},
      round_number: roundNumber,
    }),
  });
  if (!res.ok) throw new Error("Intake request failed");
  return res.json();
}

// ─── Jobs ────────────────────────────────────────────────────────────────────

/** Submit a job using a completed JobBrief (replaces the old submitJob). */
export async function submitJobWithBrief(
  brief: JobBrief,
  projectId: string,
  token: string
): Promise<{ job_id: string }> {
  const res = await fetch(`${BASE_URL}/jobs`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ brief, project_id: projectId }),
  });
  if (!res.ok) throw new Error("Failed to submit job");
  return res.json();
}

export async function getJob(jobId: string, token: string): Promise<JobDetails> {
  const res = await fetch(`${BASE_URL}/jobs/${jobId}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Failed to fetch job");
  return res.json();
}

export async function getJobs(token: string): Promise<Job[]> {
  const res = await fetch(`${BASE_URL}/jobs`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Failed to fetch jobs");
  return res.json();
}

// ─── Projects ────────────────────────────────────────────────────────────────

export async function getProjects(token: string): Promise<Project[]> {
  const res = await fetch(`${BASE_URL}/projects`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Failed to fetch projects");
  return res.json();
}

export async function createProject(
  name: string,
  description: string,
  token: string
): Promise<{ project_id: string }> {
  const res = await fetch(`${BASE_URL}/projects`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) throw new Error("Failed to create project");
  return res.json();
}

// ─── Exports ─────────────────────────────────────────────────────────────────

export async function downloadExport(jobId: string, token: string): Promise<Blob> {
  const res = await fetch(`${BASE_URL}/exports/${jobId}/download`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Export not available");
  return res.blob();
}
