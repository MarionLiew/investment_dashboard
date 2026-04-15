import { db } from "@/lib/db";
import { Connector, ConnectorSyncResult } from "@/lib/connectors/base";
import { ensureAsset } from "@/lib/services/assets";
import { makeId } from "@/lib/utils";
import type { PriceSnapshot, Transaction } from "@/lib/types";

const PROXY = "http://localhost:3001/api/okx";

// OKX API response shapes
type OkxBalanceItem = { ccy: string; bal: string; availBal: string; frozenBal: string };
type OkxFillItem = {
  instId: string;
  tradeId: string;
  fillPx: string;
  fillSz: string;
  side: "buy" | "sell";
  feeCcy: string;
  fee: string; // negative = cost
  ts: string;
};
type OkxResp<T> = { code: string; msg: string; data: T[] };

type OkxCreds = { apiKey: string; secretKey: string; passphrase: string };

function parseCcy(instId: string): string {
  // "BTC-USDT" → "BTC", "BTC-USDT-SWAP" → "BTC"
  return instId.split("-")[0];
}

async function okxGet<T>(path: string, creds?: OkxCreds): Promise<OkxResp<T>> {
  const headers: Record<string, string> = {};
  if (creds) {
    headers["X-OKX-API-KEY"] = creds.apiKey;
    headers["X-OKX-SECRET-KEY"] = creds.secretKey;
    headers["X-OKX-PASSPHRASE"] = creds.passphrase;
  }
  const res = await fetch(`${PROXY}${path}`, { headers });
  if (!res.ok) throw new Error(`OKX proxy error: ${res.status}`);
  return res.json() as Promise<OkxResp<T>>;
}

export class OkxConnector implements Connector {
  async syncAccount(accountId: string, creds?: OkxCreds): Promise<ConnectorSyncResult> {
    const errors: string[] = [];
    let importedTransactions = 0;
    let updatedPrices = 0;

    // ── 1. Spot fills (trade history) ──────────────────────────
    try {
      const fillsResp = await okxGet<OkxFillItem>(
        "/api/v5/trade/fills-history?instType=SPOT&limit=100",
        creds
      );

      if (fillsResp.code !== "0") {
        errors.push(`fills: ${fillsResp.msg}`);
      } else {
        const transactions = this.fillsToTransactions(fillsResp.data, accountId);
        for (const txn of transactions) {
          const exists = db.getTransactions().some((t) => t.id === txn.id);
          if (!exists) {
            db.addTransaction(txn);
            importedTransactions++;
          }
        }
      }
    } catch (e) {
      errors.push(`fills: ${String(e)}`);
    }

    // ── 2. Asset balances → latest prices ──────────────────────
    try {
      const balResp = await okxGet<OkxBalanceItem>("/api/v5/asset/balances", creds);
      if (balResp.code !== "0") {
        // Try trading account balance as fallback
        const acctResp = await okxGet<{ details: OkxBalanceItem[] }>("/api/v5/account/balance", creds);
        if (acctResp.code === "0") {
          const details = acctResp.data[0]?.details ?? [];
          for (const item of details) {
            if (parseFloat(item.bal) > 0) {
              updatedPrices += await this.fetchAndCachePrice(item.ccy, creds);
            }
          }
        } else {
          errors.push(`balances: ${balResp.msg}`);
        }
      } else {
        for (const item of balResp.data) {
          if (parseFloat(item.bal) > 0) {
            updatedPrices += await this.fetchAndCachePrice(item.ccy, creds);
          }
        }
      }
    } catch (e) {
      errors.push(`balances: ${String(e)}`);
    }

    const msg =
      errors.length > 0
        ? `同步部分完成 (导入 ${importedTransactions} 条交易)。错误: ${errors.join("; ")}`
        : `OKX 同步完成，导入 ${importedTransactions} 条交易，更新 ${updatedPrices} 条行情。`;

    return { importedTransactions, updatedPrices, message: msg };
  }

  private fillsToTransactions(fills: OkxFillItem[], accountId: string): Transaction[] {
    return fills.map((fill) => {
      const symbol = parseCcy(fill.instId);
      const asset = ensureAsset({
        assetType: "crypto",
        symbol,
        name: symbol,
        market: "CRYPTO",
        currency: "USD"
      });

      return {
        id: `okx_${fill.tradeId}`,
        accountId,
        assetId: asset.id,
        type: fill.side,
        quantity: parseFloat(fill.fillSz),
        price: parseFloat(fill.fillPx),
        fee: Math.abs(parseFloat(fill.fee)),
        currency: "USD",
        executedAt: new Date(parseInt(fill.ts)).toISOString(),
        note: "OKX 实盘同步",
        metadata: { instId: fill.instId, tradeId: fill.tradeId }
      };
    });
  }

  private async fetchAndCachePrice(ccy: string, creds?: OkxCreds): Promise<number> {
    if (ccy === "USDT" || ccy === "USDC") {
      // Stablecoins = 1 USD
      const asset = ensureAsset({ assetType: "cash", symbol: ccy, name: ccy, market: "CRYPTO", currency: "USD" });
      db.upsertPrice({ assetId: asset.id, price: 1, currency: "USD", updatedAt: new Date().toISOString(), source: "stablecoin", stale: false });
      return 1;
    }

    try {
      const instId = `${ccy}-USDT`;
      const tickerResp = await okxGet<{ last: string }>(`/api/v5/market/ticker?instId=${instId}`, creds);
      if (tickerResp.code === "0" && tickerResp.data[0]) {
        const price = parseFloat(tickerResp.data[0].last);
        if (price > 0) {
          const asset = ensureAsset({
            assetType: "crypto",
            symbol: ccy,
            name: ccy,
            market: "CRYPTO",
            currency: "USD"
          });
          const snapshot: PriceSnapshot = {
            assetId: asset.id,
            price,
            currency: "USD",
            updatedAt: new Date().toISOString(),
            source: "okx-ticker",
            stale: false
          };
          db.upsertPrice(snapshot);
          return 1;
        }
      }
    } catch {
      // ignore
    }
    return 0;
  }
}

export const okxConnector = new OkxConnector();
