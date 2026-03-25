import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Card, Button, Input, Select, Textarea, Pill } from "../components/ui";
import { ToastHost, type ToastItem } from "../components/Toast";
import { apiGet, apiSend } from "../lib/api";
import { newId } from "../lib/id";
import type { AlertListOut, AlertOut, AlertUpdate, RiskExplainOut } from "../lib/types";

function pillKindFromSeverity(sev: string | undefined | null) {
  const s = (sev || "").toUpperCase();
  if (s === "LOW") return "low" as const;
  if (s === "MEDIUM") return "medium" as const;
  return "high" as const;
}

export default function AlertsPage() {
  const [list, setList] = useState<AlertListOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(25);
  const [severity, setSeverity] = useState<string>("");
  const [userId, setUserId] = useState<string>("");

  const [selected, setSelected] = useState<AlertOut | null>(null);
  const [explain, setExplain] = useState<RiskExplainOut | null>(null);
  const [updating, setUpdating] = useState(false);

  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const addToast = useCallback((title: string, message: string) => {
    setToasts((prev) => [...prev, { id: newId(), title, message }]);
  }, []);
  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const [updateForm, setUpdateForm] = useState<AlertUpdate>({
    alert_status: "",
    notes: "",
    sar_filed: false,
    false_positive: false
  });

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      const sev = severity.trim();
      const uid = userId.trim();
      if (sev) params.set("severity", sev);
      if (uid) params.set("user_id", uid.toUpperCase());
      params.set("skip", String(skip));
      params.set("limit", String(limit));

      const data = await apiGet<AlertListOut>(`/alerts?${params.toString()}`);
      setList(data);
      if (selected) {
        const found = data.results.find((a) => a.alert_id === selected.alert_id);
        if (found) setSelected(found);
      }
    } catch (e) {
      addToast("Unable to load alerts", e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [severity, userId, skip, limit, selected, addToast]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const rows = useMemo(() => list?.results || [], [list]);

  const selectAlert = useCallback((a: AlertOut) => {
    setSelected(a);
    setExplain(null);
    setUpdateForm({
      alert_status: a.alert_status ?? "",
      notes: a.notes ?? "",
      sar_filed: Boolean(a.sar_filed),
      false_positive: Boolean(a.false_positive)
    });
  }, []);



  const fetchExplain = useCallback(async (alertId: string) => {
    try {
      const data = await apiGet<RiskExplainOut>(`/alerts/${alertId}/explain`);
      setExplain(data);
    } catch {
      setExplain(null);
    }
  }, []);

  useEffect(() => {
    if (selected?.alert_id) void fetchExplain(selected.alert_id);
    else setExplain(null);
  }, [selected?.alert_id, fetchExplain]);
  const save = useCallback(async () => {
    if (!selected) {
      addToast("Select an alert", "Choose an alert from the list before updating.");
      return;
    }

    setUpdating(true);
    try {
      const res = await apiSend<AlertOut>(`/alerts/${selected.alert_id}`, "PATCH", {
        alert_status: updateForm.alert_status || null,
        notes: updateForm.notes || null,
        sar_filed: updateForm.sar_filed ?? null,
        false_positive: updateForm.false_positive ?? null
      });
      setSelected(res);
      addToast("Alert updated", `Alert ${res.alert_id} saved successfully.`);
      void refresh();
    } catch (e) {
      addToast("Update failed", e instanceof Error ? e.message : "Unknown error");
    } finally {
      setUpdating(false);
    }
  }, [selected, updateForm, addToast, refresh]);

  const escalate = useCallback(async () => {
    if (!selected) {
      addToast("Select an alert", "Choose an alert from the list before escalating.");
      return;
    }
    setUpdating(true);
    try {
      const res = await apiSend<AlertOut>(`/alerts/${selected.alert_id}/escalate`, "POST", {});
      setSelected(res);
      addToast("Alert escalated", `Alert ${res.alert_id} escalated.`);
      void refresh();
    } catch (e) {
      addToast("Escalation failed", e instanceof Error ? e.message : "Unknown error");
    } finally {
      setUpdating(false);
    }
  }, [selected, addToast, refresh]);

  return (
    <>
      <div className="topbar">
        <div>
          <h1 className="pageTitle">Alerts</h1>
          <p className="pageDesc">
            Analyst triage console. Filter by severity or user, review context, document investigation notes, and mark
            SAR filings or false positives. Escalation actions are audited in the backend.
          </p>
        </div>
      </div>

      <div className="grid2">
        <Card
          title="Alert Queue"
          hint="Select an alert to review and update it on the right."
          right={
            <div className="inline">
              <Button variant="secondary" onClick={() => setSkip(0)} disabled={loading || skip === 0}>
                First
              </Button>
              <Button
                variant="secondary"
                onClick={() => setSkip((s) => Math.max(0, s - limit))}
                disabled={loading || skip === 0}
              >
                Prev
              </Button>
              <Button
                variant="secondary"
                onClick={() => setSkip((s) => s + limit)}
                disabled={loading || (list ? skip + limit >= list.total : true)}
              >
                Next
              </Button>
            </div>
          }
        >
          <div className="row">
            <div className="grid2">
              <Select
                label="Severity Filter"
                value={severity}
                onChange={(e) => {
                  setSkip(0);
                  setSeverity(e.target.value);
                }}
                help="Focus analyst attention by severity bucket."
              >
                <option value="">All</option>
                <option value="LOW">LOW</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HIGH">HIGH</option>
                <option value="CRITICAL">CRITICAL</option>
              </Select>
              <Input
                label="User Filter"
                value={userId}
                onChange={(e) => {
                  setSkip(0);
                  setUserId(e.target.value.toUpperCase());
                }}
                help="Optional user/customer identifier (filters combine with severity). Example: USR00070."
              />
            </div>

            <div className="inline" style={{ justifyContent: "space-between" }}>
              <div className="help">Total: {list?.total ?? 0}</div>
              <select
                className="select"
                style={{ width: 140 }}
                value={String(limit)}
                onChange={(e) => {
                  setSkip(0);
                  setLimit(Number(e.target.value));
                }}
              >
                <option value="10">10 / page</option>
                <option value="25">25 / page</option>
                <option value="50">50 / page</option>
              </select>
            </div>

            <table className="table" aria-label="Alerts table">
              <thead>
                <tr>
                  <th>Alert</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Txn</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr
                    key={a.alert_id}
                    onClick={() => selectAlert(a)}
                    style={{
                      cursor: "pointer",
                      background: selected?.alert_id === a.alert_id ? "#eef4ff" : undefined
                    }}
                    aria-selected={selected?.alert_id === a.alert_id}
                  >
                    <td style={{ fontWeight: 900 }}>{a.alert_id}</td>
                    <td>
                      <Pill kind={pillKindFromSeverity(a.severity)}>{a.severity || "—"}</Pill>
                    </td>
                    <td>{a.alert_status || "—"}</td>
                    <td>{a.txn_id || "—"}</td>
                  </tr>
                ))}
                {!rows.length ? (
                  <tr>
                    <td colSpan={4} className="help">
                      {loading ? "Loading..." : "No alerts found."}
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </Card>

        <Card
          title="Triage & Update"
          hint="Document investigation notes and update the workflow state."
          right={
            <div className="inline">
              <Button onClick={save} disabled={updating || !selected}>
                {updating ? "Saving..." : "Save"}
              </Button>
              <Button variant="danger" onClick={escalate} disabled={updating || !selected}>
                Escalate
              </Button>
            </div>
          }
        >
          {!selected ? (
            <div className="help">Select an alert from the left panel to begin triage.</div>
          ) : (
            <div className="row">
              <div className="grid2">
                <Input label="Alert ID" value={selected.alert_id} readOnly help="Immutable primary key." />
                <Input
                  label="Transaction ID"
                  value={selected.txn_id ?? ""}
                  readOnly
                  help="Linked transaction (if available)."
                />
              </div>

              <div className="grid2">
                <Input label="Rule" value={selected.alert_rule ?? ""} readOnly help="Rule signature that triggered this alert." />
                <Input label="Analyst" value={selected.assigned_analyst ?? ""} readOnly help="Assigned owner (if set)." />
              </div>

              <div className="grid3">
                <Input label="Rule Score" value={String(selected.rule_score ?? "")} readOnly help="Rule engine score." />
                <Input label="ML Score" value={String(selected.ml_score ?? "")} readOnly help="Model score (if available)." />
                <Input label="Graph Score" value={String(selected.graph_score ?? "")} readOnly help="Network risk signal." />
              </div>


              {explain ? (
                <div className="card" style={{ boxShadow: "none", padding: 12, borderStyle: "dashed" }}>
                  <div className="label" style={{ marginBottom: 6 }}>
                    Explain Risk
                  </div>

                  {explain.breakdown ? (
                    <div className="help">
                      Score breakdown (weight ? score): Rule {explain.breakdown.rule.contribution.toFixed(3)}, ML{" "}
                      {explain.breakdown.ml.contribution.toFixed(3)}, Graph {explain.breakdown.graph.contribution.toFixed(3)}.
                    </div>
                  ) : null}

                  {explain.reasons?.length ? (
                    <ul style={{ margin: 0, paddingLeft: 18, color: "#1f2a44", lineHeight: 1.55 }}>
                      {explain.reasons.map((r) => (
                        <li key={r} style={{ fontSize: 13 }}>
                          {r}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="help">No explanation available.</div>
                  )}

                  {explain.highlights?.length ? (
                    <div className="help" style={{ marginTop: 8 }}>
                      Highlights: {explain.highlights.slice(0, 4).map((h) => `${h.label}: ${h.value}`).join(" | ")}
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="help">Select an alert to load the explanation panel.</div>
              )}

              <div className="grid2">
                <Select
                  label="Alert Status"
                  value={updateForm.alert_status ?? ""}
                  onChange={(e) => setUpdateForm((p) => ({ ...p, alert_status: e.target.value }))}
                  help="Use a consistent set of statuses for reporting."
                >
                  <option value="">(Unchanged)</option>
                  <option value="OPEN">OPEN</option>
                  <option value="IN_REVIEW">IN_REVIEW</option>
                  <option value="RESOLVED">RESOLVED</option>
                  <option value="ESCALATED">ESCALATED</option>
                </Select>
                <Select
                  label="Disposition"
                  value={updateForm.false_positive ? "false_positive" : updateForm.sar_filed ? "sar_filed" : ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    setUpdateForm((p) => ({
                      ...p,
                      sar_filed: v === "sar_filed",
                      false_positive: v === "false_positive"
                    }));
                  }}
                  help="Choose one: SAR filed or false positive."
                >
                  <option value="">None</option>
                  <option value="sar_filed">SAR Filed</option>
                  <option value="false_positive">False Positive</option>
                </Select>
              </div>

              <Textarea
                label="Investigation Notes"
                value={updateForm.notes ?? ""}
                onChange={(e) => setUpdateForm((p) => ({ ...p, notes: e.target.value }))}
                placeholder="Summarize investigation: rationale, evidence, and next steps..."
                help="High-quality notes make audit, handoff, and QA significantly easier."
              />
            </div>
          )}
        </Card>
      </div>

      <ToastHost toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
