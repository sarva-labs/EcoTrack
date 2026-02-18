"use client";

export interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  trend?: "up" | "down" | "stable";
  trendValue?: string;
  status?: "good" | "warning" | "danger";
}

const statusColor: Record<NonNullable<MetricCardProps["status"]>, string> = {
  good: "text-emerald-600 dark:text-emerald-400",
  warning: "text-amber-600 dark:text-amber-400",
  danger: "text-red-600 dark:text-red-400",
};

const trendIcons: Record<NonNullable<MetricCardProps["trend"]>, { icon: string; color: string }> = {
  up: { icon: "↑", color: "text-emerald-600" },
  down: { icon: "↓", color: "text-red-600" },
  stable: { icon: "→", color: "text-muted-foreground" },
};

export default function MetricCard({
  title,
  value,
  unit,
  trend,
  trendValue,
  status = "good",
}: MetricCardProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        {trend && (
          <span
            className={`inline-flex items-center gap-0.5 text-xs font-semibold ${trendIcons[trend].color}`}
          >
            {trendIcons[trend].icon}
            {trendValue && <span>{trendValue}</span>}
          </span>
        )}
      </div>

      <div className="mt-2 flex items-baseline gap-1.5">
        <span className={`text-3xl font-bold tracking-tight ${statusColor[status]}`}>
          {value}
        </span>
        {unit && (
          <span className="text-sm font-medium text-muted-foreground">{unit}</span>
        )}
      </div>
    </div>
  );
}
