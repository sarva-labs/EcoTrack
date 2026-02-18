"use client";

import MetricCard from "@/components/MetricCard";
import AlertPanel, { Alert } from "@/components/AlertPanel";
import MapPlaceholder from "@/components/MapPlaceholder";

/* ── Mock data ── */
const foodMetrics = [
  { title: "Global Yield Index", value: "1.08", trend: "up" as const, trendValue: "+3.2%", status: "good" as const },
  { title: "Regions Monitored", value: "240", trend: "stable" as const, status: "good" as const },
  { title: "Crops Tracked", value: "32", trend: "stable" as const, status: "good" as const },
  { title: "Drought Risk Areas", value: "28", trend: "up" as const, trendValue: "+4", status: "warning" as const },
  { title: "Food Insecure Pop.", value: "783M", trend: "up" as const, trendValue: "+2.1%", status: "danger" as const },
  { title: "Prediction Accuracy", value: "91.4%", trend: "up" as const, trendValue: "+1.8%", status: "good" as const },
];

const cropYields = [
  { crop: "🌾 Wheat", region: "South Asia", predicted: "3.42 t/ha", change: "+4.1%", confidence: "High", status: "good" },
  { crop: "🌽 Maize", region: "East Africa", predicted: "1.87 t/ha", change: "-12.3%", confidence: "Medium", status: "danger" },
  { crop: "🍚 Rice", region: "Southeast Asia", predicted: "4.21 t/ha", change: "+1.8%", confidence: "High", status: "good" },
  { crop: "🫘 Soybean", region: "South America", predicted: "3.15 t/ha", change: "+2.4%", confidence: "High", status: "good" },
  { crop: "🥔 Potato", region: "Central Europe", predicted: "28.6 t/ha", change: "-3.2%", confidence: "Medium", status: "warning" },
  { crop: "🌿 Cassava", region: "West Africa", predicted: "9.82 t/ha", change: "+0.5%", confidence: "Low", status: "good" },
];

const droughtAlerts: Alert[] = [
  {
    id: "f1",
    domain: "Food Security",
    severity: "critical",
    title: "Severe Drought — Horn of Africa",
    description: "Fourth consecutive failed rainy season. Crop failure at 68%. 23M people facing acute food insecurity.",
    timestamp: new Date(Date.now() - 4 * 3600000).toISOString(),
    region: "East Africa",
  },
  {
    id: "f2",
    domain: "Food Security",
    severity: "high",
    title: "Agricultural Drought — Central India",
    description: "Monsoon deficit of 38%. Kharif crop sowing delayed by 3 weeks. Rice paddy stress detected via NDVI.",
    timestamp: new Date(Date.now() - 12 * 3600000).toISOString(),
    region: "South Asia",
  },
  {
    id: "f3",
    domain: "Food Security",
    severity: "medium",
    title: "Soil Moisture Deficit — US Midwest",
    description: "Topsoil moisture below 20th percentile in 34 counties. Corn yield impact estimated at -5%.",
    timestamp: new Date(Date.now() - 36 * 3600000).toISOString(),
    region: "North America",
  },
  {
    id: "f4",
    domain: "Food Security",
    severity: "info",
    title: "Locust Swarm Advisory — Arabian Peninsula",
    description: "Breeding conditions favorable. Monitoring for potential swarm formation in coming weeks.",
    timestamp: new Date(Date.now() - 72 * 3600000).toISOString(),
    region: "Middle East",
  },
];

const foodSecurityIndex = [
  { country: "🇳🇴 Norway", score: 87.4, category: "Very High", color: "bg-emerald-500" },
  { country: "🇮🇪 Ireland", score: 84.0, category: "Very High", color: "bg-emerald-500" },
  { country: "🇧🇷 Brazil", score: 62.1, category: "Moderate", color: "bg-amber-500" },
  { country: "🇮🇳 India", score: 50.2, category: "Low", color: "bg-orange-500" },
  { country: "🇳🇬 Nigeria", score: 39.8, category: "Very Low", color: "bg-red-500" },
  { country: "🇾🇪 Yemen", score: 22.4, category: "Critical", color: "bg-red-700" },
];

export default function FoodSecurityPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <span className="text-3xl">🌾</span> Food Security
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Crop yield prediction, drought monitoring, and food security index tracking
        </p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {foodMetrics.map((m) => (
          <MetricCard key={m.title} {...m} />
        ))}
      </div>

      {/* Crop Yield Predictions */}
      <div>
        <h3 className="eco-section-title">Crop Yield Predictions</h3>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {cropYields.map((c) => (
            <div key={c.crop + c.region} className="eco-card">
              <div className="flex items-center justify-between mb-2">
                <span className="text-lg font-semibold text-foreground">{c.crop}</span>
                <span
                  className={`text-xs font-bold px-2 py-0.5 rounded ${
                    c.confidence === "High"
                      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300"
                      : c.confidence === "Medium"
                      ? "bg-amber-100 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300"
                      : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                  }`}
                >
                  {c.confidence}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mb-2">{c.region}</p>
              <div className="flex items-baseline gap-2">
                <span className="text-xl font-bold text-foreground">{c.predicted}</span>
                <span
                  className={`text-sm font-semibold ${
                    c.status === "good"
                      ? "text-emerald-600"
                      : c.status === "warning"
                      ? "text-amber-600"
                      : "text-red-600"
                  }`}
                >
                  {c.change}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Drought alerts + Map */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div>
          <h3 className="eco-section-title">Drought Alerts</h3>
          <AlertPanel alerts={droughtAlerts} />
        </div>
        <div>
          <h3 className="eco-section-title">Drought Risk Map</h3>
          <MapPlaceholder title="Global Drought Monitoring" height="h-80" domain="food-security" />
        </div>
      </div>

      {/* Food Security Index */}
      <div>
        <h3 className="eco-section-title">Global Food Security Index</h3>
        <div className="eco-card">
          <div className="space-y-3">
            {foodSecurityIndex.map((c) => (
              <div key={c.country} className="flex items-center gap-4">
                <span className="text-sm font-medium text-foreground w-32">{c.country}</span>
                <div className="flex-1 h-3 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full ${c.color} rounded-full transition-all`}
                    style={{ width: `${c.score}%` }}
                  />
                </div>
                <span className="text-sm font-bold text-foreground w-12 text-right">{c.score}</span>
                <span
                  className={`text-xs font-semibold w-20 text-right ${
                    c.score >= 80
                      ? "text-emerald-600"
                      : c.score >= 60
                      ? "text-amber-600"
                      : c.score >= 40
                      ? "text-orange-600"
                      : "text-red-600"
                  }`}
                >
                  {c.category}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
