import { Link } from "react-router-dom";
import { buildPortfolioSummary } from "@/lib/services/portfolio";
import { getFxOverview } from "@/lib/services/fx";
import type { BaseCurrency } from "@/lib/types";
import { currencyFormatter, percentFormatter, fmtCST } from "@/lib/utils";
import { InvestmentTimelineChart, AccountReturnChart, ReturnRateHistoryChart } from "@/components/portfolio-charts";
import { MarketClock } from "@/components/market-clock";

const currencyOptions: BaseCurrency[] = ["CNY", "USD"];

const ASSET_TYPE_LABELS: Record<string, string> = {
  stock: "股票",
  fund: "基金",
  crypto: "加密",
  cash: "现金"
};

export function Dashboard({ baseCurrency }: { baseCurrency: BaseCurrency }) {
  const summary = buildPortfolioSummary(baseCurrency);
  const formatter = currencyFormatter(baseCurrency);
  const fxRates = getFxOverview();
  const returnRate = summary.cumulativeReturnRate;
  const isPositive = summary.cumulativeReturnBase >= 0;

  return (
    <div className="page-grid">
      <section className="hero-card">
        <div className="hero-copy">
          <p className="eyebrow">Portfolio</p>
          <h2>股票、基金、加密资产综合看板</h2>
          <p>
            手动账户与 OKX 实盘同步，统一按 {baseCurrency} 汇总。
            总资产含未投出现金；浮盈亏仅计持仓部分。
          </p>
        </div>
        <div className="currency-switch">
          {currencyOptions.map((option) => (
            <Link
              key={option}
              to={`/?baseCurrency=${option}`}
              className={option === baseCurrency ? "chip active" : "chip"}
            >
              {option}
            </Link>
          ))}
        </div>
      </section>

      {/* 5 metric cards */}
      <section className="metrics-grid">
        <article className="metric-card">
          <span>总资产</span>
          <strong>{formatter.format(summary.totalMarketValueBase)}</strong>
          <small style={{ color: "var(--ink-tertiary)", fontSize: 11 }}>
            含现金 {formatter.format(summary.accounts.reduce((s, a) => s + a.cashBalanceBase, 0))}
          </small>
        </article>
        <article className="metric-card">
          <span>累计收益</span>
          <strong className={isPositive ? "positive" : "negative"}>
            {formatter.format(summary.cumulativeReturnBase)}
          </strong>
          {returnRate !== null && (
            <small className={isPositive ? "positive" : "negative"} style={{ fontSize: 12 }}>
              {isPositive ? "+" : ""}{(returnRate * 100).toFixed(2)}%
            </small>
          )}
        </article>
        <article className="metric-card">
          <span>浮盈亏（持仓）</span>
          <strong className={summary.unrealizedPnlBase >= 0 ? "positive" : "negative"}>
            {formatter.format(summary.unrealizedPnlBase)}
          </strong>
        </article>
        <article className="metric-card">
          <span>已实现收益</span>
          <strong className={summary.totalRealizedPnlBase >= 0 ? "positive" : "negative"}>
            {formatter.format(summary.totalRealizedPnlBase)}
          </strong>
        </article>
        <article className="metric-card">
          <span>累计净投入</span>
          <strong>{formatter.format(summary.totalNetInflowBase)}</strong>
        </article>
      </section>

      {/* Market clock */}
      <section className="panel">
        <div className="panel-heading">
          <h3>市场时间</h3>
        </div>
        <MarketClock />
      </section>

      {/* Account return bars */}
      <section className="panel">
        <div className="panel-heading">
          <h3>账户收益率</h3>
          <span>{summary.accounts.length} 个账户</span>
        </div>
        <AccountReturnChart baseCurrency={baseCurrency} />
      </section>

      {/* Return rate history chart */}
      <section className="panel">
        <div className="panel-heading">
          <h3>收益率历史走势</h3>
          <span>已实现盈亏收益率（不含浮盈）</span>
        </div>
        <ReturnRateHistoryChart baseCurrency={baseCurrency} />
      </section>

      {/* Investment timeline chart */}
      <section className="panel">
        <div className="panel-heading">
          <h3>资金投入走势</h3>
          <span>累计投入 vs 已买入成本</span>
        </div>
        <InvestmentTimelineChart baseCurrency={baseCurrency} />
      </section>

      {/* Asset allocation */}
      <section className="panel">
        <div className="panel-heading">
          <h3>持仓资产构成</h3>
          <span>行情更新 {fmtCST(summary.priceTimestamp)}</span>
        </div>
        <div className="category-list">
          {summary.categories.map((category) => (
            <div key={category.assetType} className="category-row">
              <div>
                <strong>{ASSET_TYPE_LABELS[category.assetType] ?? category.assetType.toUpperCase()}</strong>
                <p>{formatter.format(category.marketValueBase)}</p>
              </div>
              <div>
                <span>{percentFormatter.format(category.weight)}</span>
                <p className={category.unrealizedPnlBase >= 0 ? "positive" : "negative"}>
                  {category.unrealizedPnlBase >= 0 ? "+" : ""}
                  {formatter.format(category.unrealizedPnlBase)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* FX rates */}
      <section className="panel">
        <div className="panel-heading">
          <h3>汇率</h3>
          <span>CNY / USD 折算</span>
        </div>
        <div className="fx-list">
          {fxRates.map((rate) => (
            <div key={rate.pair} className="fx-card">
              <strong>{rate.pair}</strong>
              <p>{rate.rate.toFixed(4)}</p>
              <span>{rate.stale ? "缓存" : "最新"}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
