import { useState } from "react";
import { db } from "@/lib/db";
import { okxConnector } from "@/lib/connectors/okx";
import { makeId, fmtCST } from "@/lib/utils";
import type { BaseCurrency } from "@/lib/types";

export function DataSourcesPanel() {
  const [, forceUpdate] = useState(0);
  const [confirm, setConfirm] = useState<"clear" | "reset" | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null); // accountId being synced
  const [syncMsg, setSyncMsg] = useState<Record<string, string>>({});

  // OKX config form state
  const [showConfigForm, setShowConfigForm] = useState(false);
  const [configAccountId, setConfigAccountId] = useState(""); // empty = new account
  const [configAccountName, setConfigAccountName] = useState("");
  const [configApiKey, setConfigApiKey] = useState("");
  const [configSecretKey, setConfigSecretKey] = useState("");
  const [configPassphrase, setConfigPassphrase] = useState("");
  const [configCurrency, setConfigCurrency] = useState<BaseCurrency>("USD");

  const accounts = db.getAccounts().filter((a) => a.sourceType === "okx");
  const configs = db.getConnectorConfigs();
  const logs = db.getSyncLogs();

  function openNewConfig() {
    setConfigAccountId("");
    setConfigAccountName("");
    setConfigApiKey("");
    setConfigSecretKey("");
    setConfigPassphrase("");
    setConfigCurrency("USD");
    setShowConfigForm(true);
  }

  function openEditConfig(accountId: string) {
    const account = db.getAccounts().find((a) => a.id === accountId);
    const config = configs.find((c) => c.accountId === accountId);
    setConfigAccountId(accountId);
    setConfigAccountName(account?.name ?? "");
    setConfigApiKey(config?.apiKey ?? "");
    setConfigSecretKey(config?.secretKey ?? "");
    setConfigPassphrase(config?.passphrase ?? "");
    setConfigCurrency(account?.baseCurrency ?? "USD");
    setShowConfigForm(true);
  }

  function handleSaveConfig() {
    if (!configAccountName.trim()) return;

    let accountId = configAccountId;

    if (!accountId) {
      // Create new account
      accountId = makeId("acct");
      db.addAccount({
        id: accountId,
        sourceType: "okx",
        name: configAccountName.trim(),
        baseCurrency: configCurrency,
        status: "active",
        updatedAt: new Date().toISOString()
      });
    } else {
      db.updateAccount(accountId, {
        name: configAccountName.trim(),
        baseCurrency: configCurrency
      });
    }

    // Upsert connector config
    const existingConfig = configs.find((c) => c.accountId === accountId);
    db.upsertConnectorConfig({
      id: existingConfig?.id ?? makeId("cfg"),
      accountId,
      connector: "okx",
      apiKey: configApiKey.trim(),
      secretKey: configSecretKey.trim(),
      passphrase: configPassphrase.trim(),
      status: "configured",
      lastSyncedAt: existingConfig?.lastSyncedAt
    });

    setShowConfigForm(false);
    forceUpdate((v) => v + 1);
  }

  function handleDeleteAccount(accountId: string) {
    db.deleteAccount(accountId);
    forceUpdate((v) => v + 1);
  }

  async function handleSync(accountId: string) {
    const config = configs.find((c) => c.accountId === accountId);
    const creds = config?.apiKey
      ? { apiKey: config.apiKey, secretKey: config.secretKey, passphrase: config.passphrase }
      : undefined;

    setSyncing(accountId);
    setSyncMsg((m) => ({ ...m, [accountId]: "" }));
    try {
      const result = await okxConnector.syncAccount(accountId, creds);
      db.addSyncLog({
        id: `log_${Date.now()}`,
        accountId,
        connector: "okx",
        status: result.message.includes("错误") ? "error" : "success",
        message: result.message,
        createdAt: new Date().toISOString()
      });
      db.updateAccount(accountId, { status: "active", updatedAt: new Date().toISOString() });
      if (config) {
        db.upsertConnectorConfig({ ...config, lastSyncedAt: new Date().toISOString(), status: "configured" });
      }
      setSyncMsg((m) => ({ ...m, [accountId]: result.message }));
      forceUpdate((v) => v + 1);
    } catch (e) {
      const msg = `同步失败: ${String(e)}`;
      setSyncMsg((m) => ({ ...m, [accountId]: msg }));
      db.addSyncLog({
        id: `log_${Date.now()}`,
        accountId,
        connector: "okx",
        status: "error",
        message: msg,
        createdAt: new Date().toISOString()
      });
    } finally {
      setSyncing(null);
    }
  }

  function handleClear() {
    db.clearAllData();
    setConfirm(null);
    window.location.reload();
  }

  function handleReset() {
    db.resetToSampleData();
    setConfirm(null);
    window.location.reload();
  }

  return (
    <div className="page-grid">
      {/* OKX Accounts */}
      <section className="panel">
        <div className="panel-heading">
          <h3>OKX 实盘账户</h3>
          <button className="btn-primary" style={{ fontSize: 12, padding: "4px 12px" }} onClick={openNewConfig}>
            + 新建账户
          </button>
        </div>

        {accounts.length === 0 && !showConfigForm && (
          <p style={{ fontSize: 13, color: "var(--ink-tertiary)" }}>
            还没有 OKX 账户，点击右上角"新建账户"添加并配置 API 密钥。
          </p>
        )}

        {/* Config form */}
        {showConfigForm && (
          <div className="confirm-box" style={{ marginBottom: 16 }}>
            <p style={{ fontWeight: 600, marginBottom: 12 }}>
              {configAccountId ? "编辑账户" : "新建 OKX 账户"}
            </p>
            <div style={{ display: "grid", gap: 10 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--ink-secondary)", display: "block", marginBottom: 4 }}>
                  账户名称
                </label>
                <input
                  value={configAccountName}
                  onChange={(e) => setConfigAccountName(e.target.value)}
                  placeholder="如：欧易主账户"
                />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--ink-secondary)", display: "block", marginBottom: 4 }}>
                    API Key
                  </label>
                  <input
                    value={configApiKey}
                    onChange={(e) => setConfigApiKey(e.target.value)}
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx"
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--ink-secondary)", display: "block", marginBottom: 4 }}>
                    Passphrase
                  </label>
                  <input
                    type="password"
                    value={configPassphrase}
                    onChange={(e) => setConfigPassphrase(e.target.value)}
                    placeholder="API 通行短语"
                  />
                </div>
              </div>
              <div>
                <label style={{ fontSize: 12, color: "var(--ink-secondary)", display: "block", marginBottom: 4 }}>
                  Secret Key
                </label>
                <input
                  type="password"
                  value={configSecretKey}
                  onChange={(e) => setConfigSecretKey(e.target.value)}
                  placeholder="Secret Key"
                />
              </div>
              <div>
                <label style={{ fontSize: 12, color: "var(--ink-secondary)", display: "block", marginBottom: 4 }}>
                  计价货币
                </label>
                <div style={{ display: "flex", gap: 8 }}>
                  {(["USD", "CNY"] as BaseCurrency[]).map((c) => (
                    <button
                      key={c}
                      type="button"
                      className={configCurrency === c ? "chip active" : "chip"}
                      onClick={() => setConfigCurrency(c)}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
              <button
                className="btn-primary"
                onClick={handleSaveConfig}
                disabled={!configAccountName.trim()}
              >
                保存
              </button>
              <button className="chip" onClick={() => setShowConfigForm(false)}>取消</button>
            </div>
          </div>
        )}

        {/* Account list */}
        {accounts.map((account) => {
          const config = configs.find((c) => c.accountId === account.id);
          const isSyncing = syncing === account.id;
          const msg = syncMsg[account.id];
          const hasKey = !!(config?.apiKey);

          return (
            <div key={account.id} style={{
              border: "1px solid var(--line)",
              borderRadius: "var(--radius-sm)",
              padding: "12px 14px",
              marginBottom: 10
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                <div>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>{account.name}</span>
                  <span style={{ marginLeft: 8, fontSize: 12, color: "var(--ink-tertiary)" }}>
                    {account.baseCurrency}
                  </span>
                  {hasKey ? (
                    <span style={{ marginLeft: 8, fontSize: 11, color: "var(--positive)" }}>API 已配置</span>
                  ) : (
                    <span style={{ marginLeft: 8, fontSize: 11, color: "var(--ink-tertiary)" }}>未配置 API</span>
                  )}
                  {config?.lastSyncedAt && (
                    <span style={{ marginLeft: 8, fontSize: 11, color: "var(--ink-tertiary)" }}>
                      上次同步：{fmtCST(config.lastSyncedAt)}
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="chip" onClick={() => openEditConfig(account.id)}>编辑</button>
                  <button
                    className="btn-primary"
                    onClick={() => handleSync(account.id)}
                    disabled={isSyncing}
                  >
                    {isSyncing ? "同步中…" : "立即同步"}
                  </button>
                  <button
                    className="chip"
                    style={{ color: "var(--negative)" }}
                    onClick={() => handleDeleteAccount(account.id)}
                  >
                    删除
                  </button>
                </div>
              </div>
              {msg && (
                <p style={{
                  marginTop: 10,
                  padding: "6px 10px",
                  borderRadius: "var(--radius-sm)",
                  fontSize: 12,
                  background: msg.includes("失败") || msg.includes("错误") ? "var(--negative-bg)" : "var(--positive-bg)",
                  color: msg.includes("失败") || msg.includes("错误") ? "var(--negative)" : "var(--positive)"
                }}>
                  {msg}
                </p>
              )}
            </div>
          );
        })}
      </section>

      {/* Data management */}
      <section className="panel">
        <div className="panel-heading">
          <h3>数据管理</h3>
          <span>清空或重置本地存储数据</span>
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button
            className="chip"
            style={{ color: "var(--negative)", borderColor: "rgba(192,57,43,0.3)" }}
            onClick={() => setConfirm("clear")}
          >
            清空所有数据
          </button>
          <button className="chip" onClick={() => setConfirm("reset")}>
            恢复示例数据
          </button>
        </div>

        {confirm === "clear" && (
          <div className="confirm-box">
            <p>确定要清空所有账户、交易和流水吗？<strong>此操作不可撤销。</strong></p>
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button
                className="btn-primary"
                style={{ background: "var(--negative)" }}
                onClick={handleClear}
              >
                确认清空
              </button>
              <button className="chip" onClick={() => setConfirm(null)}>取消</button>
            </div>
          </div>
        )}

        {confirm === "reset" && (
          <div className="confirm-box">
            <p>将覆盖当前所有数据，恢复为内置示例数据，确认继续？</p>
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button className="btn-primary" onClick={handleReset}>确认恢复</button>
              <button className="chip" onClick={() => setConfirm(null)}>取消</button>
            </div>
          </div>
        )}
      </section>

      {/* Sync logs */}
      {logs.length > 0 && (
        <section className="panel">
          <div className="panel-heading">
            <h3>同步日志</h3>
            <span>{logs.length} 条记录</span>
          </div>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>账户</th>
                  <th>状态</th>
                  <th>说明</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => {
                  const account = db.getAccounts().find((a) => a.id === log.accountId);
                  return (
                    <tr key={log.id}>
                      <td>{fmtCST(log.createdAt)}</td>
                      <td>{account?.name ?? log.accountId}</td>
                      <td>
                        <span className={log.status === "success" ? "positive" : "negative"}>
                          {log.status === "success" ? "成功" : "失败"}
                        </span>
                      </td>
                      <td>{log.message}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
