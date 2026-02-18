"use client";

import { useState } from "react";
import MetricCard from "@/components/MetricCard";
import AlertPanel, { Alert } from "@/components/AlertPanel";
import MapPlaceholder from "@/components/MapPlaceholder";

/* ── Mock data ── */
const timeRanges = ["24h", "7d", "30d", "90d", "1y"] as const;

const overviewMetrics = [
  { title: "Total Observations", value: "1.2M", trend: "up" as const, trendValue: "+12.4%", status: "good" as const },
  { title: "Active Sensors", value: "34,200", trend: "up" as const, trendValue: "+340", status: "good" as const },
  { title: "Countries Covered", value: "180", trend: "stable" as const, trendValue: "", status: "good" as const },
  { title: "Active Alerts", value: "47", trend: "up" as const, trendValue: "+8", status: "warning" as const },
  { title: "Data Freshness", value: "< 5 min", trend: "stable" as const, status: "good" as const },
  { title: "API Uptime", value: "99.97%", trend: "stable" as const, status: "good" as const },
  { title: "FL Nodes", value: "128", trend: "up" as const, trendValue: "+14", status: "good" as const },
  { title: "Model Accuracy", value: "94.2%", trend: "up" as const, trendValue: "+1.3%", status: "good" as const },
];

const domainSummary = [
  { domain: "Climate", icon: "🌡️", key: "Anomalies detected", value: "23", color: "text-blue-600 dark:text-blue-400" },
  { domain: "Biodiversity", icon: "🦎", key: "Species at risk", value: "1,208", color: "text-green-600 dark:text-green-400" },
  { domain: "Health", icon: "🏥", key: "AQI alerts", value: "12", color: "text-red-600 dark:text-red-400" },
  { domain: "Food Security", icon: "🌾", key: "Drought zones", value: "7", color: "text-amber-600 dark:text-amber-400" },
  { domain: "Resources", icon: "💧", key: "Water stress areas", value: "34", color: "text-purple-600 dark:text-purple-400" },
];

const mockAlerts: Alert[] = [
  {
    id: "a1",
    domain: "Climate",
    severity: "high",
    title: "Arctic Sea Ice Minimum Approaching Record Low",
    description: "Sea ice extent at 3.92M km², tracking 8% below 2012 record minimum.",
    timestamp: new Date(Date.now() - 25 * 60000).toISOString(),
    region: "Arctic Ocean",
  },
  {
    id: "a2",
    domain: "Health",
    severity: "critical",
    title: "Extreme Heat Advisory — South Asia",
    description: "Wet-bulb temperatures exceeding 35°C across northern India and Pakistan.",
    timestamp: new Date(Date.now() - 2 * 3600000).toISOString(),
    region: "South Asia",
  },
  {
    id: "a3",
    domain: "Biodiversity",
    severity: "medium",
    title: "Coral Bleaching Event — Great Barrier Reef",
    description: "Mass bleaching detected across 42% of monitored reef sites.",
    timestamp: new Date(Date.now() - 5 * 3600000).toISOString(),
    region: "Oceania",
  },
  {
    id: "a4",
    domain: "Food Security",
    severity: "high",
    title: "Drought Intensification — Horn of Africa",
    description: "Fourth consecutive failed rainy season. Crop failure predicted at 68%.",
    timestamp: new Date(Date.now() - 12 * 3600000).toISOString(),
    region: "East Africa",
  },
  {
    id: "a5",
    domain: "Resources",
    severity: "medium",
    title: "Groundwater Depletion — Ogallala Aquifer",
    description: "Water table dropped 1.8m below seasonal average.",
    timestamp: new Date(Date.now() - 24 * 3600000).toISOString(),
    region: "Central US",
  },
  {
    id: "a6",
    domain: "Climate",
    severity: "info",
    title: "La Niña Watch Issued",
    description: "ENSO models suggest 60% probability of La Niña developing by Q3.",
    timestamp: new Date(Date.now() - 48 * 3600000).toISOString(),
    region: "Tropical Pacific",
  },
];

export default function DashboardPage() {
  const [timeRange, setTimeRange] = useState<(typeof timeRanges)[number]>("7d");

  return (
    <div className="space-y-8">
      {/* Title row + time selector */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dashboard Overview</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Cross-domain environmental monitoring at a glance
          </p>
        </div>
        <div className="flex items-center gap-1 p-1 rounded-lg bg-muted">
          {timeRanges.map((t) => (
            <button
              key={t}
              onClick={() => setTimeRange(t)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                timeRange === t
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Metric cards grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {overviewMetrics.map((m) => (
          <MetricCard key={m.title} {...m} />
        ))}
      </div>

      {/* Domain summary + Map */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Domain summary cards */}
        <div className="lg:col-span-1 space-y-3">
          <h3 className="eco-section-title">Domain Status</h3>
          {domainSummary.map((d) => (
            <div
              key={d.domain}
              className="flex items-center gap-4 p-4 rounded-xl border border-border bg-card hover:shadow-sm transition-shadow"
            >
              <span className="text-2xl">{d.icon}</span>
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-semibold ${d.color}`}>{d.domain}</p>
                <p className="text-xs text-muted-foreground">{d.key}</p>
              </div>
              <span className="text-lg font-bold text-foreground">{d.value}</span>
            </div>
          ))}
        </div>

        {/* Map placeholder */}
        <div className="lg:col-span-2">
          <h3 className="eco-section-title">Global Coverage</h3>
          <MapPlaceholder title="Global Environmental Monitoring" height="h-[420px]" />
        </div>
      </div>

      {/* Charts placeholder + Alerts */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Charts area */}
        <div>
          <h3 className="eco-section-title">Trends</h3>
          <div className="grid gap-4">
            {/* Chart placeholder 1 */}
            <div className="eco-card h-48 flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <p className="text-3xl mb-2">📈</p>
                <p className="text-sm font-medium">Temperature Anomaly Trend</p>
                <p className="text-xs mt-1">Chart component — connect Recharts or D3</p>
              </div>
            </div>
            {/* Chart placeholder 2 */}
            <div className="eco-card h-48 flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <p className="text-3xl mb-2">📊</p>
                <p className="text-sm font-medium">Cross-Domain Correlation Matrix</p>
                <p className="text-xs mt-1">Chart component — connect Recharts or D3</p>
              </div>
            </div>
          </div>
        </div>

        {/* Alert panel */}
        <div>
          <h3 className="eco-section-title">Recent Alerts</h3>
          <AlertPanel alerts={mockAlerts} maxVisible={6} />
        </div>
      </div>
    </div>
  );
}
