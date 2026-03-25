import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Card, Button, Input, Select, Pill } from "../components/ui";
import { ToastHost, type ToastItem } from "../components/Toast";
import { apiGet, apiSend } from "../lib/api";
import { newId } from "../lib/id";
import type {
  TransactionCreate,
  TransactionListOut,
  TransactionOut,
  TransactionScoreIn,
  TransactionScoreOut,
  RiskExplainOut
} from "../lib/types";

function pillKindFromRisk(label: string) {
  const upper = (label || "").toUpperCase();
  if (upper === "LOW") return "low" as const;
  if (upper === "MEDIUM") return "medium" as const;
  return "high" as const;
}

function nowIsoNoMs() {
  const d = new Date();
  d.setMilliseconds(0);
  return d.toISOString();
}

function randomInt(min: number, max: number) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function choose<T>(arr: T[]) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function makeRandomScoreSample(): TransactionScoreIn {
  const normalCountries = ["US", "IN", "GB", "DE", "FR", "SG", "AE", "CA", "AU", "JP"];
  const highRisk = ["IR", "KP", "SY", "MM", "CU", "SD", "RU", "BY", "YE", "LY", "AF", "VE"];
  const channels = ["web", "mobile", "api"];
  const paymentMethods = ["bank_transfer", "card", "wallet", "Crypto", "DeFi", "CEX"];
  const txnTypes = ["p2p", "merchant_payment", "cash_in", "cash_out", "wire"];
  const currencies = ["USD", "EUR", "GBP", "INR", "BTC", "ETH", "USDT"];

  const risky = Math.random() < 0.55;
  const structuring = risky && Math.random() < 0.35;
  const crypto = risky && Math.random() < 0.35;
  const highRiskCountry = risky && Math.random() < 0.28;

  let amount = risky ? randomInt(6000, 24000) : randomInt(25, 5000);
  let recentTxnCount = 0;
  let recentTotalUsd = 0;

  if (structuring) {
    amount = randomInt(4500, 9800);
    recentTxnCount = randomInt(3, 8);
    recentTotalUsd = randomInt(15000, 60000);
  }

  const senderCountry = highRiskCountry ? choose(highRisk) : choose(normalCountries);
  const receiverCountry = highRiskCountry ? choose(highRisk) : choose(normalCountries);

  const isCrossBorder = senderCountry !== receiverCountry ? Math.random() < 0.85 : Math.random() < 0.2;

  const d = new Date();
  d.setMilliseconds(0);
  if (risky && Math.random() < 0.4) {
    d.setUTCHours(choose([0, 1, 2, 3, 23]), randomInt(0, 59), 0, 0);
  } else {
    d.setUTCHours(randomInt(8, 20), randomInt(0, 59), 0, 0);
  }

  const paymentMethod = crypto ? choose(["Crypto", "DeFi", "CEX"]) : choose(paymentMethods);
  const currency = crypto ? choose(["BTC", "ETH", "USDT"]) : choose(currencies);

  return {
    amount_usd: amount,
    currency,
    payment_method: paymentMethod,
    txn_type: choose(txnTypes),
    timestamp: d.toISOString(),
    is_cross_border: isCrossBorder,
    sender_country: senderCountry,
    receiver_country: receiverCountry,
    ip_country: choose(normalCountries),
    channel: choose(channels),
    pep_involved: risky && Math.random() < 0.12,
    dormant_days: risky && Math.random() < 0.15 ? randomInt(365, 1500) : 0,
    recent_txn_count: recentTxnCount,
    recent_total_usd: recentTotalUsd,
    graph_score: Math.round((risky ? Math.random() * 0.55 : Math.random() * 0.25) * 100) / 100
  };
}

export default function TransactionsPage() {
  const [list, setList] = useState<TransactionListOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(25);

  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<TransactionOut | null>(null);
  const [createdExplain, setCreatedExplain] = useState<RiskExplainOut | null>(null);
  const [asyncTaskId, setAsyncTaskId] = useState<string | null>(null);
  const [asyncTaskStatus, setAsyncTaskStatus] = useState<Record<string, unknown> | null>(null);

  const [scoring, setScoring] = useState(false);
  const [scoreResult, setScoreResult] = useState<TransactionScoreOut | null>(null);
  const [batch, setBatch] = useState<Array<{ input: TransactionScoreIn; output: TransactionScoreOut }>>([]);

  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const addToast = useCallback((title: string, message: string) => {
    setToasts((prev) => [...prev, { id: newId(), title, message }]);
  }, []);
  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const [form, setForm] = useState<TransactionCreate>({
    txn_id: `TXN-${Math.floor(Math.random() * 900000 + 100000)}`,
    sender_id: "S-1001",
    receiver_id: "R-2001",
    amount_usd: 1250,
    amount_local: 1250,
    currency: "USD",
    fx_rate_to_usd: 1.0,
    payment_method: "bank_transfer",
    txn_type: "p2p",
    timestamp: nowIsoNoMs(),
    is_cross_border: false,
    sender_country: "US",
    receiver_country: "US",
    device_fingerprint: "",
    ip_country: "US",
    channel: "web"
  });

  const [scoreForm, setScoreForm] = useState<TransactionScoreIn>(() => ({
    amount_usd: 2500,
    currency: "USD",
    payment_method: "bank_transfer",
    txn_type: "p2p",
    timestamp: nowIsoNoMs(),
    is_cross_border: false,
    sender_country: "US",
    receiver_country: "US",
    ip_country: "US",
    channel: "web",
    pep_involved: false,
    dormant_days: 0,
    recent_txn_count: 0,
    recent_total_usd: 0,
    graph_score: 0
  }));

  const total = list?.total ?? 0;
  const canPrev = skip > 0;
  const canNext = skip + limit < total;

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiGet<TransactionListOut>(`/transactions?skip=${skip}&limit=${limit}`);
      setList(data);
    } catch (e) {
      addToast("Unable to load transactions", e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [skip, limit, addToast]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const rows = useMemo(() => list?.results || [], [list]);

  const submit = useCallback(async () => {
    setCreating(true);
    setCreated(null);
    setCreatedExplain(null);
    setAsyncTaskId(null);
    setAsyncTaskStatus(null);
    try {
      const payload: TransactionCreate = {
        ...form,
        amount_usd: Number(form.amount_usd),
        amount_local: Number(form.amount_local),
        fx_rate_to_usd: Number(form.fx_rate_to_usd),
        is_cross_border: Boolean(form.is_cross_border),
        timestamp: new Date(form.timestamp).toISOString()
      };
      const res = await apiSend<TransactionOut>("/transactions", "POST", payload);
      setCreated(res);
      try {
        const ex = await apiGet<RiskExplainOut>(`/transactions/${res.txn_id}/explain`);
        setCreatedExplain(ex);
      } catch {
        setCreatedExplain(null);
      }
      addToast("Transaction ingested", `Risk ${res.risk_label} - Score ${res.composite_risk_score.toFixed(3)}`);
      void refresh();
    } catch (e) {
      addToast("Create failed", e instanceof Error ? e.message : "Unknown error");
    } finally {
      setCreating(false);
    }
  }, [form, addToast, refresh]);



  const submitAsync = useCallback(async () => {
    setCreating(true);
    setCreated(null);
    setCreatedExplain(null);
    setAsyncTaskStatus(null);
    try {
      const payload: TransactionCreate = {
        ...form,
        amount_usd: Number(form.amount_usd),
        amount_local: Number(form.amount_local),
        fx_rate_to_usd: Number(form.fx_rate_to_usd),
        is_cross_border: Boolean(form.is_cross_border),
        timestamp: new Date(form.timestamp).toISOString()
      };
      const res = await apiSend<{ ok: boolean; task_id: string }>("/transactions/async", "POST", payload);
      setAsyncTaskId(res.task_id);
      addToast("Queued", `Background task started: ${res.task_id}`);
    } catch (e) {
      addToast("Queue failed", e instanceof Error ? e.message : "Unknown error");
    } finally {
      setCreating(false);
    }
  }, [form, addToast]);

  const checkAsyncTask = useCallback(async () => {
    if (!asyncTaskId) return;
    try {
      const res = await apiGet<Record<string, unknown>>(`/transactions/tasks/${asyncTaskId}`);
      setAsyncTaskStatus(res);

      const state = String((res as any).state || "");
      const result = (res as any).result as any;

      if (state === "SUCCESS") {
        addToast("Task complete", "Transaction ingested in background.");
        const txnId = result && typeof result === "object" ? String(result.txn_id || "") : "";
        if (txnId) {
          try {
            const txn = await apiGet<TransactionOut>(`/transactions/${txnId}`);
            setCreated(txn);
            try {
              const ex = await apiGet<RiskExplainOut>(`/transactions/${txnId}/explain`);
              setCreatedExplain(ex);
            } catch {
              setCreatedExplain(null);
            }
          } catch {
            // ignore
          }
        }
        void refresh();
      }
      if (state === "FAILURE") addToast("Task failed", String((res as any).error || "Unknown error"));
    } catch (e) {
      addToast("Check failed", e instanceof Error ? e.message : "Unknown error");
    }
  }, [asyncTaskId, addToast, refresh]);
  const score = useCallback(async () => {
    setScoring(true);
    setScoreResult(null);
    try {
      const payload: TransactionScoreIn = {
        ...scoreForm,
        amount_usd: Number(scoreForm.amount_usd),
        dormant_days: Number(scoreForm.dormant_days),
        recent_txn_count: Number(scoreForm.recent_txn_count),
        recent_total_usd: Number(scoreForm.recent_total_usd),
        graph_score: Number(scoreForm.graph_score),
        is_cross_border: Boolean(scoreForm.is_cross_border),
        pep_involved: Boolean(scoreForm.pep_involved),
        timestamp: scoreForm.timestamp ? new Date(scoreForm.timestamp).toISOString() : undefined
      };
      const res = await apiSend<TransactionScoreOut>("/transactions/score", "POST", payload);
      setScoreResult(res);
      if (res.alert_recommended) {
        addToast(
          "AML alert recommended",
          `${res.severity || res.risk_label} - Score ${res.composite_risk_score.toFixed(3)}`
        );
      } else {
        addToast("Risk check complete", `${res.risk_label} - Score ${res.composite_risk_score.toFixed(3)}`);
      }
    } catch (e) {
      addToast("Score failed", e instanceof Error ? e.message : "Unknown error");
    } finally {
      setScoring(false);
    }
  }, [scoreForm, addToast]);

  const runBatch = useCallback(
    async (n: number) => {
      setScoring(true);
      setScoreResult(null);
      setBatch([]);
      try {
        const items: Array<{ input: TransactionScoreIn; output: TransactionScoreOut }> = [];
        let alerts = 0;
        for (let i = 0; i < n; i++) {
          const input = makeRandomScoreSample();
          const payload: TransactionScoreIn = {
            ...input,
            amount_usd: Number(input.amount_usd),
            dormant_days: Number(input.dormant_days),
            recent_txn_count: Number(input.recent_txn_count),
            recent_total_usd: Number(input.recent_total_usd),
            graph_score: Number(input.graph_score),
            is_cross_border: Boolean(input.is_cross_border),
            pep_involved: Boolean(input.pep_involved),
            timestamp: input.timestamp ? new Date(input.timestamp).toISOString() : undefined
          };
          const output = await apiSend<TransactionScoreOut>("/transactions/score", "POST", payload);
          if (output.alert_recommended) alerts += 1;
          items.push({ input, output });
        }
        setBatch(items);
        addToast("Batch simulation complete", `${alerts}/${n} recommended an alert`);
      } catch (e) {
        addToast("Batch failed", e instanceof Error ? e.message : "Unknown error");
      } finally {
        setScoring(false);
      }
    },
    [addToast]
  );

  return (
    <>
      <div className="topbar">
        <div>
          <h1 className="pageTitle">Transactions</h1>
          <p className="pageDesc">
            Simulate random user transfers with a quick risk check (no IDs, no database write), or ingest a transaction
            to generate alerts in the backend.
          </p>
        </div>
      </div>

      <div className="grid2">
        <Card
          title="Quick Risk Check (No IDs)"
          hint="Runs rule + ML scoring and returns an alert recommendation with reasons."
          right={
            <div className="inline">
              <Button
                variant="secondary"
                onClick={() => {
                  setScoreResult(null);
                  setScoreForm(makeRandomScoreSample());
                  setBatch([]);
                }}
              >
                Generate Random
              </Button>
              <Button variant="secondary" onClick={() => runBatch(10)} disabled={scoring}>
                Run 10 Random
              </Button>
              <Button onClick={score} disabled={scoring}>
                {scoring ? "Scoring..." : "Score"}
              </Button>
            </div>
          }
        >
          <div className="row">
            <div className="grid2">
              <Input
                label="Amount (USD)"
                type="number"
                min={0}
                step="0.01"
                value={String(scoreForm.amount_usd)}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setScoreForm((p) => ({ ...p, amount_usd: Number.isFinite(v) ? Math.max(0, v) : 0 }));
                }}
                help="Higher amounts often increase risk."
              />
              <Input
                label="Timestamp (ISO)"
                value={scoreForm.timestamp || ""}
                onChange={(e) => setScoreForm((p) => ({ ...p, timestamp: e.target.value }))}
                help="Example: 2026-03-24T12:30:00Z"
              />
            </div>

            <div className="grid2">
              <Input
                label="Currency"
                value={scoreForm.currency}
                onChange={(e) => setScoreForm((p) => ({ ...p, currency: e.target.value.toUpperCase() }))}
                help="Supports fiat and crypto codes."
              />
              <Input
                label="Payment Method"
                value={scoreForm.payment_method ?? ""}
                onChange={(e) => setScoreForm((p) => ({ ...p, payment_method: e.target.value }))}
                help="Try Crypto / DeFi / CEX to trigger crypto rule."
              />
            </div>

            <div className="grid2">
              <Input
                label="Sender Country"
                value={scoreForm.sender_country ?? ""}
                onChange={(e) => setScoreForm((p) => ({ ...p, sender_country: e.target.value.toUpperCase() }))}
                help="Two-letter code (e.g., US, IN)."
              />
              <Input
                label="Receiver Country"
                value={scoreForm.receiver_country ?? ""}
                onChange={(e) => setScoreForm((p) => ({ ...p, receiver_country: e.target.value.toUpperCase() }))}
                help="Two-letter code (e.g., US, IN)."
              />
            </div>

            <div className="grid2">
              <Select
                label="Cross Border"
                value={scoreForm.is_cross_border ? "yes" : "no"}
                onChange={(e) => setScoreForm((p) => ({ ...p, is_cross_border: e.target.value === "yes" }))}
                help="Cross-border transfers can increase risk."
              >
                <option value="no">No</option>
                <option value="yes">Yes</option>
              </Select>
              <Select
                label="PEP Involved"
                value={scoreForm.pep_involved ? "yes" : "no"}
                onChange={(e) => setScoreForm((p) => ({ ...p, pep_involved: e.target.value === "yes" }))}
                help="Simulated PEP signal (no ID lookup)."
              >
                <option value="no">No</option>
                <option value="yes">Yes</option>
              </Select>
            </div>

            <div className="grid3">
              <Input
                label="Dormant Days"
                type="number"
                min={0}
                step="1"
                value={String(scoreForm.dormant_days)}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  const n = Number.isFinite(v) ? Math.max(0, Math.trunc(v)) : 0;
                  setScoreForm((p) => ({ ...p, dormant_days: n }));
                }}
                help=">=365 with high amount can trigger dormant rule."
              />
              <Input
                label="Recent Txn Count"
                type="number"
                min={0}
                step="1"
                value={String(scoreForm.recent_txn_count)}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  const n = Number.isFinite(v) ? Math.max(0, Math.trunc(v)) : 0;
                  setScoreForm((p) => ({ ...p, recent_txn_count: n }));
                }}
                help="Simulate structuring patterns."
              />
              <Input
                label="Graph Score (0-1)"
                type="number"
                min={0}
                max={1}
                step="0.01"
                value={String(scoreForm.graph_score)}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  const n = Number.isFinite(v) ? Math.min(1, Math.max(0, v)) : 0;
                  setScoreForm((p) => ({ ...p, graph_score: n }));
                }}
                help="Optional network-risk signal."
              />
            </div>

            {scoreResult ? (
              <div className="row">
                <div className="inline" style={{ justifyContent: "space-between" }}>
                  <div className="help">
                    Composite <b>{scoreResult.composite_risk_score.toFixed(4)}</b> - Rule{" "}
                    {scoreResult.rule_score.toFixed(4)} - ML {scoreResult.ml_score.toFixed(4)} - Graph{" "}
                    {scoreResult.graph_score.toFixed(4)}
                  </div>
                  <Pill kind={pillKindFromRisk(scoreResult.risk_label)}>
                    {scoreResult.alert_recommended
                      ? `${scoreResult.severity || scoreResult.risk_label} ALERT`
                      : scoreResult.risk_label}
                  </Pill>
                </div>

                {scoreResult.ml_model_loaded === false ? (
                  <div className="help">
                    Note: ML model is not loaded. Composite score is computed using rules (and graph if provided).
                  </div>
                ) : null}

                {scoreResult.is_cross_border_used !== undefined ? (
                  <div className="help">Cross-border used: {scoreResult.is_cross_border_used ? "Yes" : "No"}</div>
                ) : null}

                {scoreResult.data_warnings?.length ? (
                  <div className="card" style={{ boxShadow: "none", padding: 12, borderStyle: "dashed" }}>
                    <div className="label" style={{ marginBottom: 6 }}>
                      Data warnings
                    </div>
                    <ul style={{ margin: 0, paddingLeft: 18, color: "#1f2a44", lineHeight: 1.55 }}>
                      {scoreResult.data_warnings.map((w) => (
                        <li key={w} style={{ fontSize: 13 }}>
                          {w}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <div className="card" style={{ boxShadow: "none", padding: 12 }}>
                  <div className="label" style={{ marginBottom: 6 }}>
                    Reasons
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, color: "#1f2a44", lineHeight: 1.55 }}>
                    {(scoreResult.reasons || []).map((r) => (
                      <li key={r} style={{ fontSize: 13 }}>
                        {r}
                      </li>
                    ))}
                  </ul>
                  {scoreResult.triggered_rules?.length ? (
                    <div className="help" style={{ marginTop: 8 }}>
                      Triggered rules: {scoreResult.triggered_rules.join(", ")}
                    </div>
                  ) : null}
                </div>
              </div>
            ) : (
              <div className="help">Tip: click Generate Random a few times and score to see different alert reasons.</div>
            )}

            {batch.length ? (
              <div className="row">
                <div className="label">Batch results</div>
                <table className="table" aria-label="Batch simulation table">
                  <thead>
                    <tr>
                      <th>Amount</th>
                      <th>Countries</th>
                      <th>Risk</th>
                      <th>Score</th>
                      <th>Top reasons</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batch.map((b, idx) => (
                      <tr key={idx}>
                        <td>${Number(b.input.amount_usd).toFixed(0)}</td>
                        <td>
                          {(b.input.sender_country || "—").toUpperCase()}→{(b.input.receiver_country || "—").toUpperCase()}
                        </td>
                        <td>
                          <Pill kind={pillKindFromRisk(b.output.risk_label)}>
                            {b.output.alert_recommended ? `${b.output.severity || b.output.risk_label}` : b.output.risk_label}
                          </Pill>
                        </td>
                        <td>{b.output.composite_risk_score.toFixed(3)}</td>
                        <td className="help">{(b.output.reasons || []).slice(0, 2).join(" | ") || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        </Card>

        <Card
          title="Ingest Transaction (DB)"
          hint="Persists the transaction and may create an alert in the backend."
          right={
            <div className="inline">
              <Button onClick={submit} disabled={creating}>
                {creating ? "Submitting..." : "Submit"}
              </Button>
              <Button variant="secondary" onClick={submitAsync} disabled={creating}>
                Submit Async
              </Button>
              <Button variant="secondary" onClick={checkAsyncTask} disabled={!asyncTaskId}>
                Check Task
              </Button>
            </div>
          }
        >
          <div className="row">
            <div className="grid2">
              <Input
                label="Transaction ID"
                value={form.txn_id}
                onChange={(e) => setForm((p) => ({ ...p, txn_id: e.target.value }))}
                help="Unique external reference for traceability."
              />
              <Input
                label="Timestamp (ISO)"
                value={form.timestamp}
                onChange={(e) => setForm((p) => ({ ...p, timestamp: e.target.value }))}
                help="Example: 2026-03-24T12:30:00Z"
              />
            </div>

            <div className="grid2">
              <Input
                label="Sender ID"
                value={form.sender_id}
                onChange={(e) => setForm((p) => ({ ...p, sender_id: e.target.value }))}
                help="Customer/account initiating the transfer."
              />
              <Input
                label="Receiver ID"
                value={form.receiver_id}
                onChange={(e) => setForm((p) => ({ ...p, receiver_id: e.target.value }))}
                help="Beneficiary/customer receiving funds."
              />
            </div>

            <div className="grid2">
              <Input
                label="Amount (USD)"
                type="number"
                min={0}
                step="0.01"
                value={String(form.amount_usd)}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setForm((p) => ({ ...p, amount_usd: Number.isFinite(v) ? Math.max(0, v) : 0 }));
                }}
                help="Used by thresholds and scoring."
              />
              <Input
                label="Amount (Local)"
                type="number"
                min={0}
                step="0.01"
                value={String(form.amount_local)}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setForm((p) => ({ ...p, amount_local: Number.isFinite(v) ? Math.max(0, v) : 0 }));
                }}
                help="Captured for reporting; USD is used for scoring."
              />
            </div>

            <div className="grid2">
              <Input
                label="Currency"
                value={form.currency}
                onChange={(e) => setForm((p) => ({ ...p, currency: e.target.value.toUpperCase() }))}
                help="ISO currency code (e.g., USD, EUR)."
              />
              <Input
                label="FX Rate to USD"
                type="number"
                min={0}
                step="0.0001"
                value={String(form.fx_rate_to_usd)}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setForm((p) => ({ ...p, fx_rate_to_usd: Number.isFinite(v) ? Math.max(0, v) : 0 }));
                }}
                help="Local * FX = USD."
              />
            </div>

            <div className="grid2">
              <Input
                label="Payment Method"
                value={form.payment_method ?? ""}
                onChange={(e) => setForm((p) => ({ ...p, payment_method: e.target.value }))}
                help="e.g., bank_transfer, card, crypto_exchange."
              />
              <Input
                label="Transaction Type"
                value={form.txn_type ?? ""}
                onChange={(e) => setForm((p) => ({ ...p, txn_type: e.target.value }))}
                help="e.g., p2p, merchant_payment, cash_in."
              />
            </div>

            <div className="grid2">
              <Select
                label="Cross Border"
                value={form.is_cross_border ? "yes" : "no"}
                onChange={(e) => setForm((p) => ({ ...p, is_cross_border: e.target.value === "yes" }))}
                help="Cross-border flows are typically higher risk."
              >
                <option value="no">No</option>
                <option value="yes">Yes</option>
              </Select>
              <Input
                label="Channel"
                value={form.channel ?? ""}
                onChange={(e) => setForm((p) => ({ ...p, channel: e.target.value }))}
                help="e.g., web, mobile, api."
              />
            </div>

            <div className="grid2">
              <Input
                label="Sender Country"
                value={form.sender_country ?? ""}
                onChange={(e) => setForm((p) => ({ ...p, sender_country: e.target.value.toUpperCase() }))}
                help="Two-letter code (e.g., US, IN)."
              />
              <Input
                label="Receiver Country"
                value={form.receiver_country ?? ""}
                onChange={(e) => setForm((p) => ({ ...p, receiver_country: e.target.value.toUpperCase() }))}
                help="Two-letter code (e.g., US, IN)."
              />
            </div>

            <div className="grid2">
              <Input
                label="IP Country"
                value={form.ip_country ?? ""}
                onChange={(e) => setForm((p) => ({ ...p, ip_country: e.target.value.toUpperCase() }))}
                help="Derived from request IP geo."
              />
              <Input
                label="Device Fingerprint"
                value={form.device_fingerprint ?? ""}
                onChange={(e) => setForm((p) => ({ ...p, device_fingerprint: e.target.value }))}
                help="Optional device identifier to link sessions."
              />
            </div>

            {created ? (
              <div className="inline" style={{ justifyContent: "space-between" }}>
                <div className="help">
                  Created: <b>{created.txn_id}</b> - {created.sender_id} {"->"} {created.receiver_id} - $
                  {created.amount_usd}
                </div>
                <Pill kind={pillKindFromRisk(created.risk_label)}>{created.risk_label}</Pill>
              </div>
            ) : null}

            {created ? (
              <div className="card" style={{ boxShadow: "none", padding: 12, borderStyle: "dashed" }}>
                <div className="label" style={{ marginBottom: 6 }}>
                  Explain Risk
                </div>

                {createdExplain?.breakdown ? (
                  <div className="help">
                    Score breakdown (weight * score): Rule {createdExplain.breakdown.rule.contribution.toFixed(3)}, ML{" "}
                    {createdExplain.breakdown.ml.contribution.toFixed(3)}, Graph {createdExplain.breakdown.graph.contribution.toFixed(3)}.
                  </div>
                ) : null}

                {createdExplain?.triggered_rules?.length ? (
                  <div className="help" style={{ marginTop: 6 }}>
                    Triggered rules: {createdExplain.triggered_rules.join(", ")}
                  </div>
                ) : null}

                {createdExplain?.reasons?.length ? (
                  <ul style={{ margin: 0, paddingLeft: 18, color: "#1f2a44", lineHeight: 1.55 }}>
                    {createdExplain.reasons.map((r) => (
                      <li key={r} style={{ fontSize: 13 }}>
                        {r}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="help">No explanation available for this transaction.</div>
                )}

                {createdExplain?.highlights?.length ? (
                  <div className="help" style={{ marginTop: 8 }}>
                    Highlights: {createdExplain.highlights.slice(0, 4).map((h) => `${h.label}: ${h.value}`).join(" | ")}
                  </div>
                ) : null}
              </div>
            ) : null}

            {asyncTaskId ? (
              <div className="card" style={{ boxShadow: "none", padding: 12, borderStyle: "dashed" }}>
                <div className="label" style={{ marginBottom: 6 }}>
                  Background Task
                </div>
                <div className="help">Task ID: {asyncTaskId}</div>
                <div className="help">State: {String((asyncTaskStatus as any)?.state || "PENDING")}</div>
                {(asyncTaskStatus as any)?.result && typeof (asyncTaskStatus as any).result === "object" ? (
                  <div className="help" style={{ marginTop: 6 }}>
                    Result: txn {String(((asyncTaskStatus as any).result as any).txn_id || "-")}
                    {((asyncTaskStatus as any).result as any).alert_id ? ` | alert ${String(((asyncTaskStatus as any).result as any).alert_id)}` : ""}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </Card>
      </div>

      <div style={{ height: 16 }} />

      <Card
        title="Recent Transactions"
        hint="Browse persisted transactions. Risk labels are computed by the backend."
        right={
          <div className="inline">
            <Button variant="secondary" onClick={() => setSkip(0)} disabled={loading || skip === 0}>
              First
            </Button>
            <Button
              variant="secondary"
              onClick={() => setSkip((s) => Math.max(0, s - limit))}
              disabled={loading || !canPrev}
            >
              Prev
            </Button>
            <Button variant="secondary" onClick={() => setSkip((s) => s + limit)} disabled={loading || !canNext}>
              Next
            </Button>
          </div>
        }
      >
        <div className="row">
          <div className="inline" style={{ justifyContent: "space-between" }}>
            <div className="help">
              Showing {Math.min(skip + 1, total)}-{Math.min(skip + limit, total)} of {total}
            </div>
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

          <table className="table" aria-label="Transactions table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Sender</th>
                <th>Receiver</th>
                <th>Amount (USD)</th>
                <th>Risk</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.txn_id}>
                  <td style={{ fontWeight: 800 }}>{t.txn_id}</td>
                  <td>{t.sender_id}</td>
                  <td>{t.receiver_id}</td>
                  <td>${t.amount_usd.toFixed(2)}</td>
                  <td>
                    <Pill kind={pillKindFromRisk(t.risk_label)}>{t.risk_label}</Pill>
                  </td>
                  <td>{Number(t.composite_risk_score ?? 0).toFixed(3)}</td>
                </tr>
              ))}
              {!rows.length ? (
                <tr>
                  <td colSpan={6} className="help">
                    {loading ? "Loading..." : "No transactions found."}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </Card>

      <ToastHost toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
