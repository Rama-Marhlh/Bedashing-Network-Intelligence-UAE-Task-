"use client";

import Link from "next/link";
import { MapPinned } from "lucide-react";

import { NAVIGATION_ITEMS, type DashboardSection } from "@/config/navigation";

export function AppHeader({ activeSection }: { activeSection: DashboardSection }) {
  return (
    <header className="app-header">
      <div className="brand-lockup">
        <div className="brand-mark" aria-hidden="true">
          <MapPinned size={20} />
        </div>
        <div>
          <p className="eyebrow">Portfolio intelligence</p>
          <h1>Bedashing Network Intelligence</h1>
          <p className="brand-subtitle">
            AI-Enabled Geospatial Decision Support for Retail Network Right-Sizing
          </p>
        </div>
      </div>
      <nav className="primary-nav" aria-label="Primary navigation">
        {NAVIGATION_ITEMS.map((item) => (
          <Link
            aria-current={item.key === activeSection ? "page" : undefined}
            className={item.key === activeSection ? "nav-link nav-link-active" : "nav-link"}
            href={item.href}
            key={item.key}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
