"use client";

interface MapPlaceholderProps {
  title?: string;
  height?: string;
  domain?: string;
}

const domainGradients: Record<string, string> = {
  climate: "from-blue-100 to-cyan-50 dark:from-blue-950 dark:to-cyan-950",
  biodiversity: "from-green-100 to-emerald-50 dark:from-green-950 dark:to-emerald-950",
  health: "from-red-100 to-rose-50 dark:from-red-950 dark:to-rose-950",
  "food-security": "from-amber-100 to-yellow-50 dark:from-amber-950 dark:to-yellow-950",
  resources: "from-purple-100 to-violet-50 dark:from-purple-950 dark:to-violet-950",
  default: "from-slate-100 to-slate-50 dark:from-slate-900 dark:to-slate-800",
};

export default function MapPlaceholder({
  title = "Geospatial Visualization",
  height = "h-80",
  domain = "default",
}: MapPlaceholderProps) {
  const gradient = domainGradients[domain] ?? domainGradients.default;

  return (
    <div
      className={`relative ${height} rounded-xl border border-border overflow-hidden bg-gradient-to-br ${gradient}`}
    >
      {/* Grid overlay to simulate map */}
      <div className="absolute inset-0 opacity-20">
        <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="mapGrid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path
                d="M 40 0 L 0 0 0 40"
                fill="none"
                stroke="currentColor"
                strokeWidth="0.5"
              />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#mapGrid)" />
        </svg>
      </div>

      {/* Simulated data points */}
      <div className="absolute inset-0">
        {[
          { top: "20%", left: "30%", size: "w-3 h-3", opacity: "opacity-60" },
          { top: "40%", left: "55%", size: "w-4 h-4", opacity: "opacity-80" },
          { top: "60%", left: "25%", size: "w-2.5 h-2.5", opacity: "opacity-50" },
          { top: "35%", left: "70%", size: "w-3.5 h-3.5", opacity: "opacity-70" },
          { top: "55%", left: "45%", size: "w-2 h-2", opacity: "opacity-40" },
          { top: "75%", left: "65%", size: "w-3 h-3", opacity: "opacity-55" },
          { top: "25%", left: "80%", size: "w-2 h-2", opacity: "opacity-45" },
        ].map((point, i) => (
          <div
            key={i}
            className={`absolute ${point.size} ${point.opacity} rounded-full bg-primary animate-pulse`}
            style={{ top: point.top, left: point.left, animationDelay: `${i * 0.3}s` }}
          />
        ))}
      </div>

      {/* Center label */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="bg-white/80 dark:bg-black/60 backdrop-blur-sm rounded-lg px-6 py-4 text-center shadow-sm">
          <span className="text-3xl mb-2 block">🗺️</span>
          <h4 className="font-semibold text-foreground text-sm">{title}</h4>
          <p className="text-xs text-muted-foreground mt-1">
            Interactive map powered by Deck.gl
          </p>
          <p className="text-[10px] text-muted-foreground mt-0.5">
            Integration ready — connect your Mapbox token
          </p>
        </div>
      </div>
    </div>
  );
}
