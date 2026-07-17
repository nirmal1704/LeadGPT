"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";

const NAV_LINKS = [
  { href: "/chat", label: "Chat" },
  { href: "/projects", label: "Projects" },
  { href: "/exports", label: "Exports" },
  { href: "/history", label: "History" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      setEmail(user?.email ?? null);
    });
  }, []);

  async function handleSignOut() {
    await supabase.auth.signOut();
  }

  return (
    <aside className="w-56 flex-shrink-0 border-r border-gray-200 flex flex-col h-full bg-white">
      <div className="px-4 py-5 border-b border-gray-200">
        <span className="text-lg font-bold text-gray-900">LeadGPT</span>
      </div>

      <nav className="flex-1 px-2 py-4 space-y-1">
        {NAV_LINKS.map(({ href, label }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                active
                  ? "bg-gray-100 text-gray-900"
                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
              }`}
            >
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="px-4 py-4 border-t border-gray-200">
        {email && (
          <p className="text-xs text-gray-500 truncate mb-2" title={email}>
            {email}
          </p>
        )}
        <button
          onClick={handleSignOut}
          className="text-sm text-gray-500 hover:text-gray-800 transition-colors"
          id="sign-out-btn"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
