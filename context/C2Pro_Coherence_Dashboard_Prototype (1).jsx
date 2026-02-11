import { useState, useEffect, useRef, useMemo } from "react";
import { RadialBarChart, RadialBar, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from "recharts";

const T = {
  primary: "#00ACC1", primaryDark: "#00838F", primaryLight: "#4DD0E1",
  bg: "#FAFAFA", card: "#FFFFFF", border: "#E4E4E7",
  text: "#09090B", textSec: "#71717A", textMuted: "#A1A1AA",
  success: "#198038", successBg: "#DEFBE6",
  warning: "#92400E", warningBg: "#FFF8E1",
  error: "#B91C1C", errorBg: "#FFF1F1",
  sidebar: "#162A38", sidebarAccent: "#1E3A4C",
  chart: { SCOPE: "#00ACC1", BUDGET: "#6929C4", QUALITY: "#1192E8", TECHNICAL: "#005D5D", LEGAL: "#9F1853", TIME: "#FA4D56" },
  r: "6px",
  shadow: "0 1px 3px 0 rgba(0,120,140,0.08)",
  shadowLg: "0 4px 6px -1px rgba(0,120,140,0.1)",
};

const DATA = {
  score: 78, project: "Torre Skyline — Contract Review",
  docs: 8, points: 2847,
  cats: {
    SCOPE:     { score: 80, alerts: 2, w: 0.20, trend: [72,75,78,80] },
    BUDGET:    { score: 62, alerts: 5, w: 0.20, trend: [58,60,61,62] },
    QUALITY:   { score: 85, alerts: 1, w: 0.15, trend: [80,82,84,85] },
    TECHNICAL: { score: 72, alerts: 3, w: 0.15, trend: [65,68,70,72] },
    LEGAL:     { score: 90, alerts: 0, w: 0.15, trend: [85,87,89,90] },
    TIME:      { score: 75, alerts: 4, w: 0.15, trend: [70,72,73,75] },
  },
  alertSum: { critical: 2, high: 5, medium: 8, low: 3 },
};

const META = {
  SCOPE: { icon: "🎯", label: "Scope" }, BUDGET: { icon: "💰", label: "Budget" },
  QUALITY: { icon: "✅", label: "Quality" }, TECHNICAL: { icon: "⚙️", label: "Technical" },
  LEGAL: { icon: "⚖️", label: "Legal" }, TIME: { icon: "⏱️", label: "Time" },
};

function useCountUp(target, dur = 1500) {
  const [v, setV] = useState(0);
  const r = useRef(0);
  useEffect(() => {
    const s = performance.now();
    const anim = (n) => {
      const p = Math.min((n - s) / dur, 1);
      setV(Math.round((1 - Math.pow(1 - p, 4)) * target));
      if (p < 1) r.current = requestAnimationFrame(anim);
    };
    r.current = requestAnimationFrame(anim);
    return () => cancelAnimationFrame(r.current);
  }, [target, dur]);
  return v;
}

function sev(score) {
  if (score >= 80) return { label: "Good", color: T.success, bg: T.successBg, shape: "●" };
  if (score >= 60) return { label: "Warning", color: T.warning, bg: T.warningBg, shape: "◆" };
  return { label: "Critical", color: T.error, bg: T.errorBg, shape: "▲" };
}

function scoreColor(s) {
  if (s >= 70) return T.success;
  if (s >= 40) return T.warning;
  return T.error;
}

function scoreLabel(s) {
  if (s >= 85) return "Excellent";
  if (s >= 70) return "Good";
  if (s >= 55) return "Acceptable";
  if (s >= 40) return "At Risk";
  return "Critical";
}

// ── Category ScoreCard ──
function ScoreCard({ cat, data, color, onClick, selected }) {
  const sv = sev(data.score);
  const animated = useCountUp(data.score);
  const m = META[cat];
  return (
    <button onClick={onClick} style={{
      background: selected ? `${color}08` : T.card, border: `1px solid ${selected ? color : T.border}`,
      borderRadius: T.r, boxShadow: T.shadow, padding: "14px 16px",
      display: "flex", alignItems: "center", gap: 12, cursor: "pointer",
      width: "100%", textAlign: "left", transition: "all 200ms ease",
    }}>
      <div style={{
        width: 38, height: 38, borderRadius: T.r, flexShrink: 0,
        background: `${color}15`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18,
      }}>{m.icon}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 22, fontWeight: 700 }}>{animated}</span>
          <span style={{ fontSize: 11, color: T.textMuted }}>/100</span>
        </div>
        <div style={{ fontSize: 12, color: T.textSec, display: "flex", gap: 4, alignItems: "center" }}>
          <span>{m.label}</span>
          <span style={{ color: T.textMuted }}>·</span>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>{Math.round(data.w * 100)}%</span>
        </div>
      </div>
      <div style={{
        padding: "3px 10px", borderRadius: 99, fontSize: 11, fontWeight: 600,
        background: sv.bg, color: sv.color, display: "flex", gap: 4, alignItems: "center", flexShrink: 0,
      }}>
        <span>{sv.shape}</span>{sv.label}
      </div>
      {data.alerts > 0 && (
        <div style={{
          width: 24, height: 24, borderRadius: "50%", fontSize: 11, fontWeight: 600,
          background: `${T.error}12`, color: T.error,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: "'JetBrains Mono', monospace", flexShrink: 0,
        }}>{data.alerts}</div>
      )}
    </button>
  );
}

// ── Main App ──
export default function C2ProDashboard() {
  const [activeNav, setActiveNav] = useState("dashboard");
  const [selectedCat, setSelectedCat] = useState(null);
  const [view, setView] = useState("breakdown"); // "breakdown" | "radar" | "alerts"
  const animatedScore = useCountUp(DATA.score);
  const color = scoreColor(DATA.score);
  const label = scoreLabel(DATA.score);

  const gaugeData = [{ name: "score", value: DATA.score, fill: color }];

  const barData = Object.entries(DATA.cats)
    .map(([k, v]) => ({ name: META[k].label, score: v.score, fill: T.chart[k] }))
    .sort((a, b) => a.score - b.score);

  const radarData = Object.entries(DATA.cats).map(([k, v]) => ({
    category: META[k].label, score: v.score, target: 80,
  }));

  const alertData = [
    { name: "Critical", count: DATA.alertSum.critical, color: T.error },
    { name: "High", count: DATA.alertSum.high, color: "#C2410C" },
    { name: "Medium", count: DATA.alertSum.medium, color: T.warning },
    { name: "Low", count: DATA.alertSum.low, color: T.success },
  ];

  const totalAlerts = Object.values(DATA.alertSum).reduce((a, b) => a + b, 0);
  const catEntries = Object.entries(DATA.cats).sort(([, a], [, b]) => a.score - b.score);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: T.bg, fontFamily: "'Inter', system-ui, sans-serif", color: T.text }}>
      {/* Demo Banner */}
      <div style={{
        background: T.warningBg, borderBottom: `1px solid ${T.warning}33`,
        padding: "5px 16px", display: "flex", alignItems: "center", justifyContent: "center",
        gap: 8, fontSize: 11, fontWeight: 500, color: T.warning,
      }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: T.warning, display: "inline-block" }} />
        Demo Mode — Sample data for "Torre Skyline" project
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Sidebar */}
        <div style={{
          width: 210, background: T.sidebar, color: "#E4E4E7",
          display: "flex", flexDirection: "column", padding: "16px 0", flexShrink: 0,
        }}>
          <div style={{ padding: "0 16px 20px", display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 28, height: 28, borderRadius: T.r,
              background: `linear-gradient(135deg, ${T.primary}, ${T.primaryDark})`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 12, fontWeight: 700, color: "white",
            }}>C2</div>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, fontSize: 14, letterSpacing: "-0.02em" }}>C2Pro</span>
          </div>
          <div style={{ fontSize: 9, fontWeight: 600, color: T.textMuted, padding: "0 16px", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>Torre Skyline</div>

          {[
            { id: "dashboard", icon: "📊", label: "Dashboard" },
            { id: "documents", icon: "📄", label: "Documents" },
            { id: "alerts", icon: "⚠️", label: "Alerts", badge: totalAlerts },
            { id: "stakeholders", icon: "👥", label: "Stakeholders" },
            { id: "procurement", icon: "🛒", label: "Procurement" },
          ].map((it) => (
            <button key={it.id} onClick={() => setActiveNav(it.id)} style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "9px 16px", border: "none", cursor: "pointer", width: "100%", textAlign: "left",
              background: activeNav === it.id ? T.sidebarAccent : "transparent",
              color: activeNav === it.id ? "white" : "#C4C4CC",
              fontSize: 13, fontWeight: activeNav === it.id ? 500 : 400,
              borderLeft: activeNav === it.id ? `3px solid ${T.primaryLight}` : "3px solid transparent",
              transition: "all 150ms ease",
            }}>
              <span style={{ fontSize: 14 }}>{it.icon}</span>
              <span>{it.label}</span>
              {it.badge && <span style={{ marginLeft: "auto", background: T.error, color: "white", borderRadius: 99, padding: "1px 6px", fontSize: 10, fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>{it.badge}</span>}
            </button>
          ))}
        </div>

        {/* Main Content */}
        <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
          {/* Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <div>
              <div style={{ fontSize: 10, color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 500, marginBottom: 4 }}>Project / Torre Skyline</div>
              <h1 style={{ fontSize: 22, fontWeight: 600, margin: 0 }}>Coherence Dashboard</h1>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {["breakdown", "radar", "alerts"].map((v) => (
                <button key={v} onClick={() => setView(v)} style={{
                  padding: "6px 14px", borderRadius: T.r, fontSize: 12, fontWeight: 500,
                  border: `1px solid ${view === v ? T.primary : T.border}`,
                  background: view === v ? `${T.primary}10` : T.card,
                  color: view === v ? T.primary : T.textSec,
                  cursor: "pointer", transition: "all 150ms ease", textTransform: "capitalize",
                }}>{v}</button>
              ))}
            </div>
          </div>

          {/* Top Row: Gauge + Stats */}
          <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 20, marginBottom: 20 }}>
            {/* Gauge Card */}
            <div style={{
              background: T.card, borderRadius: T.r, border: `1px solid ${T.border}`,
              boxShadow: T.shadow, padding: 24, display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
            }}>
              <div style={{ position: "relative", width: 180, height: 180 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <RadialBarChart cx="50%" cy="50%" innerRadius="72%" outerRadius="100%" startAngle={90} endAngle={-270} data={gaugeData} barSize={14}>
                    <RadialBar dataKey="value" cornerRadius={7} background={{ fill: "#F4F4F5" }} animationDuration={1500} animationEasing="ease-out" />
                  </RadialBarChart>
                </ResponsiveContainer>
                <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 40, fontWeight: 700, color, lineHeight: 1 }}>{animatedScore}</span>
                  <span style={{ fontSize: 13, color: T.textMuted }}>/100</span>
                </div>
              </div>
              <span style={{ padding: "4px 14px", borderRadius: 99, fontSize: 12, fontWeight: 600, color, background: `${color}12` }}>{label}</span>
              <p style={{ fontSize: 11, color: T.textMuted, textAlign: "center", margin: 0, lineHeight: 1.5 }}>
                Based on <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>{DATA.docs}</span> documents and <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>{DATA.points.toLocaleString()}</span> data points
              </p>
              <div style={{ fontSize: 10, color: T.textMuted, fontFamily: "'JetBrains Mono', monospace" }}>
                v3.2 engine · Feb 7, 2026 14:34
              </div>
            </div>

            {/* Right Panel: Dynamic View */}
            <div style={{
              background: T.card, borderRadius: T.r, border: `1px solid ${T.border}`,
              boxShadow: T.shadow, padding: 20,
            }}>
              {view === "breakdown" && (
                <div>
                  <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 16px" }}>Category Scores (sorted by priority)</h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={barData} layout="vertical" margin={{ left: 10, right: 30 }} barSize={18}>
                      <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: T.textMuted }} axisLine={false} tickLine={false} />
                      <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: T.textSec }} axisLine={false} tickLine={false} width={80} />
                      <Tooltip contentStyle={{ borderRadius: T.r, border: `1px solid ${T.border}`, fontSize: 12 }} formatter={(v) => [`${v}/100`, "Score"]} />
                      <Bar dataKey="score" radius={[0, 4, 4, 0]} animationDuration={1200}>
                        {barData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              {view === "radar" && (
                <div>
                  <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 12px" }}>Score vs Target (80)</h3>
                  <ResponsiveContainer width="100%" height={240}>
                    <RadarChart data={radarData}>
                      <PolarGrid stroke={T.border} />
                      <PolarAngleAxis dataKey="category" tick={{ fontSize: 11, fill: T.textSec }} />
                      <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
                      <Radar name="Score" dataKey="score" stroke={T.primary} fill={T.primary} fillOpacity={0.25} strokeWidth={2} animationDuration={1000} />
                      <Radar name="Target" dataKey="target" stroke={T.textMuted} fill="none" strokeDasharray="5 5" strokeWidth={1.5} />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              )}
              {view === "alerts" && (
                <div>
                  <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 16px" }}>Alert Distribution</h3>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
                    {alertData.map((a) => (
                      <div key={a.name} style={{ textAlign: "center", padding: 12, borderRadius: T.r, background: `${a.color}08`, border: `1px solid ${a.color}20` }}>
                        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 28, fontWeight: 700, color: a.color }}>{a.count}</div>
                        <div style={{ fontSize: 11, color: T.textSec, fontWeight: 500 }}>{a.name}</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ fontSize: 12, color: T.textSec, padding: "10px 14px", background: `${T.error}06`, borderRadius: T.r, border: `1px solid ${T.error}15`, display: "flex", gap: 8, alignItems: "center" }}>
                    <span style={{ fontSize: 16 }}>⚠️</span>
                    <span><strong>{DATA.alertSum.critical + DATA.alertSum.high}</strong> alerts require immediate review</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Category Cards Grid */}
          <div style={{ marginBottom: 8 }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 12px" }}>Sub-Category Breakdown</h3>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
            {catEntries.map(([cat, data]) => (
              <ScoreCard
                key={cat}
                cat={cat}
                data={data}
                color={T.chart[cat]}
                selected={selectedCat === cat}
                onClick={() => setSelectedCat(selectedCat === cat ? null : cat)}
              />
            ))}
          </div>

          {/* Selected Category Detail Sheet */}
          {selectedCat && (
            <div style={{
              marginTop: 16, background: T.card, borderRadius: T.r,
              border: `1px solid ${T.chart[selectedCat]}40`, boxShadow: T.shadowLg,
              padding: 20, animation: "fadeIn 200ms ease",
            }}>
              <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }`}</style>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 22 }}>{META[selectedCat].icon}</span>
                  <div>
                    <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{META[selectedCat].label} Analysis</h3>
                    <span style={{ fontSize: 12, color: T.textSec }}>Weight: {Math.round(DATA.cats[selectedCat].w * 100)}% · {DATA.cats[selectedCat].alerts} alert{DATA.cats[selectedCat].alerts !== 1 ? "s" : ""}</span>
                  </div>
                </div>
                <button onClick={() => setSelectedCat(null)} style={{
                  background: "none", border: `1px solid ${T.border}`, borderRadius: T.r,
                  padding: "4px 12px", fontSize: 12, cursor: "pointer", color: T.textSec,
                }}>Close</button>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
                {DATA.cats[selectedCat].trend.map((v, i) => (
                  <div key={i} style={{
                    textAlign: "center", padding: "10px 8px", borderRadius: T.r,
                    background: i === 3 ? `${T.chart[selectedCat]}10` : "#F9F9FB",
                    border: `1px solid ${i === 3 ? T.chart[selectedCat] + "30" : T.border}`,
                  }}>
                    <div style={{ fontSize: 10, color: T.textMuted, marginBottom: 4 }}>
                      {["Week 1", "Week 2", "Week 3", "Current"][i]}
                    </div>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 18, fontWeight: 600, color: i === 3 ? T.chart[selectedCat] : T.text }}>{v}</div>
                  </div>
                ))}
              </div>
              {DATA.cats[selectedCat].alerts > 0 && (
                <div style={{ marginTop: 14, padding: "10px 14px", borderRadius: T.r, background: T.warningBg, border: `1px solid ${T.warning}20`, fontSize: 12, color: T.warning }}>
                  📋 {DATA.cats[selectedCat].alerts} document pair{DATA.cats[selectedCat].alerts !== 1 ? "s" : ""} require{DATA.cats[selectedCat].alerts === 1 ? "s" : ""} review in this category — <a href="#" style={{ color: T.primary, fontWeight: 600, textDecoration: "none" }}>View in Evidence Viewer →</a>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
