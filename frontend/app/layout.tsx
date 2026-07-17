import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LeadGPT — AI Web Intelligence Platform",
  description:
    "Natural language-driven web intelligence platform. Find leads, audit SEO, and analyze competitors autonomously.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-sans bg-white text-gray-900 antialiased">{children}</body>
    </html>
  );
}
