import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, DashboardStats, Failure, Health, SampleLog } from "./api";

const FALLBACK_SAMPLE = `npm error code ETIMEDOUT
npm error errno ETIMEDOUT
npm error network request to https://registry.npmjs.org/react failed, reason: connect ETIMEDOUT
npm ERR! network Temporary network failure
Error: Process completed with exit code 1.`;

function Stat({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div className="animate-rise border-b border-line pb-4">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-mist">{label}</p>
      <p className={`mt-2 font-display text-3xl font-semibold ${accent ?? "text-white"}`}>{value}</p>
    </div>
  );
}

function StatusChip({ failure }: { failure: Failure }) {
  const tone = failure.auto_applied
    ? "text-signal border-signal/40"
    : failure.status === "awaiting_approval"
      ? "text-warn border-warn/40"
      : "text-mist border-line";
  return (
    <span className={`rounded border px-2 py-0.5 font-mono text-[11px] uppercase tracking-wide ${tone}`}>
      {failure.auto_applied ? "auto-fixed" : failure.status.replace(/_/g, " ")}
    </span>
  );
}

function ClassBars({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  const max = Math.max(...entries.map(([, v]) => v), 1);
  if (!entries.length) {
    return <p className="font-mono text-sm text-mist">No diagnoses yet — run the agent.</p>;
  }
  return (
    <ul className="mt-4 space-y-3">
      {entries.map(([k, v]) => (
        <li key={k}>
          <div className="mb-1 flex justify-between font-mono text-xs">
            <span className="text-mist">{k}</span>
            <span>{v}</span>
          </div>
          <div className="h-1.5 w-full bg-line/60">
            <div
              className="h-full bg-signal/80 transition-all duration-500"
              style={{ width: `${(v / max) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function App() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [samples, setSamples] = useState<SampleLog[]>([]);
  const [selectedSample, setSelectedSample] = useState<string>("");
  const [logs, setLogs] = useState(FALLBACK_SAMPLE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<Failure | null>(null);
  const [feedbackNote, setFeedbackNote] = useState<string | null>(null);

  const apiOk = health?.status === "ok";
  const canApprove = useMemo(() => {
    if (!last) return false;
    return (
      !last.auto_applied &&
      ["retry_workflow", "clear_cache", "pin_dependency"].includes(last.remediation_action)
    );
  }, [last]);

  async function refresh() {
    try {
      const [h, s] = await Promise.all([api.health(), api.stats()]);
      setHealth(h);
      setStats(s);
      setError(null);
    } catch (e) {
      setHealth(null);
      setError(e instanceof Error ? e.message : "Failed to reach API");
    }
  }

  useEffect(() => {
    refresh();
    api
      .samples()
      .then((list) => {
        setSamples(list);
        if (list[0]) {
          setSelectedSample(list[0].id);
          setLogs(list[0].content);
        }
      })
      .catch(() => undefined);
    const id = window.setInterval(refresh, 15000);
    return () => window.clearInterval(id);
  }, []);

  function pickSample(id: string) {
    setSelectedSample(id);
    const sample = samples.find((s) => s.id === id);
    if (sample) setLogs(sample.content);
  }

  async function onDiagnose(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setFeedbackNote(null);
    try {
      const result = await api.diagnose(logs);
      setLast(result);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Diagnosis failed");
    } finally {
      setBusy(false);
    }
  }

  async function sendFeedback(isCorrect: boolean) {
    if (!last) return;
    await api.feedback(last.id, isCorrect);
    setFeedbackNote(isCorrect ? "Marked correct — thanks." : "Marked incorrect — knowledge base can learn from corrections.");
    await refresh();
  }

  async function onApprove() {
    if (!last) return;
    setBusy(true);
    try {
      const updated = await api.approveRemediation(last.id);
      setLast(updated);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-ink bg-aurora">
      <div className="pointer-events-none fixed inset-0 bg-grid opacity-40" />

      <header className="relative z-10 border-b border-line/80">
        <div className="mx-auto flex max-w-6xl items-end justify-between gap-6 px-6 py-8">
          <div className="animate-rise">
            <p className="font-mono text-xs uppercase tracking-[0.28em] text-signal">CI / CD · Agent</p>
            <h1 className="mt-2 font-display text-4xl font-bold tracking-tight md:text-5xl">
              DevOps Copilot
            </h1>
            <p className="mt-3 max-w-xl text-mist">
              Diagnose pipeline failures from logs, retrieve similar past fixes, and apply only safe remediations.
            </p>
          </div>
          <div className="hidden text-right sm:block">
            <p className="font-mono text-xs text-mist">API · {health?.llm_backend ?? "…"}</p>
            <p className={`mt-1 font-mono text-sm ${apiOk ? "text-signal" : "text-alert"}`}>
              {health == null && error ? "offline" : apiOk ? "online" : "…"}
              <span
                className={`ml-2 inline-block h-2 w-2 rounded-full ${
                  apiOk ? "bg-signal animate-pulseSoft" : "bg-alert"
                }`}
              />
            </p>
            {health?.knowledge_docs != null && (
              <p className="mt-1 font-mono text-[11px] text-mist">{health.knowledge_docs} KB docs</p>
            )}
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto grid max-w-6xl gap-10 px-6 py-10 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="space-y-8">
          <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
            <Stat label="Failures" value={stats?.total_failures ?? "—"} />
            <Stat label="Diagnosed" value={stats?.diagnosed ?? "—"} accent="text-signal" />
            <Stat label="Auto-fixed" value={stats?.auto_remediated ?? "—"} />
            <Stat
              label="Accuracy"
              value={
                stats?.accuracy_estimate == null
                  ? "—"
                  : `${Math.round(stats.accuracy_estimate * 100)}%`
              }
              accent="text-warn"
            />
          </div>

          <form onSubmit={onDiagnose} className="animate-rise space-y-4" style={{ animationDelay: "80ms" }}>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <h2 className="font-display text-2xl font-semibold">Diagnose a failure</h2>
              {samples.length > 0 ? (
                <label className="flex flex-col gap-1">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-mist">Sample pack</span>
                  <select
                    value={selectedSample}
                    onChange={(e) => pickSample(e.target.value)}
                    className="border border-line bg-panel px-3 py-2 font-mono text-xs text-white outline-none ring-signal/40 focus:ring-2"
                  >
                    {samples.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.title}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <button
                  type="button"
                  className="font-mono text-xs text-signal underline-offset-4 hover:underline"
                  onClick={() => setLogs(FALLBACK_SAMPLE)}
                >
                  load sample
                </button>
              )}
            </div>
            {selectedSample && samples.find((s) => s.id === selectedSample)?.description && (
              <p className="font-mono text-xs text-mist">
                {samples.find((s) => s.id === selectedSample)?.description}
              </p>
            )}
            <textarea
              value={logs}
              onChange={(e) => setLogs(e.target.value)}
              rows={12}
              className="w-full resize-y border border-line bg-panel/80 p-4 font-mono text-sm leading-relaxed text-white outline-none ring-signal/40 focus:ring-2"
              placeholder="Paste CI failure logs…"
            />
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={busy || !logs.trim()}
                className="bg-signal px-5 py-2.5 font-display text-sm font-semibold text-ink transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? "Analyzing…" : "Run agent"}
              </button>
              {error && <p className="max-w-md font-mono text-sm text-alert">{error}</p>}
            </div>
          </form>

          {last && (
            <article className="animate-rise border border-line bg-panel/70 p-6">
              <div className="flex flex-wrap items-center gap-3">
                <h3 className="font-display text-xl font-semibold">{last.classification}</h3>
                <StatusChip failure={last} />
                {last.confidence != null && (
                  <span className="font-mono text-xs text-mist">
                    confidence {(last.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              <dl className="mt-5 space-y-4 text-sm">
                <div>
                  <dt className="font-mono text-xs uppercase tracking-wider text-mist">Root cause</dt>
                  <dd className="mt-1 text-white/90">{last.root_cause}</dd>
                </div>
                <div>
                  <dt className="font-mono text-xs uppercase tracking-wider text-mist">Suggested fix</dt>
                  <dd className="mt-1 text-white/90">{last.suggested_fix}</dd>
                </div>
                <div>
                  <dt className="font-mono text-xs uppercase tracking-wider text-mist">Remediation</dt>
                  <dd className="mt-1 font-mono text-signal">{last.remediation_action}</dd>
                </div>
                {last.agent_reasoning && (
                  <div>
                    <dt className="font-mono text-xs uppercase tracking-wider text-mist">Reasoning</dt>
                    <dd className="mt-1 text-mist">{last.agent_reasoning}</dd>
                  </div>
                )}
              </dl>
              <div className="mt-6 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => sendFeedback(true)}
                  className="border border-signal/50 px-3 py-1.5 font-mono text-xs text-signal hover:bg-signal/10"
                >
                  Mark correct
                </button>
                <button
                  type="button"
                  onClick={() => sendFeedback(false)}
                  className="border border-alert/50 px-3 py-1.5 font-mono text-xs text-alert hover:bg-alert/10"
                >
                  Mark incorrect
                </button>
                {canApprove && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={onApprove}
                    className="border border-warn/50 px-3 py-1.5 font-mono text-xs text-warn hover:bg-warn/10 disabled:opacity-40"
                  >
                    Approve remediation
                  </button>
                )}
              </div>
              {feedbackNote && <p className="mt-3 font-mono text-xs text-mist">{feedbackNote}</p>}
            </article>
          )}
        </section>

        <aside className="space-y-6">
          <div className="animate-rise border border-line bg-panel/50 p-5" style={{ animationDelay: "120ms" }}>
            <h2 className="font-display text-lg font-semibold">By classification</h2>
            <ClassBars data={stats?.by_classification ?? {}} />
          </div>

          <div className="animate-rise border border-line bg-panel/50 p-5" style={{ animationDelay: "160ms" }}>
            <div className="flex items-baseline justify-between">
              <h2 className="font-display text-lg font-semibold">Recent failures</h2>
              <span className="font-mono text-[10px] text-mist">
                awaiting {stats?.awaiting_approval ?? 0}
              </span>
            </div>
            <ul className="mt-4 max-h-[28rem] space-y-4 overflow-y-auto pr-1">
              {(stats?.recent_failures ?? []).map((f) => (
                <li key={f.id}>
                  <button
                    type="button"
                    onClick={() => setLast(f)}
                    className="w-full border-b border-line/70 pb-4 text-left transition hover:border-signal/40"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-mono text-xs text-mist">
                        #{f.id} · {f.repo}
                      </p>
                      <StatusChip failure={f} />
                    </div>
                    <p className="mt-2 text-sm font-medium">{f.classification ?? "unclassified"}</p>
                    <p className="mt-1 line-clamp-2 text-sm text-mist">{f.root_cause}</p>
                  </button>
                </li>
              ))}
              {!stats?.recent_failures?.length && (
                <li className="font-mono text-sm text-mist">Empty — paste logs and diagnose.</li>
              )}
            </ul>
          </div>
        </aside>
      </main>
    </div>
  );
}
