"use client";

import Link from "next/link";

export interface DomainCardProps {
  title: string;
  description: string;
  icon: string;
  href: string;
  metrics: { label: string; value: string }[];
  status: "healthy" | "warning" | "critical";
}

const statusStyles: Record<DomainCardProps["status"], { dot: string; bg: string; border: string }> = {
  healthy: {
    dot: "bg-emerald-500",
    bg: "bg-emerald-50 dark:bg-emerald-950/30",
    border: "border-emerald-200 dark:border-emerald-800",
  },
  warning: {
    dot: "bg-amber-500",
    bg: "bg-amber-50 dark:bg-amber-950/30",
    border: "border-amber-200 dark:border-amber-800",
  },
  critical: {
    dot: "bg-red-500",
    bg: "bg-red-50 dark:bg-red-950/30",
    border: "border-red-200 dark:border-red-800",
  },
};

export default function DomainCard({
  title,
  description,
  icon,
  href,
  metrics,
  status,
}: DomainCardProps) {
  const styles = statusStyles[status];

  return (
    <Link href={href} className="group block">
      <div
        className={`relative overflow-hidden rounded-xl border ${styles.border} ${styles.bg} p-6 transition-all duration-300 hover:shadow-lg hover:-translate-y-1`}
      >
        {/* Status indicator */}
        <div className="absolute top-4 right-4 flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${styles.dot} animate-pulse`} />
          <span className="text-xs font-medium text-muted-foreground capitalize">
            {status}
          </span>
        </div>

        {/* Icon & Title */}
        <div className="mb-4">
          <span className="text-4xl" role="img" aria-label={title}>
            {icon}
          </span>
          <h3 className="mt-3 text-xl font-semibold text-foreground group-hover:text-primary transition-colors">
            {title}
          </h3>
        </div>

        {/* Description */}
        <p className="text-sm text-muted-foreground leading-relaxed mb-4">
          {description}
        </p>

        {/* Metrics */}
        <div className="grid grid-cols-2 gap-3">
          {metrics.map((metric) => (
            <div key={metric.label} className="text-center p-2 rounded-lg bg-white/60 dark:bg-white/5">
              <p className="text-lg font-bold text-foreground">{metric.value}</p>
              <p className="text-xs text-muted-foreground">{metric.label}</p>
            </div>
          ))}
        </div>

        {/* Arrow */}
        <div className="mt-4 flex items-center text-sm font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">
          Explore domain
          <svg
            className="ml-1 h-4 w-4 transition-transform group-hover:translate-x-1"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </div>
    </Link>
  );
}
