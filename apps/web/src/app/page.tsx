import Link from "next/link";
import DomainCard from "@/components/DomainCard";

const domains = [
  {
    title: "Climate Analytics",
    description:
      "Real-time climate monitoring, anomaly detection, and forecasting across global weather stations and satellite feeds.",
    icon: "🌡️",
    href: "/dashboard/climate",
    status: "healthy" as const,
    metrics: [
      { label: "Stations", value: "12,400" },
      { label: "Variables", value: "48" },
      { label: "Anomalies", value: "23" },
      { label: "Forecasts", value: "7-day" },
    ],
  },
  {
    title: "Biodiversity",
    description:
      "Species tracking, ecosystem health scoring, and conservation priority mapping with AI-powered habitat analysis.",
    icon: "🦎",
    href: "/dashboard/biodiversity",
    status: "warning" as const,
    metrics: [
      { label: "Species", value: "84,200" },
      { label: "Hotspots", value: "36" },
      { label: "Habitats", value: "142" },
      { label: "Threatened", value: "1,208" },
    ],
  },
  {
    title: "Public Health",
    description:
      "Air quality monitoring, disease risk assessment, and heat vulnerability analysis for population health protection.",
    icon: "🏥",
    href: "/dashboard/health",
    status: "warning" as const,
    metrics: [
      { label: "AQI Sensors", value: "8,900" },
      { label: "Risk Zones", value: "18" },
      { label: "Heat Alerts", value: "7" },
      { label: "Coverage", value: "92%" },
    ],
  },
  {
    title: "Food Security",
    description:
      "Crop yield prediction, drought monitoring, and food security index calculation using satellite and ground data.",
    icon: "🌾",
    href: "/dashboard/food-security",
    status: "healthy" as const,
    metrics: [
      { label: "Regions", value: "240" },
      { label: "Crops", value: "32" },
      { label: "Drought Risk", value: "12%" },
      { label: "Yield Δ", value: "+3.2%" },
    ],
  },
  {
    title: "Resource Equity",
    description:
      "Water stress analysis, environmental justice scoring, and resource allocation optimization for equitable distribution.",
    icon: "💧",
    href: "/dashboard/resources",
    status: "critical" as const,
    metrics: [
      { label: "Water Stress", value: "28%" },
      { label: "EJ Score", value: "0.64" },
      { label: "Allocations", value: "580" },
      { label: "Optimized", value: "73%" },
    ],
  },
];

const summaryMetrics = [
  { value: "1.2M", label: "Observations" },
  { value: "180", label: "Countries" },
  { value: "5", label: "Domains" },
  { value: "42", label: "API Endpoints" },
];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-emerald-50 via-white to-slate-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      {/* ── Navigation ── */}
      <nav className="sticky top-0 z-40 border-b border-border bg-white/80 dark:bg-slate-950/80 backdrop-blur-md">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="text-2xl">🌍</span>
            <span className="text-xl font-bold text-foreground tracking-tight">
              EcoTrack
            </span>
          </Link>
          <div className="hidden md:flex items-center gap-6">
            <Link
              href="/dashboard"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Dashboard
            </Link>
            <Link
              href="/dashboard/climate"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Climate
            </Link>
            <Link
              href="/dashboard/biodiversity"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Biodiversity
            </Link>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              API Docs
            </a>
          </div>
          <Link
            href="/dashboard"
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Open Dashboard
          </Link>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="container mx-auto px-4 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 text-primary text-xs font-semibold mb-6">
          <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
          AI-for-Earth Platform v0.1
        </div>
        <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-foreground tracking-tight mb-6">
          EcoTrack
          <br />
          <span className="text-primary">Planetary Environmental Intelligence</span>
        </h1>
        <p className="text-lg md:text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
          Unified analytics across climate, biodiversity, public health, food
          security, and resource equity — powered by federated learning and
          multi-agent AI.
        </p>

        {/* CTA */}
        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl bg-primary text-primary-foreground font-semibold shadow-lg shadow-primary/25 hover:shadow-primary/40 hover:-translate-y-0.5 transition-all"
          >
            🚀 Explore Dashboard
          </Link>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl border-2 border-border text-foreground font-semibold hover:bg-muted hover:-translate-y-0.5 transition-all"
          >
            📖 API Documentation
          </a>
          <a
            href="https://github.com/ecotrack"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl border-2 border-border text-foreground font-semibold hover:bg-muted hover:-translate-y-0.5 transition-all"
          >
            ⭐ GitHub
          </a>
        </div>
      </section>

      {/* ── Summary metrics bar ── */}
      <section className="container mx-auto px-4 pb-12">
        <div className="flex flex-wrap items-center justify-center gap-6 md:gap-12 py-6 px-8 rounded-2xl bg-card border border-border shadow-sm">
          {summaryMetrics.map((m) => (
            <div key={m.label} className="text-center">
              <p className="text-3xl md:text-4xl font-bold text-primary">
                {m.value}
              </p>
              <p className="text-sm text-muted-foreground mt-0.5">{m.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Domain Cards ── */}
      <section className="container mx-auto px-4 pb-20">
        <div className="text-center mb-10">
          <h2 className="text-3xl font-bold text-foreground mb-3">
            Five Integrated Domains
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Cross-domain environmental monitoring with real-time analytics,
            AI-powered insights, and privacy-preserving federated learning.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {domains.map((domain) => (
            <DomainCard key={domain.title} {...domain} />
          ))}
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-border py-8">
        <div className="container mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground">
            © 2026 EcoTrack — AI for Earth. Open-source planetary intelligence.
          </p>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <a href="http://localhost:8000/docs" className="hover:text-foreground transition-colors">
              API
            </a>
            <a href="https://github.com/ecotrack" className="hover:text-foreground transition-colors">
              GitHub
            </a>
            <a href="/dashboard" className="hover:text-foreground transition-colors">
              Dashboard
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}
