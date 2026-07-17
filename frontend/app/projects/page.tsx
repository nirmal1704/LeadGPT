"use client";

import { useState, useEffect } from "react";
import type { Metadata } from "next";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import { supabase } from "@/lib/supabase";
import { getProjects, createProject } from "@/lib/api";
import type { Project } from "@/lib/api";

function ProjectsContent() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadProjects();
  }, []);

  async function loadProjects() {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    const data = await getProjects(session.access_token);
    setProjects(data);
    setLoading(false);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    await createProject(name, description, session.access_token);
    setName("");
    setDescription("");
    setShowModal(false);
    setCreating(false);
    loadProjects();
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-8">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-xl font-semibold text-gray-900">Projects</h1>
            <button
              id="new-project-btn"
              onClick={() => setShowModal(true)}
              className="btn-primary"
            >
              New project
            </button>
          </div>

          {loading ? (
            <p className="text-sm text-gray-400">Loading…</p>
          ) : projects.length === 0 ? (
            <div className="card text-center py-12">
              <p className="text-gray-500 text-sm">No projects yet. Create your first project to get started.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {projects.map((p) => (
                <div key={p.id} className="card">
                  <h2 className="font-medium text-gray-900">{p.name}</h2>
                  {p.description && <p className="text-sm text-gray-500 mt-1">{p.description}</p>}
                  <p className="text-xs text-gray-400 mt-2">{new Date(p.created_at).toLocaleDateString()}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {showModal && (
          <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setShowModal(false)}>
            <div className="card w-full max-w-md" onClick={(e) => e.stopPropagation()}>
              <h2 className="font-semibold text-gray-900 mb-4">New project</h2>
              <form onSubmit={handleCreate} className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                  <input
                    id="project-name-input"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    className="input-field"
                    placeholder="Q3 Lead Campaign"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                  <input
                    id="project-description-input"
                    type="text"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="input-field"
                    placeholder="Optional"
                  />
                </div>
                <div className="flex gap-2 justify-end mt-4">
                  <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">Cancel</button>
                  <button type="submit" className="btn-primary" disabled={creating}>
                    {creating ? "Creating…" : "Create"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default function ProjectsPage() {
  return (
    <AuthGuard>
      <ProjectsContent />
    </AuthGuard>
  );
}
