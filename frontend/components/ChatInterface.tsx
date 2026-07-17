"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { supabase } from "@/lib/supabase";
import {
  submitIntake,
  submitJobWithBrief,
  getJob,
  getProjects,
  downloadExport,
} from "@/lib/api";
import type { Project, JobBrief, JobDetails, IntakeResponse } from "@/lib/api";
import MessageBubble from "@/components/MessageBubble";
import JobStatusBadge from "@/components/JobStatusBadge";

// ─── Types ────────────────────────────────────────────────────────────────────

type Stage = "intake" | "progress" | "results";

interface Message {
  role: "user" | "system";
  content: string;
  timestamp: string;
}

// ─── Stage label mapping ──────────────────────────────────────────────────────

const STAGE_LABELS: Record<string, string> = {
  queued:    "Queued",
  planning:  "Planning search strategy",
  searching: "Searching for businesses",
  verifying: "Verifying lead details",
  building:  "Building Excel file",
  completed: "Complete",
  failed:    "Failed",
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function ChatInterface() {
  // ── Stage ──
  const [stage, setStage] = useState<Stage>("intake");

  // ── Intake state ──
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "system",
      content:
        "Hi! I'm LeadGPT. Tell me what you're looking for and I'll find you verified leads.\n\n" +
        "You can start with something like:\n" +
        "\"I run a web-design agency in Mumbai and I want 20 restaurant leads that don't have a website.\"",
      timestamp: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [partialBrief, setPartialBrief] = useState<Record<string, unknown>>({});
  const [roundNumber, setRoundNumber] = useState(0);

  // ── Project ──
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");

  // ── Progress state ──
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobDetails, setJobDetails] = useState<JobDetails | null>(null);
  const [pollInterval, setPollInterval] = useState<ReturnType<typeof setInterval> | null>(null);

  // ── Results state ──
  const [completedBrief, setCompletedBrief] = useState<JobBrief | null>(null);
  const [assumptions, setAssumptions] = useState<string[]>([]);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);

  // ── Side effects ──

  useEffect(() => {
    loadProjects();
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function loadProjects() {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    const data = await getProjects(session.access_token);
    setProjects(data);
    if (data.length > 0) setSelectedProjectId(data[0].id);
  }

  // ── Intake submit ─────────────────────────────────────────────────────────

  async function handleIntakeSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || submitting) return;

    const userText = input.trim();
    setInput("");
    setSubmitting(true);

    const userMsg: Message = {
      role: "user",
      content: userText,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Not authenticated");

      const response: IntakeResponse = await submitIntake(
        userText,
        partialBrief,
        roundNumber,
        session.access_token
      );

      if (response.status === "needs_info" && response.question) {
        // Still gathering information — show the follow-up question
        setPartialBrief(response.partial_brief ?? partialBrief);
        setRoundNumber(response.round_number ?? roundNumber + 1);
        setMessages((prev) => [
          ...prev,
          { role: "system", content: response.question!, timestamp: new Date().toISOString() },
        ]);
      } else if (response.status === "ready" && response.brief) {
        // Brief is complete — submit the job and move to Progress
        setCompletedBrief(response.brief);
        setAssumptions(response.assumptions ?? []);

        if (!selectedProjectId) {
          setMessages((prev) => [
            ...prev,
            {
              role: "system",
              content: "Please select a project first (or create one in the Projects page).",
              timestamp: new Date().toISOString(),
            },
          ]);
          setSubmitting(false);
          return;
        }

        const confirmMsg = _buildConfirmationMessage(response.brief, response.assumptions ?? []);
        setMessages((prev) => [
          ...prev,
          { role: "system", content: confirmMsg, timestamp: new Date().toISOString() },
        ]);

        const { job_id } = await submitJobWithBrief(
          response.brief,
          selectedProjectId,
          session.access_token
        );

        setJobId(job_id);
        setStage("progress");
        startPolling(job_id, session.access_token);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "system",
          content: "Something went wrong. Please try again.",
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setSubmitting(false);
    }
  }

  // ── Polling ───────────────────────────────────────────────────────────────

  function startPolling(jid: string, token: string) {
    const interval = setInterval(async () => {
      try {
        const details = await getJob(jid, token);
        setJobDetails(details);

        if (details.job.status === "completed" || details.job.status === "failed") {
          clearInterval(interval);
          setPollInterval(null);
          setStage("results");
        }
      } catch {
        // Transient network error — keep polling
      }
    }, 3000);
    setPollInterval(interval);
  }

  // ── Results: download ─────────────────────────────────────────────────────

  async function handleDownload() {
    if (!jobId) return;
    setDownloadError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Not authenticated");
      const blob = await downloadExport(jobId, session.access_token);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `leads_${jobId.slice(0, 8)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setDownloadError("Export not ready yet. Try again in a moment.");
    }
  }

  // ── Start over ────────────────────────────────────────────────────────────

  function handleStartOver() {
    if (pollInterval) clearInterval(pollInterval);
    setStage("intake");
    setMessages([
      {
        role: "system",
        content: "Ready for another search. What leads are you looking for?",
        timestamp: new Date().toISOString(),
      },
    ]);
    setInput("");
    setPartialBrief({});
    setRoundNumber(0);
    setJobId(null);
    setJobDetails(null);
    setCompletedBrief(null);
    setAssumptions([]);
    setDownloadError(null);
    setPollInterval(null);
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full">

      {/* ── INTAKE STAGE ── */}
      {stage === "intake" && (
        <>
          <div className="flex-1 overflow-y-auto px-4 py-4">
            {messages.map((msg, idx) => (
              <MessageBubble
                key={idx}
                role={msg.role}
                content={msg.content}
                timestamp={msg.timestamp}
              />
            ))}
            <div ref={bottomRef} />
          </div>

          <div className="border-t border-gray-200 px-4 py-3">
            {projects.length > 0 && (
              <div className="mb-2">
                <select
                  id="project-select"
                  value={selectedProjectId}
                  onChange={(e) => setSelectedProjectId(e.target.value)}
                  className="input-field text-xs max-w-xs"
                >
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <form onSubmit={handleIntakeSubmit} className="flex gap-2">
              <input
                id="chat-input"
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Tell me what leads you're looking for…"
                className="input-field flex-1"
                disabled={submitting}
              />
              <button
                id="send-btn"
                type="submit"
                className="btn-primary"
                disabled={submitting || !input.trim()}
              >
                {submitting ? "…" : "Send"}
              </button>
            </form>

            {!selectedProjectId && (
              <p className="text-xs text-amber-600 mt-1">
                Please create a project in the Projects page first.
              </p>
            )}
          </div>
        </>
      )}

      {/* ── PROGRESS STAGE ── */}
      {stage === "progress" && jobDetails && (
        <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 gap-6">
          <div className="w-full max-w-sm">
            <div className="flex items-center gap-3 mb-4">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500" />
              </span>
              <span className="text-sm font-medium text-gray-700">
                {STAGE_LABELS[jobDetails.job.current_stage] ?? "Working…"}
              </span>
            </div>

            {jobDetails.job.current_stage !== "planning" &&
              jobDetails.job.leads_requested > 0 && (
              <div className="text-sm text-gray-500 mb-4">
                {jobDetails.job.leads_found_so_far} of {jobDetails.job.leads_requested} leads found
              </div>
            )}

            <JobStatusBadge status={jobDetails.job.status} />

            {/* Log expander */}
            <details className="mt-6">
              <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
                View details
              </summary>
              <div className="mt-2 max-h-48 overflow-y-auto rounded border border-gray-100 bg-gray-50 p-3">
                {jobDetails.logs.map((log) => (
                  <p
                    key={log.id}
                    className={`text-xs leading-relaxed ${
                      log.level === "error" ? "text-red-500" : "text-gray-500"
                    }`}
                  >
                    {log.message}
                  </p>
                ))}
                {jobDetails.logs.length === 0 && (
                  <p className="text-xs text-gray-400">No logs yet…</p>
                )}
              </div>
            </details>
          </div>
        </div>
      )}

      {stage === "progress" && !jobDetails && (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-sm text-gray-400">Starting job…</p>
        </div>
      )}

      {/* ── RESULTS STAGE ── */}
      {stage === "results" && jobDetails && (
        <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 gap-4 text-center">
          {jobDetails.job.status === "completed" ? (
            <>
              <div className="text-2xl">✓</div>
              <p className="font-semibold text-gray-900">
                {jobDetails.job.leads_found_so_far} lead
                {jobDetails.job.leads_found_so_far !== 1 ? "s" : ""} found
                {completedBrief
                  ? ` for ${completedBrief.lead_category} in ${completedBrief.location}`
                  : ""}
              </p>

              {assumptions.length > 0 && (
                <div className="text-xs text-amber-600 text-left max-w-xs">
                  <p className="font-medium mb-1">Assumptions made:</p>
                  <ul className="list-disc list-inside space-y-0.5">
                    {assumptions.map((a, i) => <li key={i}>{a}</li>)}
                  </ul>
                </div>
              )}

              <button
                id="download-btn"
                onClick={handleDownload}
                className="btn-primary mt-2"
              >
                Download Excel
              </button>

              {downloadError && (
                <p className="text-xs text-red-500">{downloadError}</p>
              )}
            </>
          ) : (
            <>
              <div className="text-2xl">✗</div>
              <p className="text-sm text-red-600 font-medium">Job failed.</p>
              <p className="text-xs text-gray-400">Check the log details below.</p>
              <details className="mt-2 text-left w-full max-w-sm">
                <summary className="text-xs text-gray-400 cursor-pointer">View logs</summary>
                <div className="mt-2 max-h-40 overflow-y-auto rounded border border-red-100 bg-red-50 p-3">
                  {jobDetails.logs.filter((l) => l.level === "error").map((log) => (
                    <p key={log.id} className="text-xs text-red-600 leading-relaxed">
                      {log.message}
                    </p>
                  ))}
                </div>
              </details>
            </>
          )}

          <button
            id="start-over-btn"
            onClick={handleStartOver}
            className="text-sm text-gray-400 hover:text-gray-600 mt-4 underline"
          >
            Start a new search
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function _buildConfirmationMessage(brief: JobBrief, assumptions: string[]): string {
  const lines = [
    `Got it. Starting your search now.`,
    ``,
    `• Looking for: **${brief.lead_count} ${brief.lead_category}**`,
    `• Location: ${brief.location}`,
    `• Pitch: ${brief.offering}`,
  ];
  if (brief.additional_notes) {
    lines.push(`• Notes: ${brief.additional_notes}`);
  }
  if (assumptions.length > 0) {
    lines.push(``, `I've made some assumptions where details weren't specified:`);
    assumptions.forEach((a) => lines.push(`  – ${a}`));
  }
  return lines.join("\n");
}
