import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Card, Button, Input, Select } from "../components/ui";
import { ToastHost, type ToastItem } from "../components/Toast";
import { apiGet, apiSend } from "../lib/api";
import { newId } from "../lib/id";
import type { RiskEvaluateIn, RiskEvaluateOut, RiskModelInfoOut, RiskTrainOut } from "../lib/types";

export default function RiskPage() {
  const [model, setModel] = useState<RiskModelInfoOut | null>(null);
  const [trainOut, setTrainOut] = useState<RiskTrainOut | null>(null);
  const [evalOut, setEvalOut] = useState<RiskEvaluateOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [trainMaxRows, setTrainMaxRows] = useState(200000);
  const [trainTestSize, setTrainTestSize] = useState(0.2);
  const [trainRandomState, setTrainRandomState] = useState(42);

  const [evalMaxRows, setEvalMaxRows] = useState(50000);
  const [evalTopN, setEvalTopN] = useState(20);
  const [evalSplitStrategy, setEvalSplitStrategy] = useState<"time" | "random" | "none">("time");
  const [evalTestSize, setEvalTestSize] = useState(0.2);
  const [evalRandomState, setEvalRandomState] = useState(42);

  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const addToast = useCallback((title: string, message: string) => {
    setToasts((prev) => [...prev, { id: newId(), title, message }]);
  }, []);
  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const info = await apiGet<RiskModelInfoOut>("/risk/model");
      setModel(info);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setModel(null);
      setLoadError(msg);
      addToast("Unable to load model info", msg);
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const train = useCallback(async () => {
    setLoading(true);
    setTrainOut(null);
    try {
      const out = await apiSend<RiskTrainOut>("/risk/model/train", "POST", {
        max_rows: Number(trainMaxRows),
        test_size: Number(trainTestSize),
        random_state: Number(trainRandomState)
      });
      setTrainOut(out);
      addToast("Training complete", `Model: ${out.model}`);
      void refresh();
    } catch (e) {
      addToast("Training failed", e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [trainMaxRows, trainTestSize, trainRandomState, addToast, refresh]);

  const resetModel = useCallback(async () => {
    setTrainMaxRows(200000);
    setTrainTestSize(0.2);
    setTrainRandomState(42);
    setLoading(true);
    setTrainOut(null);
    try {
      const out = await apiSend<RiskTrainOut>("/risk/model/reset", "POST", {});
      setTrainOut(out);
      addToast("Model reset", "Re-trained model with default settings.");
      void refresh();
    } catch (e) {
      addToast("Reset failed", e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [addToast, refresh]);

  const resetEval = useCallback(() => {
    setEvalMaxRows(50000);
    setEvalTopN(20);
    setEvalSplitStrategy("time");
    setEvalTestSize(0.2);
    setEvalRandomState(42);
    setEvalOut(null);
    addToast("Evaluation reset", "Restored default evaluation settings.");
  }, [addToast]);

  const evaluate = useCallback(async () => {
    setLoading(true);
    setEvalOut(null);
    try {
      const body: RiskEvaluateIn = {
        max_rows: Number(evalMaxRows),
        top_n: Number(evalTopN),
        split_strategy: String(evalSplitStrategy),
        test_size: Number(evalTestSize),
        random_state: Number(evalRandomState),
      };
      const out = await apiSend<RiskEvaluateOut>("/risk/evaluate", "POST", body);
      setEvalOut(out);
      addToast("Evaluation complete", `Rows: ${out.rows} | Positives: ${out.positives}`);
    } catch (e) {
      addToast("Evaluation failed", e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [evalMaxRows, evalTopN, evalSplitStrategy, evalTestSize, evalRandomState, addToast]);

  const canAdmin = Boolean(model?.debug);

  const featurePreview = useMemo(() => {
    const f = model?.feature_names || [];
    if (!f.length) return "—";
    return f.slice(0, 10).join(", ") + (f.length > 10 ? ` (+${f.length - 10} more)` : "");
  }, [model]);

  return (
    <>
      <div className="topbar">
        <div>
          <h1 className="pageTitle">Risk</h1>
          <p className="pageDesc">
            Model visibility for AML scoring. In DEBUG mode the backend exposes training and evaluation endpoints. In a
            production deployment these endpoints are typically disabled or protected.
          </p>
        </div>
      </div>

      <div className="grid2">
        <Card
          title="Model Info"
          hint="Loaded status and feature metadata from the backend."
          right={
            <div className="inline">
              <Button onClick={refresh} disabled={loading}>
                Refresh
              </Button>
            </div>
          }
        >
          <div className="row">
            {loadError ? <div className="help">Error: {loadError}</div> : null}
            <div className="help">Loaded: {model ? (model.loaded ? "Yes" : "No") : "—"}</div>
            <div className="help">Type: {model?.model_type ?? "—"}</div>
            <div className="help">Features: {featurePreview}</div>
            {model?.load_error ? <div className="help">Load error: {model.load_error}</div> : null}
            {!canAdmin ? (
              <div className="help">Training/evaluation is disabled in production (DEBUG=false).</div>
            ) : null}
          </div>
        </Card>

        {canAdmin ? (
          <Card
            title="Train (DEBUG)"
          hint="Builds a fresh model from the demo CSV. Returns metrics and saved model reference."
          right={
            <div className="inline">
              <Button onClick={train} disabled={loading}>
                Train
              </Button>
              <Button variant="secondary" onClick={resetModel} disabled={loading}>
                Reset
              </Button>
            </div>
          }
        >
          <div className="row">
            <div className="grid3">
              <Input
                label="Max Rows"
                type="number"
                min={1000}
                max={5000000}
                step="1000"
                value={String(trainMaxRows)}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  const n = Number.isFinite(v) ? Math.max(1000, Math.trunc(v)) : 1000;
                  setTrainMaxRows(n);
                }}
                help="Upper bound on dataset size."
              />
              <Input
                label="Test Size"
                type="number"
                min={0.05}
                max={0.5}
                step="0.01"
                value={String(trainTestSize)}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  const n = Number.isFinite(v) ? Math.min(0.5, Math.max(0.05, v)) : 0.2;
                  setTrainTestSize(n);
                }}
                help="Holdout fraction (0.05–0.5)."
              />
              <Input
                label="Random State"
                type="number"
                min={0}
                step="1"
                value={String(trainRandomState)}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  const n = Number.isFinite(v) ? Math.max(0, Math.trunc(v)) : 0;
                  setTrainRandomState(n);
                }}
                help="Reproducible split seed."
              />
            </div>

            {trainOut ? (
              <div className="row">
                <div className="help">
                  Trained on {trainOut.rows.toLocaleString()} transactions with {trainOut.positives.toLocaleString()} known
                  suspicious cases ({(trainOut.prevalence * 100).toFixed(2)}%).
                </div>
                <div className="help">
                  Split: {trainOut.split_strategy || "time"}
                  {trainOut.cutoff_timestamp ? ` (cutoff: ${trainOut.cutoff_timestamp})` : ""}.
                </div>
                <div className="help">
                  Model quality (holdout test): ROC-AUC {trainOut.ml.roc_auc?.toFixed(3) ?? "N/A"} (higher is better;
                  0.50 = random) and Average Precision {trainOut.ml.average_precision?.toFixed(3) ?? "N/A"} (better for rare
                  events like SAR filings).
                </div>
                <div className="help">
                  What the model looks at: amount, time-of-day/week, cross-border flag, rule triggers (large/high-risk/pep/structuring/etc.),
                  graph score, and basic transaction metadata (currency, method, countries, channel).
                </div>
              </div>
            ) : (
              <div className="help">Training output appears here after a successful run.</div>
            )}
          </div>
        </Card>
        ) : null}
      </div>

      <div style={{ height: 16 }} />

      {canAdmin ? (
        <Card
          title="Evaluate (DEBUG)"
        hint="Computes ROC-AUC and Average Precision for ML and composite scoring."
        right={
          <div className="inline">
            <Button variant="secondary" onClick={resetEval} disabled={loading}>
              Reset
            </Button>
            <Button onClick={evaluate} disabled={loading}>
              Evaluate
            </Button>
          </div>
        }
      >
        <div className="row">
          <div className="grid2">
            <Input
              label="Max Rows"
              type="number"
              min={100}
              max={500000}
              step="100"
              value={String(evalMaxRows)}
              onChange={(e) => {
                const v = Number(e.target.value);
                const n = Number.isFinite(v) ? Math.max(100, Math.trunc(v)) : 100;
                setEvalMaxRows(n);
              }}
              help="Truncate evaluation set for faster checks."
            />
            <Input
              label="Top N"
              type="number"
              min={0}
              max={200}
              step="1"
              value={String(evalTopN)}
              onChange={(e) => {
                const v = Number(e.target.value);
                const n = Number.isFinite(v) ? Math.min(200, Math.max(0, Math.trunc(v))) : 0;
                setEvalTopN(n);
              }}
              help="Return top risky transactions for spot checks."
            />
          </div>

          <div className="grid2">
            <Select
              label="Split Strategy"
              value={evalSplitStrategy}
              onChange={(e) => {
                const v = e.target.value as "time" | "random" | "none";
                setEvalSplitStrategy(v);
              }}
              help="Controls how the evaluation holdout is constructed."
            >
              <option value="time">time</option>
              <option value="random">random</option>
              <option value="none">none</option>
            </Select>
            <Input
              label="Test Size"
              type="number"
              min={0.05}
              max={0.5}
              step="0.01"
              value={String(evalTestSize)}
              onChange={(e) => {
                const v = Number(e.target.value);
                const n = Number.isFinite(v) ? Math.min(0.5, Math.max(0.05, v)) : 0.2;
                setEvalTestSize(n);
              }}
              help="Holdout fraction (used by time/random splits)."
            />
          </div>
          <div className="grid2">
            <Input
              label="Random State"
              type="number"
              min={0}
              max={10000}
              step="1"
              value={String(evalRandomState)}
              onChange={(e) => {
                const v = Number(e.target.value);
                const n = Number.isFinite(v) ? Math.min(10000, Math.max(0, Math.trunc(v))) : 42;
                setEvalRandomState(n);
              }}
              help="Seed used for random split sampling."
            />
            <div className="help" style={{ alignSelf: "end" }}>
              Tip: changing training settings won’t change evaluation unless these split settings also change.
            </div>
          </div>

          {evalOut ? (
            <div className="row">
              <div className="help">
                Tested on {evalOut.rows.toLocaleString()} transactions. Known suspicious cases: {evalOut.positives.toLocaleString()} ({(
                  evalOut.prevalence * 100
                ).toFixed(2)}%).
              </div>
              <div className="help">
                Split: {evalOut.split_strategy || "time"}{evalOut.cutoff_timestamp ? ` (cutoff: ${evalOut.cutoff_timestamp})` : ""}.
              </div>
              <div className="help">
                ML score quality: ROC-AUC {evalOut.ml.roc_auc?.toFixed(3) ?? "N/A"} and Average Precision{" "}
                {evalOut.ml.average_precision?.toFixed(3) ?? "N/A"}.
              </div>
              <div className="help">
                Final (combined) score quality: ROC-AUC {evalOut.composite.roc_auc?.toFixed(3) ?? "N/A"} and Average Precision{" "}
                {evalOut.composite.average_precision?.toFixed(3) ?? "N/A"}.
              </div>

              <div className="help" style={{ marginTop: 8, fontWeight: 700 }}>
                Top risky examples (for a quick manual spot-check)
              </div>
              <div style={{ overflowX: "auto" }}>
                <table className="table" aria-label="Top risky transactions">
                  <thead>
                    <tr>
                      <th>Txn</th>
                      <th>Amount (USD)</th>
                      <th>From</th>
                      <th>To</th>
                      <th>Risk</th>
                      <th>SAR?</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evalOut.top.map((r, idx) => {
                      const row = r as Record<string, unknown>;
                      const txn = String(row.txn_id ?? "N/A");
                      const amt = Number(row.amount_usd ?? 0);
                      const from = String(row.sender_country ?? "N/A");
                      const to = String(row.receiver_country ?? "N/A");
                      const risk = Number(row.composite_used_for_rank ?? row.composite_risk_score ?? 0);
                      const sar = row.is_sar_filed === 1 || row.is_sar_filed === true;
                      return (
                        <tr key={idx}>
                          <td style={{ fontWeight: 900 }}>{txn}</td>
                          <td>{amt ? amt.toFixed(2) : "N/A"}</td>
                          <td>{from}</td>
                          <td>{to}</td>
                          <td>{risk ? risk.toFixed(3) : "N/A"}</td>
                          <td>{sar ? "Yes" : "No"}</td>
                        </tr>
                      );
                    })}
                    {!evalOut.top.length ? (
                      <tr>
                        <td colSpan={6} className="help">
                          No rows returned.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>

              {evalOut.notes?.length ? (
                <div className="help" style={{ marginTop: 8 }}>
                  Notes: {evalOut.notes.join(" | ")}
                </div>
              ) : null}
            </div>
          ) : (
            <div className="help">Evaluation output appears here after a successful run.</div>
          )}
        </div>
        </Card>
      ) : null}

      <ToastHost toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
