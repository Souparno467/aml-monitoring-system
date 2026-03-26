import React from "react";
import { NavLink, useLocation } from "react-router-dom";

const nav = [
  { to: "/dashboard", label: "Dashboard", meta: "Status & totals" },
  { to: "/transactions", label: "Transactions", meta: "Ingest & review" },
  { to: "/alerts", label: "Alerts", meta: "Triage workflow" },
  { to: "/risk", label: "Risk", meta: "Model insights" }
];

function navClass(isActive: boolean) {
  return `navItem ${isActive ? "navItemActive" : ""}`.trim();
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  return (
    <div className="appShell">
      <aside className="sidebar">
        <div className="brand">
          <div>
            <div className="brandTitle">Anti Money Laundering System</div>
            <div className="brandSubtitle">Analyst Console (Light Theme)</div>
          </div>
        </div>

        <nav className="nav" aria-label="Primary">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => navClass(isActive)}
              aria-current={location.pathname === item.to ? "page" : undefined}
            >
              <span>{item.label}</span>
              <span className="navMeta">{item.meta}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="main">{children}</main>
    </div>
  );
}
