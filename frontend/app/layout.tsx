import React from "react";
import "./globals.css";

export const metadata = {
  title: "STRATEGOS — Strategy. Quantified. Governed. Executable.",
  description:
    "STRATEGOS is a deterministic enterprise transformation modeling platform that produces strategic roadmaps, risk diagnostics, and board-ready executive briefs — autonomously.",
  keywords: [
    "enterprise transformation",
    "deterministic modeling",
    "strategic advisory",
    "risk diagnostics",
    "restructuring",
    "governance",
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-navy-900 text-gray-200 font-body antialiased">
        {children}
      </body>
    </html>
  );
}
