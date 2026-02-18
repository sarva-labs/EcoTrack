"use client";

import MetricCard from "@/components/MetricCard";
import AlertPanel, { Alert } from "@/components/AlertPanel";
import MapPlaceholder from "@/components/MapPlaceholder";

/* ── Mock AQI data ── */
const aqiCards = [
  { city: "Delhi", aqi: 284, category: "Very Unhealthy", color: "bg-purple-500", textColor: "text-purple-700 dark:text-purple-300" },
  { city: "Beijing", aqi: 156, category: "Unhealthy", color: "bg-red-500", textColor: "text-red-700 dark:text-red-300" },
  { city: "Los Angeles", aqi: 78, category: "Moderate", color: "bg-amber-500", textColor: "text-amber-700 dark:text-amber-300" },
  { city: "London", aqi: 42, category: "Good", color: "bg-emerald-500", textColor: "text-emerald-700 dark:text-emerald-300" },
  { city: "São Paulo", aqi: 112, category: "Unhealthy (Sensitive)", color: "bg-orange-500", textColor: "text-orange-700 dark:text-orange-300" },
  { city: "Lagos", aqi: 168, category: "Unhealthy", color: "bg-red-500", textColor: "text-red-700 dark:text-red-300" },
];

const healthMetrics = [
  { title: "Global Avg AQI", value: "94", trend: "up" as const, trendValue: "+6", status: "warning" as const },
  { title: "AQI Sensors Active", value: "8,900", trend: "up" as const, trendValue: "+120", status: "good" as const },
  { title: "Population at Risk", value: "2.4B", trend: "up" as const, trendValue: "+3%", status: "danger" as const },
  { title: "Heat Alerts Active", value: "7", trend: "up" as const, trendValue: "+3", status: "warning" as const },
  { title: "Disease Outbreaks", value: "12", trend: "down" as const, trendValue: "-2", status: "warning" as const },
  { title: "Health Coverage", value: "92%", trend: "up" as const, trendValue: "+1.2%", status: "good" as const },
];

const diseaseRisks = [
  { disease: "Dengue Fever", risk: "High", regions: "SE Asia, C. America", trend: "Increasing", trendColor: "text-red-500" },
  { disease: "Malaria", risk: "Medium", regions: "Sub-Saharan Africa", trend: "Stable", trendColor: "text-amber-500" },
  { disease: "Cholera", risk: "High", regions: "Horn of Africa", trend: "Increasing", trendColor: "text-red-500" },
  { disease: "Lyme Disease", risk: "Medium", regions: "N. America, Europe", trend: "Increasing", trendColor: "text-red-500" },
  { disease: "Heat Stroke", risk: "Critical", regions: "South Asia, Middle East", trend: "Increasing", trendColor: "text-red-500" },
];

const heatVulnerability = [
  { region: "South Asia", wbgt: "34.8°C", pop: "1.8B", vulnerability: "Extreme", color: "text-red-600" },
  { region: "Middle East", wbgt: "33.2°C", pop: "0.4B", vulnerability: "Very High", color: "text-orange-600" },
  { region: "Sub-Saharan Africa", wbgt: "31.5°C", pop: "1.2B", vulnerability: "High", color: "text-amber-600" },
  { region: "Southeast Asia", wbgt: "32.1°C", pop: "0.7B", vulnerability: "Very High", color: "text-orange-600" },
];

const healthAlerts: Alert[] = [
  {
    id: "h1",
    domain: "Health",
    severity: "critical",
    title: "Extreme Heat Emergency — Pakistan",
    description: "Wet-bulb temperatures exceeding 35°C. Hospitals report 340% increase in heat-related admissions.",
    timestamp: new Date(Date.now() - 3 * 3600000).toISOString(),
    region: "South Asia",
  },
  {
    id: "h2",
    domain: "Health",
    severity: "high",
    title: "Wildfire Smoke Advisory — Western US",
    description: "AQI exceeding 200 in 12 counties. Respiratory emergency protocols activated.",
    timestamp: new Date(Date.now() - 8 * 3600000).toISOString(),
    region: "North America",
  },
  {
    id: "h3",
    domain: "Health",
    severity: "medium",
    title: "Dengue Outbreak — Philippines",
    description: "Cases up 180% vs. 5-year average. 14 provinces under alert.",
    timestamp: new Date(Date.now() - 24 * 3600000).toISOString(),
    region: "Southeast Asia",
  },
];

export default function HealthPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <span className="text-3xl">🏥</span> Public Health Dashboard
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Air quality monitoring, disease risk assessment, and heat vulnerability analysis
        </p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {healthMetrics.map((m) => (
          <MetricCard key={m.title} {...m} />
        ))}
      </div>

      {/* AQI Cards */}
      <div>
        <h3 className="eco-section-title">Air Quality Index — Major Cities</h3>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {aqiCards.map((c) => (
            <div key={c.city} className="eco-card">
              <div className="flex items-center justify-between mb-3">
                <p className="font-semibold text-foreground">{c.city}</p>
                <span className={`text-xs font-bold px-2 py-0.5 rounded ${c.textColor} bg-current/10`}>
                  {c.category}
                </span>
              </div>
              <div className="flex items-end gap-2 mb-2">
                <span className={`text-3xl font-bold ${c.textColor}`}>{c.aqi}</span>
                <span className="text-sm text-muted-foreground mb-1">AQI</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full ${c.color} rounded-full`}
                  style={{ width: `${Math.min(c.aqi / 3, 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Disease Risk + Map */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div>
          <h3 className="eco-section-title">Disease Risk Assessment</h3>
          <div className="eco-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-3 font-medium text-muted-foreground">Disease</th>
                  <th className="text-left py-2 px-3 font-medium text-muted-foreground">Risk Level</th>
                  <th className="text-left py-2 px-3 font-medium text-muted-foreground">Regions</th>
                  <th className="text-left py-2 px-3 font-medium text-muted-foreground">Trend</th>
                </tr>
              </thead>
              <tbody>
                {diseaseRisks.map((d) => (
                  <tr key={d.disease} className="border-b border-border/50 hover:bg-muted/50">
                    <td className="py-2 px-3 font-medium">{d.disease}</td>
                    <td className="py-2 px-3">
                      <span
                        className={`text-xs font-semibold px-2 py-0.5 rounded ${
                          d.risk === "Critical"
                            ? "bg-red-100 text-red-700 dark:bg-red-950/30 dark:text-red-300"
                            : d.risk === "High"
                            ? "bg-orange-100 text-orange-700 dark:bg-orange-950/30 dark:text-orange-300"
                            : "bg-amber-100 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300"
                        }`}
                      >
                        {d.risk}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-muted-foreground text-xs">{d.regions}</td>
                    <td className={`py-2 px-3 text-xs font-medium ${d.trendColor}`}>{d.trend}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <h3 className="eco-section-title">Health Risk Map</h3>
          <MapPlaceholder title="Global Health Risk Zones" height="h-80" domain="health" />
        </div>
      </div>

      {/* Heat Vulnerability */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div>
          <h3 className="eco-section-title">Heat Vulnerability Indicators</h3>
          <div className="space-y-3">
            {heatVulnerability.map((h) => (
              <div key={h.region} className="eco-card flex items-center gap-4">
                <div className="flex-1">
                  <p className="font-semibold text-foreground">{h.region}</p>
                  <p className="text-xs text-muted-foreground">Population: {h.pop}</p>
                </div>
                <div className="text-right">
                  <p className="text-lg font-bold text-foreground">{h.wbgt}</p>
                  <p className="text-xs text-muted-foreground">WBGT</p>
                </div>
                <span className={`text-xs font-bold px-2 py-1 rounded ${h.color}`}>
                  {h.vulnerability}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 className="eco-section-title">Health Alerts</h3>
          <AlertPanel alerts={healthAlerts} />
        </div>
      </div>
    </div>
  );
}
