"use client";

import { useState } from "react";
import MetricCard from "@/components/MetricCard";
import AlertPanel, { Alert } from "@/components/AlertPanel";
import MapPlaceholder from "@/components/MapPlaceholder";

/* ── Mock data ── */
const resourceMetrics = [
  { title: "Global Water Stress", value: "28%", trend: "up" as const, trendValue: "+1.4%", status: "warning" as const },
  { title: "EJ Score (Global Avg)", value: "0.64", trend: "down" as const, trendValue: "-0.02", status: "warning" as const },
  { title: "Resource Allocations", value: "580", trend: "up" as const, trendValue: "+34", status: "good" as const },
  { title: "Optimized Allocations", value: "73%", trend: "up" as const, trendValue: "+4%", status: "good" as const },
  { title: "Water Scarcity Pop.", value: "2.3B", trend: "up" as const, trendValue: "+80M", status: "danger" as const },
  { title: "Renewable Energy Access", value: "67%", trend: "up" as const, trendValue: "+2.8%", status: "good" as const },
];

const waterStressRegions = [
  { region: "Middle East & N. Africa", stress: 86, level: "Extremely High", color: "bg-red-600" },
  { region: "South Asia", stress: 74, level: "High", color: "bg-orange-500" },
  { region: "Central Asia", stress: 68, level: "High", color: "bg-orange-500" },
  { region: "Western US", stress: 52, level: "Medium-High", color: "bg-amber-500" },
  { region: "Northern China", stress: 61, level: "High", color: "bg-orange-500" },
  { region: "Southern Europe", stress: 45, level: "Medium", color: "bg-yellow-500" },
  { region: "Sub-Saharan Africa", stress: 38, level: "Medium", color: "bg-yellow-500" },
  { region: "Southeast Asia", stress: 32, level: "Low-Medium", color: "bg-lime-500" },
];

const ejScores = [
  { community: "Flint, Michigan", score: 0.28, factors: "Water contamination, poverty", status: "Critical" },
  { community: "Cancer Alley, Louisiana", score: 0.31, factors: "Industrial pollution, health disparities", status: "Critical" },
  { community: "South Bronx, NY", score: 0.42, factors: "Air quality, urban heat island", status: "Very Low" },
  { community: "East LA, California", score: 0.48, factors: "Traffic pollution, limited green space", status: "Low" },
  { community: "West Louisville, KY", score: 0.45, factors: "Industrial legacy, waste sites", status: "Low" },
  { community: "Portland, OR (NE)", score: 0.62, factors: "Gentrification, displacement", status: "Moderate" },
];

const optimizerParams = [
  { param: "Equity Weight", value: "0.40", description: "Priority for equitable distribution" },
  { param: "Efficiency Weight", value: "0.35", description: "Priority for resource efficiency" },
  { param: "Sustainability Weight", value: "0.25", description: "Priority for long-term sustainability" },
  { param: "Constraint: Min Access", value: "85%", description: "Minimum resource access threshold" },
  { param: "Constraint: Max Cost", value: "$2.4B", description: "Budget ceiling per allocation cycle" },
];

const resourceAlerts: Alert[] = [
  {
    id: "r1",
    domain: "Resources",
    severity: "critical",
    title: "Water Crisis — Cape Town",
    description: "Dam levels at 18.4%. Day Zero projected in 90 days without immediate intervention.",
    timestamp: new Date(Date.now() - 2 * 3600000).toISOString(),
    region: "Southern Africa",
  },
  {
    id: "r2",
    domain: "Resources",
    severity: "high",
    title: "Groundwater Depletion — Punjab",
    description: "Water table declining 0.5m/year. 60% of wells exceeding sustainable extraction rates.",
    timestamp: new Date(Date.now() - 18 * 3600000).toISOString(),
    region: "South Asia",
  },
  {
    id: "r3",
    domain: "Resources",
    severity: "medium",
    title: "Energy Equity Gap — Rural Sub-Saharan Africa",
    description: "580M people without electricity access. Solar microgrid deployment at 23% of target.",
    timestamp: new Date(Date.now() - 48 * 3600000).toISOString(),
    region: "Sub-Saharan Africa",
  },
];

export default function ResourcesPage() {
  const [optimizing, setOptimizing] = useState(false);

  const handleOptimize = () => {
    setOptimizing(true);
    setTimeout(() => setOptimizing(false), 2000);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <span className="text-3xl">💧</span> Resource Equity
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Water stress analysis, environmental justice scoring, and resource allocation optimization
        </p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {resourceMetrics.map((m) => (
          <MetricCard key={m.title} {...m} />
        ))}
      </div>

      {/* Water stress indicators */}
      <div>
        <h3 className="eco-section-title">Water Stress Indicators by Region</h3>
        <div className="eco-card">
          <div className="space-y-3">
            {waterStressRegions.map((r) => (
              <div key={r.region} className="flex items-center gap-4">
                <span className="text-sm text-foreground w-48 shrink-0 truncate">{r.region}</span>
                <div className="flex-1 h-3 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full ${r.color} rounded-full transition-all`}
                    style={{ width: `${r.stress}%` }}
                  />
                </div>
                <span className="text-sm font-bold text-foreground w-10 text-right">{r.stress}%</span>
                <span
                  className={`text-xs font-semibold w-28 text-right ${
                    r.stress >= 80
                      ? "text-red-600"
                      : r.stress >= 60
                      ? "text-orange-600"
                      : r.stress >= 40
                      ? "text-amber-600"
                      : "text-emerald-600"
                  }`}
                >
                  {r.level}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* EJ Scores + Map */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div>
          <h3 className="eco-section-title">Environmental Justice Score Cards</h3>
          <div className="space-y-3">
            {ejScores.map((ej) => (
              <div key={ej.community} className="eco-card">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-semibold text-foreground">{ej.community}</p>
                    <p className="text-xs text-muted-foreground">{ej.factors}</p>
                  </div>
                  <span
                    className={`text-xs font-bold px-2 py-0.5 rounded ${
                      ej.score < 0.35
                        ? "bg-red-100 text-red-700 dark:bg-red-950/30 dark:text-red-300"
                        : ej.score < 0.5
                        ? "bg-orange-100 text-orange-700 dark:bg-orange-950/30 dark:text-orange-300"
                        : "bg-amber-100 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300"
                    }`}
                  >
                    {ej.status}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        ej.score < 0.35
                          ? "bg-red-500"
                          : ej.score < 0.5
                          ? "bg-orange-500"
                          : "bg-amber-500"
                      }`}
                      style={{ width: `${ej.score * 100}%` }}
                    />
                  </div>
                  <span className="text-lg font-bold text-foreground">{ej.score.toFixed(2)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <div>
            <h3 className="eco-section-title">Resource Distribution Map</h3>
            <MapPlaceholder title="Global Resource Equity" height="h-64" domain="resources" />
          </div>
          <AlertPanel alerts={resourceAlerts} />
        </div>
      </div>

      {/* Resource Allocation Optimizer */}
      <div>
        <h3 className="eco-section-title">Resource Allocation Optimizer</h3>
        <div className="eco-card">
          <div className="grid md:grid-cols-2 gap-6">
            {/* Parameters */}
            <div>
              <p className="text-sm font-medium text-muted-foreground mb-3">Optimization Parameters</p>
              <div className="space-y-3">
                {optimizerParams.map((p) => (
                  <div key={p.param} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                    <div>
                      <p className="text-sm font-medium text-foreground">{p.param}</p>
                      <p className="text-xs text-muted-foreground">{p.description}</p>
                    </div>
                    <span className="text-sm font-bold text-primary">{p.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Action + Result */}
            <div className="flex flex-col">
              <p className="text-sm font-medium text-muted-foreground mb-3">Optimization Engine</p>
              <div className="flex-1 flex flex-col items-center justify-center p-6 rounded-lg bg-muted/50 border border-dashed border-border">
                <span className="text-4xl mb-3">⚡</span>
                <p className="text-sm font-medium text-foreground mb-1">Multi-Objective Optimizer</p>
                <p className="text-xs text-muted-foreground text-center mb-4">
                  Pareto-optimal resource allocation using reinforcement learning policy
                </p>
                <button
                  onClick={handleOptimize}
                  disabled={optimizing}
                  className={`px-6 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                    optimizing
                      ? "bg-muted text-muted-foreground cursor-wait"
                      : "bg-purple-600 text-white hover:bg-purple-700 shadow-lg shadow-purple-500/25"
                  }`}
                >
                  {optimizing ? "⏳ Optimizing..." : "🚀 Run Optimization"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
