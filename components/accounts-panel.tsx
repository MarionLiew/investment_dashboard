import { useState } from "react";
import { buildAccountPerformance } from "@/lib/services/portfolio";
import { db } from "@/lib/db";
import { makeId } from "@/lib/utils";
import type { Account, AccountSourceType, BaseCurrency } from "@/lib/types";
import { currencyFormatter } from "@/lib/utils";

const CURRENCIES: BaseCurrency[] = ["CNY", "USD"];
const SOURCE_TYPES: AccountSourceType[] = ["manual", "okx", "broker", "fund_platform"];
const SOURCE_LABELS: Record<AccountSourceType, string> = {
  manual: "手动",
  okx: "OKX",
  broker: "券商",
  fund_platform: "基金平台"
};

export function AccountsPanel({ baseCurrency }: { baseCurrency: BaseCurrency }) {
  const [version, setVersion] = useState(0);
  const [showNewForm, setShowNewForm] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // New account form state
  const [newName, setNewName] = useState("");
  const [newSource, setNewSource] = useState<AccountSourceType>("manual");
  const [newCurrency, setNewCurrency] = useState<BaseCurrency>("CNY");

  const accounts = db.getAccounts();

  function handleCurrencyChange(accountId: string, currency: BaseCurrency) {
    db.updateAccount(accountId, { baseCurrency: currency });
    setVersion((v) => v + 1);
  }

  function handleAddAccount() {
    if (!newName.trim()) return;
    db.addAccount({
      id: makeId("acct"),
      sourceType: newSource,
      name: newName.trim(),
      baseCurrency: newCurrency,
      status: "active",
      updatedAt: new Date().toISOString()
    });
    setNewName("");
    setNewSource("manual");
    setNewCurrency("CNY");
    setShowNewForm(false);
    setVersion((v) => v + 1);
  }

  function handleDeleteAccount(id: string) {
    db.deleteAccount(id);
    setConfirmDelete(null);
    setVersion((v) => v + 1);
  }

  // Compute performance per-account using each account's own baseCurrency
  const performances = accounts.map((account: Account) => {
    const allPerf = buildAccountPerformance(account.baseCurrency);
    const perf = allPerf.find((p) => p.accountId === account.id)!;
    return { account, perf };
  });

  return (
    <div className="panel">
      <div className="panel-heading">
        <h3>账户表现</h3>
        <button
          className="btn-primary"
          style={{ fontSize: 12, padding: "4px 12px" }}
          onClick={() => setShowNewForm((v) => !v)}
        >
          {showNewForm ? "收起" : "+ 新建账户"}
        </button>
      </div>

      {/* New account form */}
      {showNewForm && (
        <div className="confirm-box" style={{ marginBottom: 16 }}>
          <p style={{ fontWeight: 600, marginBottom: 12 }}>新建账户</p>
          <div style={{ display: "grid", gap: 10 }}>
            <div>
              <label style={{ fontSize: 12, color: "var(--ink-secondary)", display: "block", marginBottom: 4 }}>
                账户名称
              </label>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="如：招商证券、长桥美股"
              />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--ink-secondary)", display: "block", marginBottom: 4 }}>
                  账户类型
                </label>
                <select value={newSource} onChange={(e) => setNewSource(e.target.value as AccountSourceType)}>
                  {SOURCE_TYPES.map((s) => (
                    <option key={s} value={s}>{SOURCE_LABELS[s]}</option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 12, color: "var(--ink-secondary)", display: "block", marginBottom: 4 }}>
                  计价货币
                </label>
                <select value={newCurrency} onChange={(e) => setNewCurrency(e.target.value as BaseCurrency)}>
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
            <button className="btn-primary" onClick={handleAddAccount} disabled={!newName.trim()}>
              创建
            </button>
            <button className="chip" onClick={() => setShowNewForm(false)}>取消</button>
          </div>
        </div>
      )}

      <div className="cards-two-up" key={version}>
        {performances.map(({ account, perf }) => {
          const formatter = currencyFormatter(account.baseCurrency);
          const isConfirmingDelete = confirmDelete === account.id;
          return (
            <article key={account.id} className="account-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
                <div>
                  <p className="eyebrow">{SOURCE_LABELS[account.sourceType] ?? account.sourceType}</p>
                  <h4>{account.name}</h4>
                </div>
                <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                  {CURRENCIES.map((c) => (
                    <button
                      key={c}
                      onClick={() => handleCurrencyChange(account.id, c)}
                      className={account.baseCurrency === c ? "chip active" : "chip"}
                      style={{ cursor: "pointer", border: "none", fontSize: "12px" }}
                    >
                      {c}
                    </button>
                  ))}
                  {!isConfirmingDelete ? (
                    <button
                      className="chip"
                      style={{ color: "var(--negative)", fontSize: 12 }}
                      onClick={() => setConfirmDelete(account.id)}
                    >
                      删除
                    </button>
                  ) : (
                    <>
                      <button
                        className="chip"
                        style={{ color: "var(--negative)", fontWeight: 600, fontSize: 12 }}
                        onClick={() => handleDeleteAccount(account.id)}
                      >
                        确认删除
                      </button>
                      <button className="chip" style={{ fontSize: 12 }} onClick={() => setConfirmDelete(null)}>
                        取消
                      </button>
                    </>
                  )}
                </div>
              </div>
              <dl>
                <div>
                  <dt>账户净值</dt>
                  <dd>{formatter.format(perf.marketValueBase)}</dd>
                </div>
                <div>
                  <dt>累计收益</dt>
                  <dd>
                    <span className={perf.cumulativeReturnBase >= 0 ? "positive" : "negative"}>
                      {formatter.format(perf.cumulativeReturnBase)}
                    </span>
                    {perf.cumulativeReturnRate !== null && (
                      <span
                        className={perf.cumulativeReturnBase >= 0 ? "positive" : "negative"}
                        style={{ fontSize: 11, marginLeft: 6 }}
                      >
                        {perf.cumulativeReturnBase >= 0 ? "+" : ""}
                        {(perf.cumulativeReturnRate * 100).toFixed(2)}%
                      </span>
                    )}
                  </dd>
                </div>
                <div>
                  <dt>累计净投入</dt>
                  <dd>{formatter.format(perf.totalNetInflowBase)}</dd>
                </div>
                <div>
                  <dt>现金余额</dt>
                  <dd>{formatter.format(perf.cashBalanceBase)}</dd>
                </div>
              </dl>
            </article>
          );
        })}
      </div>
    </div>
  );
}
