"use client";

import { useState, useEffect } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import { supabase } from "@/lib/supabase";
import { getJobs } from "@/lib/api";
import type { Job } from "@/lib/api";

function HistoryContent() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [logs, setLogs] = useState<{ message: string; level: string; created_at: string }[]>([]);

  useEffect(() => {
    loadJobs();
  }, []);

  async function loadJobs() {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    const data = await getJobs(session.access_token);
    setJobs(data);
    setLoading(false);
  }

  async function selectJob(jobId: string) {
    setSelected(jobId);
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/jobs/${jobId}`,
      { headers: { Authorization: `Bearer ${session.access_token}` } }
    );
    const data = await res.json();
    setLogs(data.logs ?? []);
  }

  const STATUS_COLORS: Record<string, string> = {
    completed: "text-green-700",
    failed: "text-red-700",
    running: "text-blue-700",
    queued: "text-gray-600",
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-8">
        <div className="max-w-5xl mx-auto">
          <h1 className="text-xl font-semibold text-gray-900 mb-6">Job History</h1>

          {loading ? (
            <p className="text-sm text-gray-400">Loading…</p>
          ) : (
            <div className="border border-gray-200 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Objective</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {jobs.map((job) => (
                    <tr
                      key={job.id}
                      className="hover:bg-gray-50 cursor-pointer"
                      onClick={() => selectJob(job.id)}
                    >
                      <td className="px-4 py-3 text-gray-900 max-w-xs truncate">{job.objective}</td>
                      <td className={`px-4 py-3 font-medium ${STATUS_COLORS[job.status] ?? "text-gray-600"}`}>
                        {job.status}
                      </td>
                      <td className="px-4 py-3 text-gray-500">{new Date(job.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {selected && logs.length > 0 && (
            <div className="mt-6 card">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-medium text-gray-900">Job Logs</h2>
                <button onClick={() => setSelected(null)} className="text-xs text-gray-400 hover:text-gray-600">
                  Close
                </button>
              </div>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {logs.map((log, idx) => (
                  <div key={idx} className="flex gap-3 text-xs">
                    <span className={`font-medium ${log.level === "error" ? "text-red-600" : "text-gray-500"}`}>
                      {log.level}
                    </span>
                    <span className="text-gray-700">{log.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default function HistoryPage() {
  return (
    <AuthGuard>
      <HistoryContent />
    </AuthGuard>
  );
}
