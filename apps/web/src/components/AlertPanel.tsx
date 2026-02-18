"use client";

export interface Alert {
  id: string;
  domain: string;
  severity: "info" | "low" | "medium" | "high" | "critical";
  title: string;
  description: string;
  timestamp: string;
  region: string;
}

interface AlertPanelProps {
  alerts: Alert[];
  maxVisible?: number;
}

const severityConfig: Record<
  Alert["severity"],
  { bg: string; text: string; icon: string; border: string }
> = {
  info: {
    bg: "bg-blue-50 dark:bg-blue-950/30",
    text: "text-blue-700 dark:text-blue-300",
    icon: "ℹ️",
    border: "border-l-blue-500",
  },
  low: {
    bg: "bg-slate-50 dark:bg-slate-950/30",
    text: "text-slate-700 dark:text-slate-300",
    icon: "📋",
    border: "border-l-slate-400",
  },
  medium: {
    bg: "bg-amber-50 dark:bg-amber-950/30",
    text: "text-amber-700 dark:text-amber-300",
    icon: "⚠️",
    border: "border-l-amber-500",
  },
  high: {
    bg: "bg-orange-50 dark:bg-orange-950/30",
    text: "text-orange-700 dark:text-orange-300",
    icon: "🔶",
    border: "border-l-orange-500",
  },
  critical: {
    bg: "bg-red-50 dark:bg-red-950/30",
    text: "text-red-700 dark:text-red-300",
    icon: "🚨",
    border: "border-l-red-600",
  },
};

function timeAgo(timestamp: string): string {
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

export default function AlertPanel({ alerts, maxVisible = 5 }: AlertPanelProps) {
  const visibleAlerts = alerts.slice(0, maxVisible);

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between">
        <h3 className="font-semibold text-foreground flex items-center gap-2">
          <span>🔔</span> Environmental Alerts
        </h3>
        <span className="text-xs font-medium px-2 py-1 rounded-full bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300">
          {alerts.length} active
        </span>
      </div>

      <div className="divide-y divide-border">
        {visibleAlerts.map((alert) => {
          const cfg = severityConfig[alert.severity];
          return (
            <div
              key={alert.id}
              className={`px-5 py-3 border-l-4 ${cfg.border} ${cfg.bg} hover:brightness-95 transition-all cursor-pointer`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm">{cfg.icon}</span>
                    <span className={`text-sm font-semibold ${cfg.text}`}>
                      {alert.title}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {alert.description}
                  </p>
                  <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      📍 {alert.region}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      🏷️ {alert.domain}
                    </span>
                    <span>{timeAgo(alert.timestamp)}</span>
                  </div>
                </div>
                <span
                  className={`shrink-0 text-[10px] font-bold uppercase px-2 py-0.5 rounded ${cfg.bg} ${cfg.text}`}
                >
                  {alert.severity}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {alerts.length > maxVisible && (
        <div className="px-5 py-3 text-center border-t border-border">
          <button className="text-sm font-medium text-primary hover:underline">
            View all {alerts.length} alerts →
          </button>
        </div>
      )}

      {alerts.length === 0 && (
        <div className="px-5 py-8 text-center text-muted-foreground">
          <p className="text-2xl mb-2">✅</p>
          <p className="text-sm">No active alerts</p>
        </div>
      )}
    </div>
  );
}
