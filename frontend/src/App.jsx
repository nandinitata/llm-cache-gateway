import { useCallback, useEffect, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const SAMPLES = [
  "What is the capital of France?",
  "Which city is the capital of France?",
  "Explain what a hash map is, in one sentence.",
  "In one sentence, what's a hash map?",
];

function Ring({ rate }) {
  const pct = Math.round((rate || 0) * 100);
  const R = 52, C = 2 * Math.PI * R;
  return (
    <svg className="ring" viewBox="0 0 120 120" width="120" height="120">
      <circle cx="60" cy="60" r={R} className="ring__track" />
      <circle
        cx="60" cy="60" r={R} className="ring__fill"
        strokeDasharray={C} strokeDashoffset={C - (C * pct) / 100}
        transform="rotate(-90 60 60)"
      />
      <text x="60" y="58" className="ring__num">{pct}</text>
      <text x="60" y="76" className="ring__lab">% HIT</text>
    </svg>
  );
}

function LatencyBars({ hit, model }) {
  const max = Math.max(hit, model, 1);
  return (
    <div className="bars">
      <div className="bar">
        <span className="bar__k">cache hit</span>
        <span className="bar__track"><span className="bar__fill bar__fill--hit" style={{ width: `${(hit / max) * 100}%` }} /></span>
        <span className="bar__v">{hit ? `${hit.toFixed(0)}ms` : "—"}</span>
      </div>
      <div className="bar">
        <span className="bar__k">model call</span>
        <span className="bar__track"><span className="bar__fill bar__fill--model" style={{ width: `${(model / max) * 100}%` }} /></span>
        <span className="bar__v">{model ? `${(model / 1000).toFixed(1)}s` : "—"}</span>
      </div>
    </div>
  );
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [log, setLog] = useState([]);
  const [stats, setStats] = useState({ hits: 0, misses: 0, total: 0, hit_rate: 0, entries: 0 });
  const [health, setHealth] = useState(null);
  const [busy, setBusy] = useState(false);
  const [rate, setRate] = useState(null);
  const avgHit = useRef(0);
  const avgModel = useRef(0);

  const refreshStats = useCallback(() => {
    fetch(`${API_BASE}/stats`).then((r) => r.json()).then(setStats).catch(() => {});
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/health`).then((r) => r.json()).then(setHealth).catch(() => {});
    refreshStats();
    if (new URLSearchParams(window.location.search).has("demo")) {
      fetch("/demo.json").then((r) => r.json()).then((d) => {
        if (d.stats) setStats(d.stats);
        if (d.log) setLog(d.log);
        if (d.avgHit) avgHit.current = d.avgHit;
        if (d.avgModel) avgModel.current = d.avgModel;
      }).catch(() => {});
    }
  }, [refreshStats]);

  const ask = useCallback(async (q) => {
    const text = (q ?? question).trim();
    if (!text || busy) return;
    setBusy(true);
    setRate(null);
    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Client-Id": "console" },
        body: JSON.stringify({ question: text }),
      });
      const data = await res.json();
      if (res.status === 429) { setRate(data.detail); return; }
      const row = { ...data, question: text, ts: Date.now() };
      setLog((l) => [row, ...l].slice(0, 12));
      if (data.cached) avgHit.current = avgHit.current ? (avgHit.current + data.latency_ms) / 2 : data.latency_ms;
      else avgModel.current = avgModel.current ? (avgModel.current + data.latency_ms) / 2 : data.latency_ms;
      refreshStats();
    } finally { setBusy(false); }
  }, [question, busy, refreshStats]);

  return (
    <div className="console">
      <header className="bar-top">
        <div className="brand">
          <span className="brand__dot" />
          <span className="brand__name">LLM CACHE GATEWAY</span>
          <span className="brand__sub">semantic cache · rate limiter · redis</span>
        </div>
        <div className="brand__status">
          {health && <span className={`pill ${health.redis ? "pill--ok" : "pill--bad"}`}>redis {health.redis ? "up" : "down"}</span>}
          {health && <span className="pill">{health.embed_model}</span>}
          {health && <span className="pill">{health.answer_model}</span>}
        </div>
      </header>

      <main className="grid">
        <section className="feed">
          <div className="asker">
            <input
              className="asker__in"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask()}
              placeholder="ask the gateway a question…"
              spellCheck={false}
            />
            <button className="asker__btn" onClick={() => ask()} disabled={busy}>
              {busy ? "…" : "SEND"}
            </button>
          </div>
          <div className="chips">
            {SAMPLES.map((s) => (
              <button key={s} className="chip" onClick={() => { setQuestion(s); ask(s); }}>{s}</button>
            ))}
          </div>
          {rate && <div className="ratewarn">⚠ {rate}</div>}

          <div className="stream">
            <div className="stream__head">REQUEST STREAM</div>
            {log.length === 0 && <p className="stream__idle">Send a question. Repeats and rewordings come back from the cache instead of the model.</p>}
            <ul className="rows">
              {log.map((row, i) => (
                <li key={row.ts + "-" + i} className={`row row--${row.cached ? "hit" : "model"}`} style={{ animationDelay: `${Math.min(i, 3) * 40}ms` }}>
                  <span className="row__tag">{row.cached ? "CACHED" : "MODEL"}</span>
                  <span className="row__q">{row.question}</span>
                  <span className="row__meta">
                    {row.cached && <span className="row__sim">sim {row.similarity}</span>}
                    <span className="row__lat">{row.latency_ms < 1000 ? `${row.latency_ms}ms` : `${(row.latency_ms / 1000).toFixed(1)}s`}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <aside className="panels">
          <div className="panel panel--ring">
            <Ring rate={stats.total ? stats.hit_rate : 0} />
            <div className="counts">
              <div className="count"><b>{stats.hits}</b><span>hits</span></div>
              <div className="count"><b>{stats.misses}</b><span>misses</span></div>
              <div className="count"><b>{stats.entries}</b><span>cached</span></div>
            </div>
          </div>

          <div className="panel">
            <div className="panel__k">LATENCY</div>
            <LatencyBars hit={avgHit.current} model={avgModel.current} />
            {avgHit.current > 0 && avgModel.current > 0 && (
              <p className="panel__note">cache hits are ~{Math.round(avgModel.current / avgHit.current)}× faster than the model</p>
            )}
          </div>

          <div className="panel">
            <div className="panel__k">HOW IT WORKS</div>
            <ol className="how">
              <li>embed the question (local model)</li>
              <li>ask Redis for the nearest past question (VSIM)</li>
              <li>close enough? return the stored answer</li>
              <li>otherwise call the model once, then cache it</li>
            </ol>
          </div>
        </aside>
      </main>
    </div>
  );
}
