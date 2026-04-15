import { useState, useEffect } from "react";

// ─── Market session definitions ────────────────────────────────────────────────
// All times in local wall-clock hours (24h) within the respective timezone.

interface Session { open: number; close: number }   // decimal hours, e.g. 9.5 = 09:30

const CN_SESSIONS: Session[] = [
  { open: 9.5,  close: 11.5 },   // 09:30 – 11:30
  { open: 13,   close: 15 },     // 13:00 – 15:00
];

const US_PRE_MARKET:  Session = { open: 4,   close: 9.5  };  // 04:00 – 09:30 ET
const US_REGULAR:     Session = { open: 9.5, close: 16   };  // 09:30 – 16:00 ET
const US_AFTER_HOURS: Session = { open: 16,  close: 20   };  // 16:00 – 20:00 ET

// ─── Helpers ────────────────────────────────────────────────────────────────────

function nowIn(tz: string): Date {
  // Parse current time in the given timezone via Intl
  return new Date(new Date().toLocaleString("en-US", { timeZone: tz }));
}

function decimalHour(d: Date): number {
  return d.getHours() + d.getMinutes() / 60 + d.getSeconds() / 3600;
}

function isWeekend(d: Date): boolean {
  const dow = d.getDay();
  return dow === 0 || dow === 6;
}

function minutesToHHMM(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = Math.floor(minutes % 60);
  const s = Math.floor((minutes * 60) % 60);
  if (h > 0) return `${h}小时${m}分`;
  if (m > 0) return `${m}分${s}秒`;
  return `${s}秒`;
}

function fmtTime(d: Date, tz: string): string {
  return d.toLocaleTimeString("zh-CN", {
    timeZone: tz,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function fmtDate(d: Date, tz: string): string {
  return d.toLocaleDateString("zh-CN", {
    timeZone: tz,
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
  });
}

// ─── Market status calculation ──────────────────────────────────────────────────

type MarketStatus =
  | { state: "open";       label: string; countdown: number; sessionEnd: number }
  | { state: "pre";        label: string; countdown: number }
  | { state: "after";      label: string; countdown: number }
  | { state: "closed";     label: string; nextOpenMin: number };

function cnMarketStatus(now: Date): MarketStatus {
  if (isWeekend(now)) {
    // Next open: Monday 09:30
    const daysUntilMon = (8 - now.getDay()) % 7 || 7;
    const nextOpen = new Date(now);
    nextOpen.setDate(now.getDate() + daysUntilMon);
    nextOpen.setHours(9, 30, 0, 0);
    const mins = (nextOpen.getTime() - now.getTime()) / 60000;
    return { state: "closed", label: "休市（周末）", nextOpenMin: mins };
  }
  const h = decimalHour(now);
  for (const s of CN_SESSIONS) {
    if (h >= s.open && h < s.close) {
      return {
        state: "open",
        label: "交易中",
        countdown: (s.close - h) * 60,
        sessionEnd: s.close,
      };
    }
  }
  // Pre-market (before first session)
  if (h < CN_SESSIONS[0].open) {
    return { state: "pre", label: "未开盘", countdown: (CN_SESSIONS[0].open - h) * 60 };
  }
  // Lunch break
  if (h >= CN_SESSIONS[0].close && h < CN_SESSIONS[1].open) {
    return { state: "pre", label: "午休", countdown: (CN_SESSIONS[1].open - h) * 60 };
  }
  // After market
  const nextMorning = new Date(now);
  nextMorning.setDate(now.getDate() + 1);
  nextMorning.setHours(9, 30, 0, 0);
  // Skip weekend
  while (isWeekend(nextMorning)) nextMorning.setDate(nextMorning.getDate() + 1);
  const mins = (nextMorning.getTime() - now.getTime()) / 60000;
  return { state: "closed", label: "已收盘", nextOpenMin: mins };
}

function usMarketStatus(now: Date): MarketStatus {
  if (isWeekend(now)) {
    const daysUntilMon = (8 - now.getDay()) % 7 || 7;
    const nextOpen = new Date(now);
    nextOpen.setDate(now.getDate() + daysUntilMon);
    nextOpen.setHours(9, 30, 0, 0);
    const mins = (nextOpen.getTime() - now.getTime()) / 60000;
    return { state: "closed", label: "休市（周末）", nextOpenMin: mins };
  }
  const h = decimalHour(now);
  if (h >= US_REGULAR.open && h < US_REGULAR.close) {
    return { state: "open", label: "正式交易", countdown: (US_REGULAR.close - h) * 60, sessionEnd: US_REGULAR.close };
  }
  if (h >= US_PRE_MARKET.open && h < US_REGULAR.open) {
    return { state: "pre", label: "盘前交易", countdown: (US_REGULAR.open - h) * 60 };
  }
  if (h >= US_REGULAR.close && h < US_AFTER_HOURS.close) {
    return { state: "after", label: "盘后交易", countdown: (US_AFTER_HOURS.close - h) * 60 };
  }
  // Closed until pre-market next day
  const nextPre = new Date(now);
  nextPre.setDate(now.getDate() + 1);
  nextPre.setHours(4, 0, 0, 0);
  while (isWeekend(nextPre)) nextPre.setDate(nextPre.getDate() + 1);
  const mins = (nextPre.getTime() - now.getTime()) / 60000;
  return { state: "closed", label: "已收盘", nextOpenMin: mins };
}

// ─── CME Globex commodities status ───────────────────────────────────────────
// XAU (Gold), CL (WTI), BZ (Brent), NG (Nat Gas)
// Sun 18:00 – Fri 17:00 ET; daily maintenance break Mon–Thu 17:00–18:00 ET

type CmeStatus =
  | { state: "open";    label: string; countdown: number }
  | { state: "break";   label: string; countdown: number }
  | { state: "closed";  label: string; nextOpenMin: number };

function cmeMarketStatus(now: Date): CmeStatus {
  const dow = now.getDay();   // 0=Sun, 6=Sat
  const h   = decimalHour(now);

  if (dow === 6) {  // Saturday — always closed
    const nextOpen = new Date(now);
    nextOpen.setDate(now.getDate() + 1);
    nextOpen.setHours(18, 0, 0, 0);
    return { state: "closed", label: "休市（周末）", nextOpenMin: (nextOpen.getTime() - now.getTime()) / 60000 };
  }
  if (dow === 0) {  // Sunday
    if (h < 18) {
      const nextOpen = new Date(now);
      nextOpen.setHours(18, 0, 0, 0);
      return { state: "closed", label: "休市（周末）", nextOpenMin: (nextOpen.getTime() - now.getTime()) / 60000 };
    }
    const nextClose = new Date(now);
    nextClose.setDate(now.getDate() + 1);
    nextClose.setHours(17, 0, 0, 0);
    return { state: "open", label: "交易中", countdown: (nextClose.getTime() - now.getTime()) / 60000 };
  }
  if (dow === 5) {  // Friday
    if (h < 17) {
      const nextClose = new Date(now);
      nextClose.setHours(17, 0, 0, 0);
      return { state: "open", label: "交易中", countdown: (nextClose.getTime() - now.getTime()) / 60000 };
    }
    const nextOpen = new Date(now);
    nextOpen.setDate(now.getDate() + 2);  // Sunday
    nextOpen.setHours(18, 0, 0, 0);
    return { state: "closed", label: "休市（周末）", nextOpenMin: (nextOpen.getTime() - now.getTime()) / 60000 };
  }
  // Mon–Thu (dow 1–4)
  if (h >= 17 && h < 18) {
    const resume = new Date(now);
    resume.setHours(18, 0, 0, 0);
    return { state: "break", label: "盘中休市", countdown: (resume.getTime() - now.getTime()) / 60000 };
  }
  const nextClose = new Date(now);
  if (h < 17) {
    nextClose.setHours(17, 0, 0, 0);
  } else {
    nextClose.setDate(now.getDate() + 1);
    nextClose.setHours(17, 0, 0, 0);
  }
  return { state: "open", label: "交易中", countdown: (nextClose.getTime() - now.getTime()) / 60000 };
}

function cmeStatusColor(state: CmeStatus["state"]): string {
  if (state === "open")  return "#1c8a3e";
  if (state === "break") return "#b8860b";
  return "#888";
}

function CmeCountdown({ status }: { status: CmeStatus }) {
  if (status.state === "open")   return <span>距收盘 {minutesToHHMM(status.countdown)}</span>;
  if (status.state === "break")  return <span>恢复交易 {minutesToHHMM(status.countdown)}</span>;
  return <span>下次开盘 {minutesToHHMM(status.nextOpenMin)}</span>;
}

// ─── Status badge ────────────────────────────────────────────────────────────

function statusColor(state: MarketStatus["state"]): string {
  switch (state) {
    case "open":  return "#1c8a3e";
    case "pre":
    case "after": return "#b8860b";
    default:      return "#888";
  }
}

function CountdownLine({ status }: { status: MarketStatus }) {
  if (status.state === "open") {
    return <span>距收盘 {minutesToHHMM(status.countdown)}</span>;
  }
  if (status.state === "pre") {
    return <span>距开盘 {minutesToHHMM(status.countdown)}</span>;
  }
  if (status.state === "after") {
    return <span>盘后结束 {minutesToHHMM(status.countdown)}</span>;
  }
  return <span>下次开盘 {minutesToHHMM(status.nextOpenMin)}</span>;
}

// ─── Main component ───────────────────────────────────────────────────────────

export function MarketClock() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const nowCN = nowIn("Asia/Shanghai");
  const nowUS = nowIn("America/New_York");
  const cnStatus = cnMarketStatus(nowCN);
  const usStatus = usMarketStatus(nowUS);
  const cmeStatus = cmeMarketStatus(nowUS);

  const cards = [
    {
      flag: "🇨🇳",
      name: "A股",
      tz: "Asia/Shanghai",
      label: "北京时间",
      now: nowCN,
      status: cnStatus,
    },
    {
      flag: "🇺🇸",
      name: "美股",
      tz: "America/New_York",
      label: "纽约时间",
      now: nowUS,
      status: usStatus,
    },
  ];

  return (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
      {cards.map(({ flag, name, tz, label, now, status }) => (
        <div
          key={tz}
          style={{
            flex: "1 1 180px",
            padding: "12px 16px",
            borderRadius: "var(--radius)",
            border: "1px solid var(--line)",
            background: "var(--panel)",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>{flag} {name}</span>
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                padding: "2px 8px",
                borderRadius: 20,
                background: statusColor(status.state) + "22",
                color: statusColor(status.state),
              }}
            >
              {status.label}
            </span>
          </div>

          {/* Clock */}
          <div>
            <div style={{ fontSize: 22, fontWeight: 700, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.5px" }}>
              {fmtTime(now, tz)}
            </div>
            <div style={{ fontSize: 11, color: "var(--ink-tertiary)", marginTop: 1 }}>
              {fmtDate(now, tz)} · {label}
            </div>
          </div>

          {/* Countdown */}
          <div style={{ fontSize: 12, color: "var(--ink-secondary)" }}>
            <CountdownLine status={status} />
          </div>
        </div>
      ))}

      {/* CME Globex — commodities */}
      <div
        style={{
          flex: "1 1 180px",
          padding: "12px 16px",
          borderRadius: "var(--radius)",
          border: "1px solid var(--line)",
          background: "var(--panel)",
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>🏭 大宗商品</span>
          <span
            style={{
              fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 20,
              background: cmeStatusColor(cmeStatus.state) + "22",
              color: cmeStatusColor(cmeStatus.state),
            }}
          >
            {cmeStatus.label}
          </span>
        </div>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.5px" }}>
            {fmtTime(nowUS, "America/New_York")}
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-tertiary)", marginTop: 1 }}>
            {fmtDate(nowUS, "America/New_York")} · 纽约时间
          </div>
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-secondary)" }}>
          <CmeCountdown status={cmeStatus} />
        </div>
        <div style={{ fontSize: 10, color: "var(--ink-tertiary)", opacity: 0.7 }}>
          XAU · BZ · CL · NG | CME Globex
        </div>
      </div>

    </div>
  );
}
