"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  { href: "/", label: "Dashboard", icon: "⌂" },
  { href: "/meetings/new", label: "New Meeting", icon: "＋" },
  { href: "/actions", label: "Action Tracker", icon: "☑" },
  { href: "/memory", label: "Memory Search", icon: "⌕" },
  { href: "/chat", label: "AI Meeting Chat", icon: "✦" },
  { href: "/followups", label: "AI Follow-ups", icon: "↗" },
  { href: "/insights", label: "Insights", icon: "◈" },
  { href: "/people", label: "People", icon: "♙" },
  { href: "/reminders", label: "Reminders", icon: "◷" },
];

export default function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="zoom-sidebar">
      <Link href="/" className="zoom-brand">
        <span className="zoom-brand-icon">M</span>
        <span>
          <strong>Meeting Intelligence</strong>
          <small>AI-powered accountability</small>
        </span>
      </Link>

      <div className="sidebar-label">WORKSPACE</div>

      <nav className="sidebar-nav" aria-label="Main navigation">
        {navigation.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href ||
                pathname.startsWith(item.href + "/");

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-item ${active ? "active" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              <span className="nav-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="sidebar-bottom">
        <div className="sidebar-help-icon">?</div>
        <div>
          <strong>Meeting workspace</strong>
          <p>Turn discussions into decisions and actions.</p>
        </div>
      </div>
    </aside>
  );
}
