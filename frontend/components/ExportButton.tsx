"use client";

import { downloadExport } from "@/lib/api";
import { supabase } from "@/lib/supabase";

interface ExportButtonProps {
  jobId: string;
}

export default function ExportButton({ jobId }: ExportButtonProps) {
  async function handleDownload() {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;

    try {
      const blob = await downloadExport(jobId, session.access_token);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `leads_${jobId}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      alert("Export not available yet. Try again when the job completes.");
    }
  }

  return (
    <button
      id={`export-btn-${jobId}`}
      onClick={handleDownload}
      className="btn-secondary text-xs"
    >
      Download Export
    </button>
  );
}
