"use client";

import { useState } from "react";
import MetricCard from "@/components/MetricCard";
import MapPlaceholder from "@/components/MapPlaceholder";

/* ── Mock data ── */
const ecosystemScores = [
  { name: "Tropical Rainforest", score: 0.72, trend: "down" as const, trendValue: "-2.1%", status: "warning" as const },
  { name: "Coral Reef Systems", score: 0.48, trend: "down" as const, trendValue: "-5.4%", status: "danger" as const },
  { name: "Temperate Forest", score: 0.81, trend: "stable" as const, trendValue: "+0.2%", status: "good" as const },
  { name: "Wetlands", score: 0.63, trend: "down" as const, trendValue: "-1.8%", status: "warning" as const },
  { name: "Grasslands", score: 0.69, trend: "down" as const, trendValue: "-0.9%", status: "warning" as const },
  { name: "Mangroves", score: 0.55, trend: "down" as const, trendValue: "-3.2%", status: "danger" as const },
];

const biodiversityMetrics = [
  { title: "Tracked Species", value: "84,200", trend: "up" as const, trendValue: "+1,240", status: "good" as const },
  { title: "Threatened Species", value: "1,208", trend: "up" as const, trendValue: "+42", status: "danger" as const },
  { title: "Biodiversity Hotspots", value: "36", trend: "stable" as const, status: "good" as const },
  { title: "Ecosystem Health Index", value: "0.64", trend: "down" as const, trendValue: "-0.03", status: "warning" as const },
  { title: "Protected Areas", value: "15.2%", trend: "up" as const, trendValue: "+0.4%", status: "good" as const },
  { title: "Habitat Loss Rate", value: "4.7M", unit: "ha/yr", trend: "down" as const, trendValue: "-8%", status: "warning" as const },
];

const conservationStatus = [
  { category: "Least Concern", count: 54210, pct: 64.4, color: "bg-emerald-500" },
  { category: "Near Threatened", count: 8940, pct: 10.6, color: "bg-lime-500" },
  { category: "Vulnerable", count: 10230, pct: 12.1, color: "bg-amber-500" },
  { category: "Endangered", count: 6840, pct: 8.1, color: "bg-orange-500" },
  { category: "Critically Endangered", count: 3120, pct: 3.7, color: "bg-red-500" },
  { category: "Extinct in Wild", count: 680, pct: 0.8, color: "bg-red-800" },
  { category: "Extinct", count: 180, pct: 0.2, color: "bg-slate-600" },
];

const mockSpecies = [
  { name: "Panthera tigris", common: "Tiger", status: "Endangered", pop: "~4,500", region: "South Asia" },
  { name: "Gorilla beringei", common: "Mountain Gorilla", status: "Endangered", pop: "~1,063", region: "Central Africa" },
  { name: "Phocoena sinus", common: "Vaquita", status: "Critically Endangered", pop: "~10", region: "Gulf of California" },
  { name: "Ailuropoda melanoleuca", common: "Giant Panda", status: "Vulnerable", pop: "~1,864", region: "China" },
  { name: "Dermochelys coriacea", common: "Leatherback Turtle", status: "Vulnerable", pop: "~34,000", region: "Global Oceans" },
  { name: "Diceros bicornis", common: "Black Rhino", status: "Critically Endangered", pop: "~5,630", region: "East/Southern Africa" },
];

const statusColors: Record<string, string> = {
  "Least Concern": "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/30",
  "Near Threatened": "text-lime-600 bg-lime-50 dark:bg-lime-950/30",
  Vulnerable: "text-amber-600 bg-amber-50 dark:bg-amber-950/30",
  Endangered: "text-orange-600 bg-orange-50 dark:bg-orange-950/30",
  "Critically Endangered": "text-red-600 bg-red-50 dark:bg-red-950/30",
  "Extinct in Wild": "text-red-800 bg-red-100 dark:bg-red-950/30",
};

export default function BiodiversityPage() {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredSpecies = mockSpecies.filter(
    (s) =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.common.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <span className="text-3xl">🦎</span> Biodiversity Monitoring
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Species tracking, ecosystem health scoring, and conservation priority mapping
        </p>
      </div>

      {/* Species search */}
      <div>
        <h3 className="eco-section-title">Species Search</h3>
        <div className="relative max-w-md">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">🔍</span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by species name (e.g., tiger, gorilla)..."
            className="w-full h-10 pl-9 pr-4 rounded-lg border border-border bg-card text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        {searchQuery && (
          <div className="mt-3 eco-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-3 font-medium text-muted-foreground">Species</th>
                  <th className="text-left py-2 px-3 font-medium text-muted-foreground">Common Name</th>
                  <th className="text-left py-2 px-3 font-medium text-muted-foreground">Status</th>
                  <th className="text-right py-2 px-3 font-medium text-muted-foreground">Population</th>
                  <th className="text-left py-2 px-3 font-medium text-muted-foreground">Region</th>
                </tr>
              </thead>
              <tbody>
                {filteredSpecies.map((s) => (
                  <tr key={s.name} className="border-b border-border/50 hover:bg-muted/50">
                    <td className="py-2 px-3 font-mono text-xs italic">{s.name}</td>
                    <td className="py-2 px-3 font-medium">{s.common}</td>
                    <td className="py-2 px-3">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded ${statusColors[s.status] ?? ""}`}>
                        {s.status}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right font-medium">{s.pop}</td>
                    <td className="py-2 px-3 text-muted-foreground">{s.region}</td>
                  </tr>
                ))}
                {filteredSpecies.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-muted-foreground">
                      No species found matching &quot;{searchQuery}&quot;
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {biodiversityMetrics.map((m) => (
          <MetricCard key={m.title} {...m} />
        ))}
      </div>

      {/* Ecosystem health score cards */}
      <div>
        <h3 className="eco-section-title">Ecosystem Health Scores</h3>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {ecosystemScores.map((eco) => (
            <div key={eco.name} className="eco-card">
              <p className="text-sm font-semibold text-foreground mb-3">{eco.name}</p>
              <div className="flex items-end justify-between mb-2">
                <span
                  className={`text-2xl font-bold ${
                    eco.score >= 0.7
                      ? "text-emerald-600"
                      : eco.score >= 0.5
                      ? "text-amber-600"
                      : "text-red-600"
                  }`}
                >
                  {eco.score.toFixed(2)}
                </span>
                <span
                  className={`text-xs font-medium ${
                    eco.trend === "down" ? "text-red-500" : eco.trend === "up" ? "text-emerald-500" : "text-muted-foreground"
                  }`}
                >
                  {eco.trendValue}
                </span>
              </div>
              {/* Health bar */}
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    eco.score >= 0.7
                      ? "bg-emerald-500"
                      : eco.score >= 0.5
                      ? "bg-amber-500"
                      : "bg-red-500"
                  }`}
                  style={{ width: `${eco.score * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Map + Conservation status */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div>
          <h3 className="eco-section-title">Biodiversity Hotspot Map</h3>
          <MapPlaceholder title="Global Biodiversity Hotspots" height="h-80" domain="biodiversity" />
        </div>

        <div>
          <h3 className="eco-section-title">Conservation Status Summary</h3>
          <div className="eco-card space-y-3">
            {conservationStatus.map((c) => (
              <div key={c.category} className="flex items-center gap-3">
                <div className={`h-3 w-3 rounded-full ${c.color} shrink-0`} />
                <span className="text-sm text-foreground flex-1 min-w-0 truncate">{c.category}</span>
                <span className="text-sm font-medium text-foreground">{c.count.toLocaleString()}</span>
                <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
                  <div className={`h-full ${c.color} rounded-full`} style={{ width: `${c.pct}%` }} />
                </div>
                <span className="text-xs text-muted-foreground w-10 text-right">{c.pct}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
