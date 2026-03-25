import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Card, Button } from "../components/ui";
import { ToastHost, type ToastItem } from "../components/Toast";
import { apiGet } from "../lib/api";
import { newId } from "../lib/id";
import type { DashboardStatus, HealthResponse } from "../lib/types";

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<DashboardStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((title: string, message: string) => {
    setToasts((prev) => [...prev, { id: newId(), title, message }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [h, s] = await Promise.all([
        fetch("/health").then((r) => r.json() as Promise<HealthResponse>),
        apiGet<DashboardStatus>("/dashboard/status")
      ]);
      setHealth(h);
      setStatus(s);
    } catch (e) {
      addToast("Unable to load dashboard", e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const counts = useMemo(() => status?.counts || {}, [status]);
  const cards = useMemo(
    () => [
      { label: "Transactions", value: counts.transactions ?? 0, note: "Total ingested records" },
      { label: "Alerts", value: counts.alerts ?? 0, note: "Open + resolved alerts" },
      { label: "Audit Logs", value: counts.audit_logs ?? 0, note: "Triage actions tracked" }
    ],
    [counts]
  );

  return (
    <>
      <div className="topbar">
        <div>
          <h1 className="pageTitle">Dashboard</h1>
          <p className="pageDesc">
            Operational snapshot for the Anti Money Laundering System. Confirm the API is healthy, the database is
            connected, and your environment is ready for analyst workflow demos.
          </p>
        </div>
        <div className="inline">
          <Button onClick={refresh} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
      </div>

      <div className="grid3">
        {cards.map((c) => (
          <Card key={c.label} title={c.label} hint={c.note}>
            <div style={{ fontSize: 28, fontWeight: 900, letterSpacing: "-0.02em" }}>{c.value}</div>
          </Card>
        ))}
      </div>

      <div style={{ height: 16 }} />

      <div className="grid2">
        <Card
          title="API Health"
          hint="Quick liveness check from the backend server."
          right={
            health ? <span className="pill pillLow">ONLINE</span> : <span className="pill pillHigh">UNKNOWN</span>
          }
        >
          <div className="row">
            <div className="help">Status: {health?.status ?? "—"}</div>
            <div className="help">Version: {health?.version ?? "—"}</div>
            <div className="help">Environment: {health?.env ?? "—"}</div>
          </div>
        </Card>

      </div>

      <ToastHost toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
