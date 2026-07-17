import type { Metadata } from "next";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import ChatInterface from "@/components/ChatInterface";

export const metadata: Metadata = {
  title: "Chat — LeadGPT",
  description: "Submit lead generation objectives and track real-time results",
};

export default function ChatPage() {
  return (
    <AuthGuard>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-hidden">
          <ChatInterface />
        </main>
      </div>
    </AuthGuard>
  );
}
