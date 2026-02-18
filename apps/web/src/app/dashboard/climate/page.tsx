"use client";

import { useState } from "react";
import MetricCard from "@/components/MetricCard";
import MapPlaceholder from "@/components/MapPlaceholder";
import AlertPanel, { Alert } from "@/components/AlertPanel";

/* ── Climate variables ── */
const variables = [
  "Temperature",
  "Precipitation",
  "Wind Speed",
  "Humidity",
  "CO₂ Concentration",
  "Sea Surface Temp",
  "Sea Level",
  "Solar Radiation",
] as const;

/* ── Mock metrics ── */
const climateMetrics = [
  { title: "Global Mean Temp Anomaly", value: "+1.42", unit: "°C", trend: "up" as const, trendValue: "+0.08", status: "danger" as const },
  { title: "CO₂ Concentration", value: "423.8", unit: "ppm", trend: "up" as const, trendValue: "+2.4", status: "danger" as const },
  { title: "Sea Level Rise", value: "+3.6", unit: "mm/yr", trend: "up" as const, trendValue: "+0.3", status: "warning" as const },
  { title: "Arctic Sea Ice", value: "4.12", unit: "M km²", trend: "down" as const, trendValue: "-8.2%", status: "danger" as const },
  { title: "Global Precipitation Δ", value: "+2.1", unit: "%", trend: "up" as const, trendValue: "+0.4%", status: "warning" as const },
  { title: "Active Weather Stations", value: "12,400", trend: "stable" as const, status: "good" as const },
];

/* ── Mock temperature trend data ── */
const trendData = [
  { year: 2018, anomaly: 0.83, baseline: 0 },
  { year: 2019, anomaly: 0.98, baseline: 0 },
  { year: 2020, anomaly: 1.02, baseline: 0 },
  { year: 2021, anomaly: 0.84, baseline: 0 },
  { year: 2022, anomaly: 1.15, baseline: 0 },
  { year: 2023, anomaly: 1.18, baseline: 0 },
  { year: 2024, anomaly: 1.35, baseline: 0 },
  { year: 2025, anomaly: 1.42, baseline: 0 },
];

/* ── Mock anomaly alerts ── */
const anomalyAlerts: Alert[] = [
  {
    id: "c1",
    domain: "Climate",
    severity: "critical",
    title: "Record SST in North Atlantic",
    description: "Sea surface temperatures 1.4°C above 1991-2020 average, exceeding previous record by 0.3°C.",
    timestamp: new Date(Date.now() - 1 * 3600000).toISOString(),
    region: "North Atlantic",
  },
  {
    id: "c2",
    domain: "Climate",
    severity: "high",
    title: "Permafrost Thaw Acceleration — Siberia",
    description: "Active layer depth increased 15cm beyond seasonal maximum. Methane emissions elevated.",
    timestamp: new Date(Date.now() - 6 * 3600000).toISOString(),
    region: "Siberia",
  },
  {
    id: "c3",
    domain: "Climate",
    severity: "medium",
    title: "Antarctic Ozone Hole Expanding",
    description: "Current extent 23.4M km², 12% larger than 10-year average for this date.",
    timestamp: new Date(Date.now() - 18 * 3600000).toISOString(),
    region: "Antarctica",
  },
  {
    id: "c4",
    domain: "Climate",
    severity: "info",
    title: "ENSO Neutral Phase Confirmed",
    description: "Niño 3.4 index at -0.2°C. Neutral conditions expected through Q2.",
    timestamp: new Date(Date.now() - 48 * 3600000).toISOString(),
    region: "Tropical Pacific",
  },
];

/* ── Mock forecast ── */
const forecastItems = [
  { region: "Northern Hemisphere", temp: "+1.5°C", precip: "+3%", confidence: "High" },
  { region: "Tropics", temp: "+0.9°C", precip: "-2%", confidence: "Medium" },
  { region: "Southern Hemisphere", temp: "+1.1°C", precip: "+1%", confidence: "High" },
  { region: "Arctic", temp: "+3.2°C", precip: "+8%", confidence: "Low" },
];

export default function ClimatePage() {
  const [selectedVar, setSelectedVar] = useState<string>("Temperature");

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <span className="text-3xl">🌡️</span> Climate Analytics
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Global climate monitoring, anomaly detection, and forecasting
        </p>
      </div>

      {/* Variable selector */}
      <div>
        <h3 className="text-sm font-medium text-muted-foreground mb-2">
          Climate Variable
        </h3>
        <div className="flex flex-wrap gap-2">
          {variables.map((v) => (
            <button
              key={v}
              onClick={() => setSelectedVar(v)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selectedVar === v
                  ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 ring-1 ring-blue-300 dark:ring-blue-700"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {climateMetrics.map((m) => (
          <MetricCard key={m.title} {...m} />
        ))}
      </div>

      {/* Temperature trend visualization */}
      <div>
        <h3 className="eco-section-title">Temperature Anomaly Trend ({selectedVar})</h3>
        <div className="eco-card">
          {/* Mock table chart */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground">Year</th>
                  <th className="text-right py-3 px-4 font-medium text-muted-foreground">Anomaly (°C)</th>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground">Trend</th>
                </tr>
              </thead>
              <tbody>
                {trendData.map((row) => (
                  <tr key={row.year} className="border-b border-border/50 hover:bg-muted/50">
                    <td className="py-2.5 px-4 font-medium text-foreground">{row.year}</td>
                    <td className="py-2.5 px-4 text-right">
                      <span
                        className={
                          row.anomaly > 1.0
                            ? "text-red-600 dark:text-red-400 font-semibold"
                            : "text-amber-600 dark:text-amber-400"
                        }
                      >
                        +{row.anomaly.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-2.5 px-4">
                      {/* Simple bar visualization */}
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-amber-400 to-red-500 rounded-full transition-all"
                            style={{ width: `${(row.anomaly / 1.5) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground w-8">
                          {((row.anomaly / 1.5) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 pt-3 border-t border-border text-xs text-muted-foreground text-center">
            📈 Chart placeholder — connect Recharts for interactive visualization
          </div>
        </div>
      </div>

      {/* Map + Alerts */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div>
          <h3 className="eco-section-title">Climate Anomaly Map</h3>
          <MapPlaceholder title="Global Climate Anomalies" height="h-80" domain="climate" />
        </div>
        <div>
          <h3 className="eco-section-title">Anomaly Alerts</h3>
          <AlertPanel alerts={anomalyAlerts} />
        </div>
      </div>

      {/* Forecast Panel */}
      <div>
        <h3 className="eco-section-title">7-Day Regional Forecast</h3>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {forecastItems.map((f) => (
            <div key={f.region} className="eco-card">
              <p className="text-sm font-semibold text-foreground mb-2">{f.region}</p>
              <div className="space-y-1.5">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Temperature</span>
                  <span className="font-medium text-red-600 dark:text-red-400">{f.temp}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Precipitation</span>
                  <span className="font-medium text-blue-600 dark:text-blue-400">{f.precip}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Confidence</span>
                  <span
                    className={`font-medium ${
                      f.confidence === "High"
                        ? "text-emerald-600"
                        : f.confidence === "Medium"
                        ? "text-amber-600"
                        : "text-red-600"
                    }`}
                  >
                    {f.confidence}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
