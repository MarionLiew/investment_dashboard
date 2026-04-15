import { useState } from "react";
import { db } from "@/lib/db";
import { ensureAsset } from "@/lib/services/assets";
import { makeId } from "@/lib/utils";
import type { AssetType, TransactionType } from "@/lib/types";

const TRANSACTION_TYPES: { value: TransactionType; label: string }[] = [
  { value: "buy", label: "买入" },
  { value: "sell", label: "卖出" },
  { value: "deposit", label: "入金" },
  { value: "withdrawal", label: "出金" },
  { value: "dividend", label: "分红" },
  { value: "interest", label: "利息" },
  { value: "fee", label: "手续费" }
];

const ASSET_TYPES: { value: AssetType; label: string }[] = [
  { value: "stock", label: "股票" },
  { value: "fund", label: "基金" },
  { value: "crypto", label: "加密货币" },
  { value: "cash", label: "现金" }
];

function toLocalDatetimeValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

interface Props {
  onAdded: () => void;
}

export function TransactionForm({ onAdded }: Props) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const accounts = db.getAccounts();
  const assets = db.getAssets();

  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "");
  const [symbol, setSymbol] = useState("");
  const [type, setType] = useState<TransactionType>("buy");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [fee, setFee] = useState("0");
  const [currency, setCurrency] = useState("CNY");
  const [executedAt, setExecutedAt] = useState(toLocalDatetimeValue(new Date()));

  // Extra fields shown when symbol not found in existing assets
  const [assetType, setAssetType] = useState<AssetType>("stock");
  const [assetName, setAssetName] = useState("");
  const [market, setMarket] = useState("");

  const matchedAsset = symbol.trim()
    ? assets.find((a) => a.symbol.toLowerCase() === symbol.trim().toLowerCase())
    : undefined;
  const needsAssetDetails = symbol.trim().length > 0 && !matchedAsset;

  function reset() {
    setSymbol("");
    setType("buy");
    setQuantity("");
    setPrice("");
    setFee("0");
    setCurrency("CNY");
    setExecutedAt(toLocalDatetimeValue(new Date()));
    setAssetType("stock");
    setAssetName("");
    setMarket("");
    setError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    const qty = parseFloat(quantity);
    const px = parseFloat(price);
    const f = parseFloat(fee);

    if (!accountId) return setError("请选择账户");
    if (!symbol.trim()) return setError("请输入资产代码");
    if (isNaN(qty) || qty <= 0) return setError("数量必须大于 0");
    if (isNaN(px) || px < 0) return setError("价格不能为负数");
    if (isNaN(f) || f < 0) return setError("手续费不能为负数");
    if (needsAssetDetails && !assetName.trim()) return setError("请填写资产名称");
    if (needsAssetDetails && !market.trim()) return setError("请填写市场代码（如 CN-SH、CRYPTO）");

    setSubmitting(true);
    try {
      const asset = ensureAsset(
        matchedAsset ?? {
          symbol: symbol.trim().toUpperCase(),
          name: assetName.trim(),
          assetType,
          market: market.trim(),
          currency
        }
      );

      db.addTransaction({
        id: makeId("txn"),
        accountId,
        assetId: asset.id,
        type,
        quantity: qty,
        price: px,
        fee: f,
        currency,
        executedAt: new Date(executedAt).toISOString()
      });

      reset();
      setOpen(false);
      onAdded();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="panel" style={{ marginBottom: 0 }}>
      <div className="panel-heading" style={{ marginBottom: open ? 16 : 0 }}>
        <h3>录入交易</h3>
        <button
          className={open ? "chip active" : "chip"}
          onClick={() => { setOpen((v) => !v); setError(""); }}
        >
          {open ? "收起" : "+ 新增"}
        </button>
      </div>

      {open && (
        <form onSubmit={handleSubmit} className="txn-form">
          <div className="form-row">
            <label>
              账户
              <select value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </label>

            <label>
              类型
              <select value={type} onChange={(e) => setType(e.target.value as TransactionType)}>
                {TRANSACTION_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </label>

            <label>
              货币
              <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                <option value="CNY">CNY</option>
                <option value="USD">USD</option>
              </select>
            </label>
          </div>

          <div className="form-row">
            <label>
              资产代码
              <input
                type="text"
                placeholder="如 BTC、600519"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
              />
              {matchedAsset && (
                <span className="form-hint">✓ {matchedAsset.name}</span>
              )}
            </label>

            <label>
              数量
              <input
                type="number"
                placeholder="0"
                min="0"
                step="any"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
              />
            </label>

            <label>
              价格
              <input
                type="number"
                placeholder="0.00"
                min="0"
                step="any"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
              />
            </label>

            <label>
              手续费
              <input
                type="number"
                placeholder="0"
                min="0"
                step="any"
                value={fee}
                onChange={(e) => setFee(e.target.value)}
              />
            </label>
          </div>

          {needsAssetDetails && (
            <div className="form-row form-hint-row">
              <span className="form-hint">新资产，请补充信息：</span>
              <label>
                资产类型
                <select value={assetType} onChange={(e) => setAssetType(e.target.value as AssetType)}>
                  {ASSET_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </label>
              <label>
                资产名称
                <input
                  type="text"
                  placeholder="如 贵州茅台"
                  value={assetName}
                  onChange={(e) => setAssetName(e.target.value)}
                />
              </label>
              <label>
                市场
                <input
                  type="text"
                  placeholder="如 CN-SH、CRYPTO"
                  value={market}
                  onChange={(e) => setMarket(e.target.value)}
                />
              </label>
            </div>
          )}

          <div className="form-row">
            <label>
              成交时间
              <input
                type="datetime-local"
                value={executedAt}
                onChange={(e) => setExecutedAt(e.target.value)}
              />
            </label>
          </div>

          {error && <p className="form-error">{error}</p>}

          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? "提交中…" : "确认录入"}
            </button>
            <button type="button" className="chip" onClick={() => { reset(); setOpen(false); }}>
              取消
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
