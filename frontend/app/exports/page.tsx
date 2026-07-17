"use client";

import { useState, useEffect } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import ExportButton from "@/components/ExportButton";
import { supabase } from "@/lib/supabase";

interface Export {
  id: string;
  job_id: string;
  file_name: string;
  file_type: string;
  created_at: string;
}

function ExportsContent() {
  const [exports, setExports] = useState<Export[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadExports();
  }, []);

  async function loadExports() {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;

    const BASE = process.env.NEXT_PUBLIC_API_URL;
    const res = await fetch(`${BASE}/exports`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    });
    if (res.ok) {
      const data = await res.json();
      setExports(data);
    }
    setLoading(false);
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-8">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-xl font-semibold text-gray-900 mb-6">Exports</h1>

          {loading ? (
            <p className="text-sm text-gray-400">Loading…</p>
          ) : exports.length === 0 ? (
            <div className="card text-center py-12">
              <p className="text-sm text-gray-500">No exports yet. Complete a job to generate an export.</p>
            </div>
          ) : (
            <div className="border border-gray-200 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">File</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Type</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Date</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Download</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {exports.map((exp) => (
                    <tr key={exp.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-gray-900 font-mono text-xs">{exp.file_name}</td>
                      <td className="px-4 py-3 text-gray-500 uppercase">{exp.file_type}</td>
                      <td className="px-4 py-3 text-gray-500">{new Date(exp.created_at).toLocaleDateString()}</td>
                      <td className="px-4 py-3"><ExportButton jobId={exp.job_id} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default function ExportsPage() {
  return (
    <AuthGuard>
      <ExportsContent />
    </AuthGuard>
  );
}
