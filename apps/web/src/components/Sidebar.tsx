"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  label: string;
  href: string;
  icon: string;
  domain: string;
}

const navItems: NavItem[] = [
  { label: "Overview", href: "/dashboard", icon: "📊", domain: "overview" },
  { label: "Climate", href: "/dashboard/climate", icon: "🌡️", domain: "climate" },
  { label: "Biodiversity", href: "/dashboard/biodiversity", icon: "🦎", domain: "biodiversity" },
  { label: "Public Health", href: "/dashboard/health", icon: "🏥", domain: "health" },
  { label: "Food Security", href: "/dashboard/food-security", icon: "🌾", domain: "food-security" },
  { label: "Resources", href: "/dashboard/resources", icon: "💧", domain: "resources" },
];

const domainColors: Record<string, string> = {
  overview: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
  climate: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  biodiversity: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  health: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  "food-security": "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  resources: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
};

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 shrink-0 border-r border-border bg-card hidden lg:flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-border">
        <Link href="/" className="flex items-center gap-2.5 group">
          <span className="text-2xl">🌍</span>
          <div>
            <h1 className="text-lg font-bold text-foreground tracking-tight group-hover:text-primary transition-colors">
              EcoTrack
            </h1>
            <p className="text-[10px] text-muted-foreground -mt-0.5">
              Planetary Intelligence
            </p>
          </div>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <p className="px-3 mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Domains
        </p>
        {navItems.map((item) => {
          const isActive =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname?.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? domainColors[item.domain]
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Bottom section */}
      <div className="border-t border-border px-4 py-4 space-y-1">
        <Link
          href="/dashboard"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-all"
        >
          <span>⚙️</span> Settings
        </Link>
        <Link
          href="/"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-all"
        >
          <span>📖</span> API Docs
        </Link>
      </div>
    </aside>
  );
}
