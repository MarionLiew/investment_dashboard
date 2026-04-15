import { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
  Legend
} from "recharts";
import { buildInvestmentTimeline, buildPortfolioSummary } from "@/lib/services/portfolio";
import type { BaseCurrency } from "@/lib/types";
import { currencyFormatter } from "@/lib/utils";

type Period = "1W" | "1M" | "3M" | "All";
const PERIODS: Period[] = ["1W", "1M", "3M", "All"];

function filterByPeriod<T extends { date: string }>(data: T[], period: Period): T[] {
  if (period === "All") return data;
  const now = new Date();
  const cutoff = new Date(now);
  if (period === "1W") cutoff.setDate(now.getDate() - 7);
  else if (period === "1M") cutoff.setMonth(now.getMonth() - 1);
  else if (period === "3M") cutoff.setMonth(now.getMonth() - 3);
  const cutoffStr = cutoff.toISOString().substring(0, 10);
  return data.filter((d) => d.date >= cutoffStr);
}

function PeriodSelector({ value, onChange }: { value: Period; onChange: (p: Period) => void }) {
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {PERIODS.map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          style={{
            padding: "2px 10px",
            fontSize: 12,
            borderRadius: 6,
            border: "1px solid var(--line)",
            background: value === p ? "var(--accent)" : "transparent",
            color: value === p ? "#fff" : "var(--ink-secondary)",
            cursor: "pointer",
            fontWeight: value === p ? 600 : 400,
            transition: "all 0.15s",
          }}
        >
          {p}
        </button>
      ))}
    </div>
  );
}

function formatShortDate(date: string) {
  return date.substring(5); // "MM-DD"
}

function formatAmount(value: number, baseCurrency: BaseCurrency) {
  return currencyFormatter(baseCurrency).format(value);
}

export function InvestmentTimelineChart({ baseCurrency }: { baseCurrency: BaseCurrency }) {
  const [period, setPeriod] = useState<Period>("All");
  const rawPoints = buildInvestmentTimeline(baseCurrency);
  if (rawPoints.length === 0) return null;

  // Deduplicate by date (keep last value per date)
  const byDate = new Map<string, { date: string; netInflow: number; costBasis: number }>();
  for (const p of rawPoints) {
    byDate.set(p.date, p);
  }
  const allPoints = [...byDate.values()];
  const points = filterByPeriod(allPoints, period);

  const lastDate = allPoints[allPoints.length - 1].date;
  const chartData = points.map((p) => ({
    date: formatShortDate(p.date),
    累计投入: p.netInflow,
    已买入成本: p.costBasis
  }));

  // Append a "today" point if different from last
  const today = new Date().toISOString().substring(0, 10);
  if (today !== lastDate && points.length > 0) {
    chartData.push({
      date: formatShortDate(today),
      累计投入: points[points.length - 1].netInflow,
      已买入成本: points[points.length - 1].costBasis
    });
  }

  const formatter = currencyFormatter(baseCurrency);
  const abbrev = baseCurrency === "CNY" ? "万" : "K";
  const divisor = baseCurrency === "CNY" ? 10000 : 1000;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
        <PeriodSelector value={period} onChange={setPeriod} />
      </div>
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="colorInflow" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.15} />
            <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorCost" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--positive)" stopOpacity={0.15} />
            <stop offset="95%" stopColor="var(--positive)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "var(--ink-tertiary)" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "var(--ink-tertiary)" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `${(v / divisor).toFixed(1)}${abbrev}`}
        />
        <Tooltip
          formatter={(value) => formatter.format(Number(value))}
          contentStyle={{
            fontSize: 12,
            border: "1px solid var(--line)",
            borderRadius: "var(--radius-sm)",
            background: "var(--panel)"
          }}
          labelStyle={{ color: "var(--ink-secondary)" }}
        />
        <Legend
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
        />
        <Area
          type="monotone"
          dataKey="累计投入"
          stroke="var(--accent)"
          strokeWidth={2}
          fill="url(#colorInflow)"
          dot={false}
        />
        <Area
          type="monotone"
          dataKey="已买入成本"
          stroke="var(--positive)"
          strokeWidth={2}
          fill="url(#colorCost)"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
    </div>
  );
}

export function AccountReturnChart({ baseCurrency }: { baseCurrency: BaseCurrency }) {
  const summary = buildPortfolioSummary(baseCurrency);
  const formatter = currencyFormatter(baseCurrency);

  const accounts = summary.accounts.filter((a) => a.totalNetInflowBase > 0);
  if (accounts.length === 0) return null;

  const maxValue = Math.max(...accounts.map((a) => Math.abs(a.marketValueBase)));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {accounts.map((account) => {
        const rate = account.cumulativeReturnRate;
        const isPositive = account.cumulativeReturnBase >= 0;
        const barWidth = maxValue > 0 ? (account.marketValueBase / maxValue) * 100 : 0;
        return (
          <div key={account.accountId}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13 }}>
              <span style={{ fontWeight: 500 }}>{account.accountName}</span>
              <span>
                <span style={{ color: "var(--ink-secondary)", marginRight: 12 }}>
                  净值 {formatter.format(account.marketValueBase)}
                </span>
                {rate !== null && (
                  <span className={isPositive ? "positive" : "negative"} style={{ fontWeight: 600 }}>
                    {isPositive ? "+" : ""}{(rate * 100).toFixed(2)}%
                  </span>
                )}
              </span>
            </div>
            <div style={{ height: 8, borderRadius: 4, background: "var(--bg)", overflow: "hidden", position: "relative" }}>
              <div style={{
                height: "100%",
                width: `${barWidth}%`,
                borderRadius: 4,
                background: isPositive ? "var(--positive)" : "var(--negative)",
                opacity: 0.7,
                transition: "width 0.4s ease"
              }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: 11, color: "var(--ink-tertiary)" }}>
              <span>投入 {formatter.format(account.totalNetInflowBase)}</span>
              <span>
                {isPositive ? "收益 +" : "亏损 "}
                {formatter.format(Math.abs(account.cumulativeReturnBase))}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function ReturnRateHistoryChart({ baseCurrency }: { baseCurrency: BaseCurrency }) {
  const [period, setPeriod] = useState<Period>("All");
  const summary = buildPortfolioSummary(baseCurrency);
  const allPts = summary.dailyPortfolioValues.filter((d) => d.returnRate != null);
  if (allPts.length === 0) return null;

  const pts = filterByPeriod(allPts, period);
  const chartData = pts.map((d) => ({
    date: d.date.substring(5),   // "MM-DD"
    收益率: parseFloat(((d.returnRate as number) * 100).toFixed(2)),
  }));

  const isAllNegative = chartData.every((d) => d["收益率"] <= 0);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
        <PeriodSelector value={period} onChange={setPeriod} />
      </div>
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="colorReturnPos" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#1c8a3e" stopOpacity={0.18} />
            <stop offset="95%" stopColor="#1c8a3e" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorReturnNeg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#c0392b" stopOpacity={0.18} />
            <stop offset="95%" stopColor="#c0392b" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "var(--ink-tertiary)" }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 11, fill: "var(--ink-tertiary)" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `${v.toFixed(1)}%`}
        />
        <Tooltip
          formatter={(value) => [`${Number(value).toFixed(2)}%`, "已实现收益率"]}
          contentStyle={{
            fontSize: 12,
            border: "1px solid var(--line)",
            borderRadius: "var(--radius-sm)",
            background: "var(--panel)"
          }}
          labelStyle={{ color: "var(--ink-secondary)" }}
        />
        <ReferenceLine y={0} stroke="#aaa" strokeDasharray="4 2" strokeWidth={1} />
        <Area
          type="monotone"
          dataKey="收益率"
          stroke={isAllNegative ? "#c0392b" : "#1c8a3e"}
          strokeWidth={2}
          fill={isAllNegative ? "url(#colorReturnNeg)" : "url(#colorReturnPos)"}
          dot={false}
          activeDot={{ r: 4 }}
        />
      </AreaChart>
    </ResponsiveContainer>
    </div>
  );
}
