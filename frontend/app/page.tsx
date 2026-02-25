"use client";

import React, { useState } from "react";

/* ───────────────────── NAV ───────────────────── */
function Nav() {
  const [open, setOpen] = useState(false);
  const links = [
    { label: "Platform", href: "#platform" },
    { label: "How It Works", href: "#how-it-works" },
    { label: "Industries", href: "#industries" },
    { label: "Advisory Board", href: "#advisory-board" },
    { label: "Governance", href: "#governance" },
    { label: "Deployment", href: "#deployment" },
  ];
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-navy-900/90 backdrop-blur-md border-b border-navy-700/40">
      <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
        <a href="/" className="text-xl font-semibold tracking-wide text-white">
          STRATEGOS
        </a>
        <div className="hidden md:flex items-center gap-8">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="text-sm text-accent-silver hover:text-white transition-colors"
            >
              {l.label}
            </a>
          ))}
          <a
            href="/login"
            className="text-sm px-5 py-2 rounded bg-accent-gold/90 text-navy-900 font-semibold hover:bg-accent-gold transition-colors"
          >
            Launch Platform
          </a>
        </div>
        <button
          className="md:hidden text-accent-silver"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2">
            {open ? (
              <path d="M6 6l12 12M6 18L18 6" />
            ) : (
              <path d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>
      {open && (
        <div className="md:hidden px-6 pb-4 flex flex-col gap-3 bg-navy-900/95 border-b border-navy-700/40">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="text-sm text-accent-silver hover:text-white"
              onClick={() => setOpen(false)}
            >
              {l.label}
            </a>
          ))}
          <a
            href="/login"
            className="text-sm px-4 py-2 rounded bg-accent-gold/90 text-navy-900 font-semibold text-center"
            onClick={() => setOpen(false)}
          >
            Launch Platform
          </a>
        </div>
      )}
    </nav>
  );
}

/* ───────────────────── HERO ───────────────────── */
function Hero() {
  return (
    <section className="relative pt-32 pb-24 md:pt-44 md:pb-36 px-6">
      <div className="max-w-4xl mx-auto text-center">
        <p className="text-accent-gold text-sm font-medium tracking-[0.25em] uppercase mb-6">
          Deterministic Enterprise Transformation Platform
        </p>
        <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold text-white leading-[1.08] tracking-tight">
          Strategy. Quantified.
          <br />
          Governed. Executable.
        </h1>
        <p className="mt-8 text-lg md:text-xl text-gray-400 max-w-2xl mx-auto leading-relaxed">
          STRATEGOS models enterprise transformation with deterministic precision — producing
          strategic roadmaps, risk diagnostics, and board-ready executive briefs autonomously.
          No interpretation drift. No probabilistic guesswork. Every output is reproducible,
          versioned, and auditable.
        </p>
        <div className="mt-12 flex flex-col sm:flex-row gap-4 justify-center">
          <a
            href="/login"
            className="px-8 py-3.5 bg-accent-gold/90 text-navy-900 font-semibold rounded hover:bg-accent-gold transition-colors text-sm tracking-wide"
          >
            Launch Platform
          </a>
          <a
            href="#how-it-works"
            className="px-8 py-3.5 border border-gray-600 text-gray-300 rounded hover:border-gray-400 hover:text-white transition-colors text-sm tracking-wide"
          >
            See How It Works
          </a>
        </div>
      </div>
      {/* Subtle radial glow */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden -z-10">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-accent-gold/[0.03] rounded-full blur-[120px]" />
      </div>
    </section>
  );
}

/* ───────────────────── WHAT WE DELIVER ───────────────────── */
const deliverables = [
  {
    title: "Strategic Roadmaps",
    description:
      "STRATEGOS generates sequenced transformation roadmaps grounded in quantified metrics — not opinion. Every recommendation traces back to deterministic engine output.",
  },
  {
    title: "Enterprise Architecture Blueprints",
    description:
      "STRATEGOS evaluates technical debt exposure and modernization intensity, producing architecture blueprints that map directly to modeled risk surfaces.",
  },
  {
    title: "Risk Diagnostics",
    description:
      "STRATEGOS classifies enterprise state through threshold-based evaluation — NORMAL, ELEVATED_RISK, or CRITICAL_ZONE — with full contribution breakdown per rule.",
  },
  {
    title: "Modernization Intensity Modeling",
    description:
      "STRATEGOS quantifies modernization pressure using coefficient-driven scoring across metrics, surfacing exactly which vectors are driving transformation urgency.",
  },
  {
    title: "Capital Impact Analysis",
    description:
      "STRATEGOS models capital allocation patterns against transformation scenarios, enabling CFO-grade visibility into investment exposure and rebalancing triggers.",
  },
  {
    title: "Board-Ready Executive Briefs",
    description:
      "STRATEGOS synthesizes all engine outputs into governance-grade executive briefs — structured, deterministic, and audit-ready for board-level consumption.",
  },
];

function Platform() {
  return (
    <section id="platform" className="py-24 px-6 section-divider">
      <div className="max-w-6xl mx-auto">
        <p className="text-accent-gold text-sm font-medium tracking-[0.2em] uppercase mb-3">
          What STRATEGOS Delivers
        </p>
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
          Autonomous Strategy Infrastructure
        </h2>
        <p className="text-gray-400 max-w-2xl mb-16">
          STRATEGOS operates as your deterministic strategy engine — modeling transformation at scale
          without human interpretation bottlenecks. Every output is reproducible, every decision traceable.
        </p>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {deliverables.map((d) => (
            <div
              key={d.title}
              className="bg-navy-800/60 border border-navy-700/50 rounded-lg p-6 hover:border-accent-gold/20 transition-colors"
            >
              <h3 className="text-lg font-semibold text-white mb-3">{d.title}</h3>
              <p className="text-sm text-gray-400 leading-relaxed">{d.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ───────────────────── HOW IT WORKS ───────────────────── */
const steps = [
  {
    num: "01",
    title: "Configuration-Driven Modeling",
    description:
      "STRATEGOS loads versioned model configurations — metrics, coefficients, rules, conditions, and state thresholds — entirely from the database. No modeling logic is hardcoded.",
  },
  {
    num: "02",
    title: "Deterministic Engine Execution",
    description:
      "STRATEGOS evaluates every rule condition against input data using sandboxed expression evaluation, producing a scored contribution breakdown with full audit trail.",
  },
  {
    num: "03",
    title: "State Classification",
    description:
      "STRATEGOS classifies the enterprise into a deterministic state — NORMAL, ELEVATED_RISK, or CRITICAL_ZONE — based on threshold evaluation against the computed total score.",
  },
  {
    num: "04",
    title: "Restructuring Trigger",
    description:
      "When STRATEGOS detects CRITICAL_ZONE, it activates restructuring templates from the database — producing actionable restructuring directives with assigned ownership.",
  },
  {
    num: "05",
    title: "Advisory Board Interpretation",
    description:
      "STRATEGOS feeds deterministic outputs to a structured advisory board — domain-specific agents that interpret results without modifying the underlying engine logic.",
  },
];

function HowItWorks() {
  return (
    <section id="how-it-works" className="py-24 px-6 section-divider">
      <div className="max-w-5xl mx-auto">
        <p className="text-accent-gold text-sm font-medium tracking-[0.2em] uppercase mb-3">
          How STRATEGOS Works
        </p>
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
          From Raw Metrics to Executive Clarity
        </h2>
        <p className="text-gray-400 max-w-2xl mb-16">
          STRATEGOS transforms enterprise data into actionable intelligence through a deterministic
          pipeline — no probabilistic models, no interpretation drift.
        </p>
        <div className="space-y-12">
          {steps.map((s) => (
            <div key={s.num} className="flex gap-6 md:gap-8">
              <div className="flex-shrink-0 w-12 h-12 rounded-full bg-navy-700/80 border border-navy-600/60 flex items-center justify-center text-accent-gold font-mono text-sm font-medium">
                {s.num}
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">{s.title}</h3>
                <p className="text-gray-400 leading-relaxed max-w-xl">{s.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ───────────────────── INDUSTRIES ───────────────────── */
const industries = [
  {
    name: "Telecommunications",
    context:
      "STRATEGOS models network modernization intensity, spectrum capital allocation, and regulatory compliance thresholds unique to telecom transformation.",
  },
  {
    name: "Financial Services",
    context:
      "STRATEGOS evaluates credit exposure surfaces, regulatory capital buffers, and systemic risk vectors with deterministic precision for banking and insurance.",
  },
  {
    name: "Energy & Utilities",
    context:
      "STRATEGOS quantifies grid modernization pressure, renewable transition debt, and capital cycle exposure for energy infrastructure transformation.",
  },
  {
    name: "Public Sector",
    context:
      "STRATEGOS models service delivery modernization intensity, compliance governance overlays, and budget reallocation thresholds for government entities.",
  },
  {
    name: "Manufacturing",
    context:
      "STRATEGOS evaluates supply chain restructuring urgency, operational technology debt, and Industry 4.0 modernization readiness across manufacturing portfolios.",
  },
  {
    name: "Healthcare",
    context:
      "STRATEGOS models clinical infrastructure transformation, regulatory compliance pressure, and patient system modernization intensity for health organizations.",
  },
  {
    name: "Private Equity",
    context:
      "STRATEGOS evaluates portfolio company transformations in parallel — producing cross-entity risk diagnostics and capital redeployment scenarios for PE operators.",
  },
  {
    name: "Digital-Native Enterprises",
    context:
      "STRATEGOS models hyper-growth scaling pressure, technical debt accumulation velocity, and platform architecture modernization triggers for born-digital companies.",
  },
];

function Industries() {
  return (
    <section id="industries" className="py-24 px-6 section-divider">
      <div className="max-w-6xl mx-auto">
        <p className="text-accent-gold text-sm font-medium tracking-[0.2em] uppercase mb-3">
          Cross-Industry Adaptability
        </p>
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
          Industry-Agnostic by Architecture. Industry-Aware by Design.
        </h2>
        <p className="text-gray-400 max-w-2xl mb-16">
          STRATEGOS adapts its configuration-driven modeling to any vertical — from heavily regulated
          financial services to high-velocity digital-native enterprises. The engine remains deterministic;
          the configurations carry the industry intelligence.
        </p>
        <div className="grid md:grid-cols-2 gap-6">
          {industries.map((ind) => (
            <div
              key={ind.name}
              className="bg-navy-800/40 border border-navy-700/40 rounded-lg p-6 hover:border-accent-gold/15 transition-colors"
            >
              <h3 className="text-base font-semibold text-white mb-2">{ind.name}</h3>
              <p className="text-sm text-gray-400 leading-relaxed">{ind.context}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ───────────────────── ADVISORY BOARD ───────────────────── */
const advisors = [
  {
    role: "Schema Extraction",
    title: "Input Structuring",
    description:
      "STRATEGOS converts unstructured enterprise context into structured session schemas through confidence-scored extraction with clarification loops.",
  },
  {
    role: "Strategy Advisor",
    title: "Transformation Narrative",
    description:
      "STRATEGOS interprets deterministic engine outputs into strategic transformation roadmaps, modernization narratives, and sequenced advisory recommendations.",
  },
  {
    role: "Risk Officer",
    title: "Risk Diagnostics",
    description:
      "STRATEGOS explains CRITICAL_ZONE triggers, identifies systemic vulnerability surfaces, and produces risk mitigation commentary grounded in engine state.",
  },
  {
    role: "Architecture Advisor",
    title: "Technical Blueprints",
    description:
      "STRATEGOS interprets IT landscape outputs to suggest modernization blueprints and evaluate technical debt exposure at the architecture level.",
  },
  {
    role: "Financial Impact Advisor",
    title: "Capital & Revenue Analysis",
    description:
      "STRATEGOS analyzes financial context from engine output, explains revenue exposure, and suggests capital allocation strategies aligned with modeled risk.",
  },
  {
    role: "Synthesis Advisor",
    title: "Executive Brief Generation",
    description:
      "STRATEGOS aggregates all advisory outputs into a unified board-ready executive brief — without introducing new deterministic claims beyond engine output.",
  },
];

function AdvisoryBoard() {
  return (
    <section id="advisory-board" className="py-24 px-6 section-divider">
      <div className="max-w-6xl mx-auto">
        <p className="text-accent-gold text-sm font-medium tracking-[0.2em] uppercase mb-3">
          STRATEGOS Advisory Board
        </p>
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
          Structured Interpretation. Zero Drift.
        </h2>
        <p className="text-gray-400 max-w-2xl mb-16">
          STRATEGOS augments its deterministic engine with a structured advisory board —
          domain-specific interpretation layers that translate engine output into strategic
          intelligence. The advisory board never modifies deterministic logic. It interprets.
        </p>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {advisors.map((a) => (
            <div
              key={a.role}
              className="bg-navy-800/60 border border-navy-700/50 rounded-lg p-6 hover:border-accent-gold/20 transition-colors"
            >
              <p className="text-xs text-accent-gold font-medium tracking-wider uppercase mb-2">
                {a.role}
              </p>
              <h3 className="text-lg font-semibold text-white mb-3">{a.title}</h3>
              <p className="text-sm text-gray-400 leading-relaxed">{a.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ───────────────────── CASE STUDY ───────────────────── */
function CaseStudy() {
  return (
    <section id="case-study" className="py-24 px-6 section-divider">
      <div className="max-w-5xl mx-auto">
        <p className="text-accent-gold text-sm font-medium tracking-[0.2em] uppercase mb-3">
          Illustrative Case
        </p>
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-16">
          European Telecom — Network Modernization Diagnostic
        </h2>
        <div className="space-y-10">
          {[
            {
              label: "Situation",
              text: "A mid-size European telecom operator faced accelerating capex pressure from legacy network infrastructure, rising technical debt, and regulatory compliance deadlines for next-generation spectrum deployment.",
            },
            {
              label: "Diagnostic State",
              text: "STRATEGOS classified the enterprise as CRITICAL_ZONE — total score 91.39 — triggered by high cost pressure (cost > 220), technical debt exposure (debt > 70), and margin collapse risk (margin < 0.12).",
            },
            {
              label: "Modeled Findings",
              text: "STRATEGOS scored 3/3 rules triggered with full contribution breakdown: cost pressure impact +12, margin collapse impact +16, debt spike impact +10. Composite stress coefficient resolved to 23.57 via formula evaluation.",
            },
            {
              label: "Strategic Roadmap",
              text: "STRATEGOS activated portfolio rationalization (Transformation Office, 90-day horizon) and cost containment (CFO, 60-day horizon) restructuring templates from database configuration.",
            },
            {
              label: "Outcome",
              text: "Deterministic output provided board-ready clarity on transformation sequencing with audit-grade reproducibility. The advisory board generated an executive brief synthesizing risk, architecture, and financial implications.",
            },
          ].map((block) => (
            <div key={block.label} className="flex gap-6 md:gap-8">
              <div className="flex-shrink-0 w-32 md:w-40">
                <p className="text-sm font-semibold text-accent-silver">{block.label}</p>
              </div>
              <p className="text-gray-400 leading-relaxed">{block.text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ───────────────────── GOVERNANCE ───────────────────── */
function Governance() {
  const pillars = [
    {
      title: "Versioned Modeling",
      description:
        "Every model version, coefficient, rule, and threshold is versioned and traceable. STRATEGOS never executes unversioned logic.",
    },
    {
      title: "Admin-Controlled Calibration",
      description:
        "All modeling parameters are controlled by authorized administrators through structured APIs. No autonomous mutation of engine configuration.",
    },
    {
      title: "Full Audit Trail",
      description:
        "Every engine execution produces a timestamped, immutable audit log. Every session supports replay — re-executing the exact same inputs against the same model state.",
    },
    {
      title: "Deterministic Reproducibility",
      description:
        "STRATEGOS guarantees identical outputs for identical inputs. No stochastic variation, no runtime randomness, no interpretation drift.",
    },
  ];

  return (
    <section id="governance" className="py-24 px-6 section-divider">
      <div className="max-w-5xl mx-auto">
        <p className="text-accent-gold text-sm font-medium tracking-[0.2em] uppercase mb-3">
          Governance & Integrity
        </p>
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
          Built for Audit. Built for Trust.
        </h2>
        <p className="text-gray-400 max-w-2xl mb-16">
          STRATEGOS enforces governance at every layer — from model versioning to execution audit trails.
          The platform is designed for environments where reproducibility is not optional.
        </p>
        <div className="grid md:grid-cols-2 gap-8">
          {pillars.map((p) => (
            <div key={p.title} className="bg-navy-800/40 border border-navy-700/40 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-white mb-3">{p.title}</h3>
              <p className="text-sm text-gray-400 leading-relaxed">{p.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ───────────────────── DEPLOYMENT ───────────────────── */
function Deployment() {
  const options = [
    {
      tier: "SaaS",
      description:
        "STRATEGOS hosted and managed. Fastest time-to-value with multi-tenant isolation, automated upgrades, and Supabase-backed persistence.",
    },
    {
      tier: "Private Cloud",
      description:
        "STRATEGOS deployed in your cloud tenancy — AWS, Azure, or GCP. Full data sovereignty with managed infrastructure and dedicated engine instances.",
    },
    {
      tier: "On-Premise",
      description:
        "STRATEGOS deployed inside your network perimeter. Dockerized backend and frontend with customer-managed PostgreSQL, Redis, and infrastructure.",
    },
  ];

  return (
    <section id="deployment" className="py-24 px-6 section-divider">
      <div className="max-w-5xl mx-auto">
        <p className="text-accent-gold text-sm font-medium tracking-[0.2em] uppercase mb-3">
          Deployment Options
        </p>
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
          Your Infrastructure. Your Terms.
        </h2>
        <p className="text-gray-400 max-w-2xl mb-16">
          STRATEGOS supports every deployment posture — from fully managed SaaS to air-gapped
          on-premise installations.
        </p>
        <div className="grid md:grid-cols-3 gap-8">
          {options.map((o) => (
            <div
              key={o.tier}
              className="bg-navy-800/60 border border-navy-700/50 rounded-lg p-6 hover:border-accent-gold/20 transition-colors"
            >
              <h3 className="text-xl font-bold text-white mb-3">{o.tier}</h3>
              <p className="text-sm text-gray-400 leading-relaxed">{o.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ───────────────────── PRICING TIERS ───────────────────── */
function Tiers() {
  const tiers = [
    {
      name: "Engine",
      tag: "Tier 1",
      features: [
        "Deterministic transformation engine",
        "Config-driven rule evaluation",
        "State classification & restructuring",
        "Full audit trail & replay",
        "Multi-tenant API access",
      ],
    },
    {
      name: "Engine + Advisory Board",
      tag: "Tier 2",
      featured: true,
      features: [
        "Everything in Tier 1",
        "Structured advisory board interpretation",
        "Domain-specific strategic narratives",
        "Risk & architecture commentary",
        "Board-ready executive briefs",
      ],
    },
    {
      name: "Engine + Advisory + Calibration",
      tag: "Tier 3",
      features: [
        "Everything in Tier 2",
        "Calibration intelligence layer",
        "Cross-industry configuration tuning",
        "Scenario comparison analytics",
        "Priority support & onboarding",
      ],
    },
  ];

  return (
    <section className="py-24 px-6 section-divider">
      <div className="max-w-5xl mx-auto">
        <p className="text-accent-gold text-sm font-medium tracking-[0.2em] uppercase mb-3">
          Platform Tiers
        </p>
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-16">
          Start Deterministic. Scale Advisory.
        </h2>
        <div className="grid md:grid-cols-3 gap-8">
          {tiers.map((t) => (
            <div
              key={t.name}
              className={`rounded-lg p-6 border ${
                t.featured
                  ? "bg-navy-700/60 border-accent-gold/30"
                  : "bg-navy-800/60 border-navy-700/50"
              }`}
            >
              <p className="text-xs text-accent-gold font-medium tracking-wider uppercase mb-1">
                {t.tag}
              </p>
              <h3 className="text-xl font-bold text-white mb-6">{t.name}</h3>
              <ul className="space-y-3">
                {t.features.map((f) => (
                  <li key={f} className="flex gap-2 text-sm text-gray-400">
                    <span className="text-accent-gold mt-0.5">—</span>
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ───────────────────── CONTACT CTA ───────────────────── */
function Contact() {
  return (
    <section id="contact" className="py-24 px-6 section-divider">
      <div className="max-w-3xl mx-auto text-center">
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
          Request an Advisory Brief
        </h2>
        <p className="text-gray-400 mb-12 max-w-xl mx-auto">
          Provide your enterprise context and STRATEGOS will produce a deterministic diagnostic
          with strategic roadmap, risk classification, and executive-ready output.
        </p>
        <a
          href="/login"
          className="inline-block px-10 py-4 bg-accent-gold/90 text-navy-900 font-semibold rounded hover:bg-accent-gold transition-colors text-sm tracking-wide"
        >
          Launch Platform →
        </a>
        <p className="mt-4 text-sm text-accent-muted">or contact <a href="mailto:advisory@strategos.dev" className="text-accent-gold hover:underline">advisory@strategos.dev</a></p>
      </div>
    </section>
  );
}

/* ───────────────────── FOOTER ───────────────────── */
function Footer() {
  return (
    <footer className="py-12 px-6 border-t border-navy-700/40">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <p className="text-sm text-accent-muted">
          &copy; {new Date().getFullYear()} STRATEGOS. Deterministic Transformation Platform.
        </p>
        <div className="flex gap-6 text-sm text-accent-muted">
          <a href="/console" className="hover:text-white transition-colors">
            Operator Console
          </a>
          <a href="#governance" className="hover:text-white transition-colors">
            Governance
          </a>
        </div>
      </div>
    </footer>
  );
}

/* ───────────────────── PAGE ───────────────────── */
export default function Page() {
  return (
    <>
      <Nav />
      <Hero />
      <Platform />
      <HowItWorks />
      <Industries />
      <AdvisoryBoard />
      <CaseStudy />
      <Governance />
      <Deployment />
      <Tiers />
      <Contact />
      <Footer />
    </>
  );
}
