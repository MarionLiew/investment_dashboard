import { db } from "@/lib/db";
import { convertAmount } from "@/lib/services/fx";
import { getLatestPrice } from "@/lib/services/pricing";
import {
  AccountPerformance,
  BaseCurrency,
  CategorySummary,
  DailyPortfolioValue,
  PortfolioSummary,
  PositionView,
  Transaction
} from "@/lib/types";
import { round } from "@/lib/utils";

type PositionAccumulator = {
  quantity: number;
  soldQuantity: number;
  investedAmountOriginal: number;
  realizedProceedOriginal: number;
  feesOriginal: number;
};

/**
 * Cash impact of a transaction in its own currency.
 * Positive = cash coming in, negative = cash going out.
 * deposit/transfer_in/sell → positive; buy/withdrawal/transfer_out → negative.
 */
const transactionCashImpact = (transaction: Transaction): number => {
  const gross = transaction.quantity * transaction.price;
  switch (transaction.type) {
    case "deposit":
    case "transfer_in":
      return gross;
    case "withdrawal":
    case "transfer_out":
      return -gross;
    case "buy":
      return -(gross + transaction.fee);
    case "sell":
      return gross - transaction.fee;
    case "dividend":
    case "interest":
      return gross;
    case "fee":
      return -transaction.fee;
    default:
      return 0;
  }
};

/**
 * Build investment positions (buy/sell only).
 * deposit/withdrawal are NOT positions — they are cash-flow events.
 * Uninvested cash is computed separately in buildAccountPerformance.
 */
export const buildPositions = (baseCurrency: BaseCurrency): PositionView[] => {
  const assets = db.getAssets();
  const accounts = db.getAccounts();
  const transactions = [...db.getTransactions()].sort((a, b) =>
    a.executedAt.localeCompare(b.executedAt)
  );
  const map = new Map<string, PositionAccumulator>();

  for (const transaction of transactions) {
    const key = `${transaction.accountId}:${transaction.assetId}`;
    const current =
      map.get(key) ??
      ({
        quantity: 0,
        soldQuantity: 0,
        investedAmountOriginal: 0,
        realizedProceedOriginal: 0,
        feesOriginal: 0
      } satisfies PositionAccumulator);

    switch (transaction.type) {
      case "buy":
        current.quantity += transaction.quantity;
        current.investedAmountOriginal += transaction.quantity * transaction.price + transaction.fee;
        break;
      case "sell":
        current.soldQuantity += transaction.quantity;
        current.quantity -= transaction.quantity;
        current.realizedProceedOriginal += transaction.quantity * transaction.price - transaction.fee;
        break;
      case "dividend":
      case "interest":
        current.realizedProceedOriginal += transaction.quantity * transaction.price;
        break;
      case "fee":
        current.feesOriginal += transaction.fee;
        current.investedAmountOriginal += transaction.fee;
        break;
      // deposit / withdrawal / transfer_in / transfer_out:
      // These are cash-flow events and do NOT create investment positions.
      // Cash balance is computed from transactionCashImpact in buildAccountPerformance.
      default:
        break;
    }

    map.set(key, current);
  }

  const positions: PositionView[] = [];

  map.forEach((value, key) => {
    const [accountId, assetId] = key.split(":");
    const asset = assets.find((item) => item.id === assetId);
    const account = accounts.find((item) => item.id === accountId);
    if (!asset || !account) return;

    if (value.quantity <= 0 && value.soldQuantity <= 0) return;

    const price = getLatestPrice(asset);
    const totalBought = value.quantity + value.soldQuantity;
    const avgCost = totalBought > 0 ? value.investedAmountOriginal / totalBought : 0;
    const costBasisOriginal = avgCost * value.quantity;
    const marketValueOriginal = price && value.quantity > 0 ? value.quantity * price.price : null;
    const marketValueBase =
      marketValueOriginal === null
        ? null
        : convertAmount(marketValueOriginal, price?.currency ?? asset.currency, baseCurrency);
    const costBasisBase = convertAmount(costBasisOriginal, asset.currency, baseCurrency);
    const unrealizedPnlBase =
      marketValueBase === null ? null : round(marketValueBase - costBasisBase);

    const realizedPnlOriginal = value.realizedProceedOriginal - avgCost * value.soldQuantity;
    const realizedPnlBase = round(
      convertAmount(realizedPnlOriginal, asset.currency, baseCurrency)
    );

    positions.push({
      assetId,
      symbol: asset.symbol,
      name: asset.name,
      assetType: asset.assetType,
      market: asset.market,
      accountId,
      accountName: account.name,
      currency: asset.currency,
      quantity: round(value.quantity, 6),
      avgCost: round(avgCost, 6),
      costBasis: round(costBasisOriginal, 2),
      latestPrice: price?.price ?? null,
      latestPriceCurrency: price?.currency ?? null,
      marketValueOriginal: marketValueOriginal === null ? null : round(marketValueOriginal, 2),
      marketValueBase: marketValueBase === null ? null : round(marketValueBase, 2),
      costBasisBase: round(costBasisBase, 2),
      unrealizedPnlBase,
      unrealizedPnlRate:
        unrealizedPnlBase === null || costBasisBase === 0 ? null : unrealizedPnlBase / costBasisBase,
      realizedPnlBase,
      soldQuantity: round(value.soldQuantity, 6),
      priceUpdatedAt: price?.updatedAt ?? null,
      stalePrice: price?.stale ?? true
    });
  });

  return positions.sort((a, b) => (b.marketValueBase ?? 0) - (a.marketValueBase ?? 0));
};

export const buildAccountPerformance = (baseCurrency: BaseCurrency): AccountPerformance[] => {
  const accounts = db.getAccounts();
  const positions = buildPositions(baseCurrency);
  const connectorConfigs = db.getConnectorConfigs();
  const transactions = db.getTransactions();

  return accounts.map((account) => {
    const positionSlice = positions.filter((item) => item.accountId === account.id);
    const investmentValueBase = round(
      positionSlice.reduce((sum, item) => sum + (item.marketValueBase ?? 0), 0),
      2
    );
    const costBasisBase = round(
      positionSlice.reduce((sum, item) => sum + item.costBasisBase, 0),
      2
    );

    const accountTransactions = transactions.filter((item) => item.accountId === account.id);

    // Cash balance = sum of all transaction cash impacts (converted to baseCurrency).
    // This correctly shows uninvested cash: deposits - buys + sells - withdrawals.
    let cashBalanceBase = 0;
    let totalNetInflowBase = 0;
    let transferredOutBase = 0;

    for (const txn of accountTransactions) {
      const impact = transactionCashImpact(txn);
      const impactBase = convertAmount(impact, txn.currency, baseCurrency);
      cashBalanceBase += impactBase;

      // Net inflow = money brought in from outside (deposits / transfer-ins)
      if (txn.type === "deposit" || txn.type === "transfer_in") {
        totalNetInflowBase += convertAmount(txn.quantity * txn.price, txn.currency, baseCurrency);
      }
      if (txn.type === "withdrawal" || txn.type === "transfer_out") {
        const amt = convertAmount(txn.quantity * txn.price, txn.currency, baseCurrency);
        totalNetInflowBase -= amt;
        transferredOutBase += amt;
      }
    }

    // Total account value = investments (market value) + uninvested cash
    const marketValueBase = round(investmentValueBase + cashBalanceBase, 2);
    const unrealizedPnlBase = round(marketValueBase - costBasisBase - cashBalanceBase, 2); // pure investment PnL
    const cumulativeReturnBase = round(marketValueBase + transferredOutBase - totalNetInflowBase, 2);
    const cumulativeReturnRate =
      totalNetInflowBase > 0 ? round(cumulativeReturnBase / totalNetInflowBase, 4) : null;

    const connectorConfig = connectorConfigs.find((item) => item.accountId === account.id);

    return {
      accountId: account.id,
      accountName: account.name,
      sourceType: account.sourceType,
      status: account.status,
      baseCurrency,
      marketValueBase,
      costBasisBase,
      unrealizedPnlBase,
      totalNetInflowBase: round(totalNetInflowBase, 2),
      transferredOutBase: round(transferredOutBase, 2),
      cumulativeReturnBase,
      cumulativeReturnRate,
      cashBalanceBase: round(cashBalanceBase, 2),
      lastSyncedAt: connectorConfig?.lastSyncedAt
    };
  });
};

export const buildPortfolioSummary = (baseCurrency: BaseCurrency = "CNY"): PortfolioSummary => {
  const positions = buildPositions(baseCurrency);
  const accounts = buildAccountPerformance(baseCurrency);

  // Total market value = investment positions + uninvested cash across all accounts
  const totalMarketValueBase = round(
    accounts.reduce((sum, a) => sum + a.marketValueBase, 0),
    2
  );
  // Cost basis is investment-only (no cash)
  const totalCostBasisBase = round(
    positions.reduce((sum, item) => sum + item.costBasisBase, 0),
    2
  );
  // Unrealized PnL = market value of investments vs cost (cash excluded from both sides)
  const totalUnrealizedPnlBase = round(
    positions.reduce((sum, item) => sum + (item.unrealizedPnlBase ?? 0), 0),
    2
  );
  const totalRealizedPnlBase = round(
    positions.reduce((sum, item) => sum + item.realizedPnlBase, 0),
    2
  );
  const totalNetInflowBase = round(
    accounts.reduce((sum, item) => sum + item.totalNetInflowBase, 0),
    2
  );
  const totalTransferredOutBase = round(
    accounts.reduce((sum, item) => sum + item.transferredOutBase, 0),
    2
  );
  const cumulativeReturnBase = round(
    totalMarketValueBase + totalTransferredOutBase - totalNetInflowBase,
    2
  );
  const cumulativeReturnRate =
    totalNetInflowBase > 0 ? round(cumulativeReturnBase / totalNetInflowBase, 4) : null;

  const categoryMap = new Map<string, CategorySummary>();
  for (const position of positions) {
    if (position.quantity <= 0) continue;
    const current =
      categoryMap.get(position.assetType) ??
      ({
        assetType: position.assetType,
        marketValueBase: 0,
        costBasisBase: 0,
        unrealizedPnlBase: 0,
        weight: 0
      } satisfies CategorySummary);
    current.marketValueBase += position.marketValueBase ?? 0;
    current.costBasisBase += position.costBasisBase;
    current.unrealizedPnlBase += position.unrealizedPnlBase ?? 0;
    categoryMap.set(position.assetType, current);
  }

  const categories = [...categoryMap.values()]
    .map((item) => ({
      ...item,
      marketValueBase: round(item.marketValueBase, 2),
      costBasisBase: round(item.costBasisBase, 2),
      unrealizedPnlBase: round(item.unrealizedPnlBase, 2),
      weight:
        totalMarketValueBase === 0 ? 0 : round(item.marketValueBase / totalMarketValueBase, 4)
    }))
    .sort((a, b) => b.marketValueBase - a.marketValueBase);

  const newestPriceTimestamp =
    db
      .getPrices()
      .map((item) => item.updatedAt)
      .sort()
      .at(-1) ?? new Date().toISOString();

  // Read pre-computed TWR + daily return series from connector configs (written by OKX sync)
  const accountIds = new Set(accounts.map((a) => a.accountId));
  let realizedTwr: number | null = null;
  let dailyPortfolioValues: DailyPortfolioValue[] = [];
  for (const cfg of db.getConnectorConfigs()) {
    if (!accountIds.has(cfg.accountId)) continue;
    if (realizedTwr === null && cfg.realizedTwr != null) realizedTwr = cfg.realizedTwr;
    if (cfg.dailyPortfolioValues?.length) dailyPortfolioValues = cfg.dailyPortfolioValues;
  }

  return {
    baseCurrency,
    totalMarketValueBase,
    totalCostBasisBase,
    totalNetInflowBase,
    totalTransferredOutBase,
    cumulativeReturnBase,
    cumulativeReturnRate,
    realizedTwr,
    dailyPortfolioValues,
    unrealizedPnlBase: totalUnrealizedPnlBase,
    totalRealizedPnlBase,
    priceTimestamp: newestPriceTimestamp,
    categories,
    accounts
  };
};

/**
 * Build a cumulative investment timeline for charting.
 * Returns one data point per transaction date, showing running net inflow and cost basis.
 */
export const buildInvestmentTimeline = (
  baseCurrency: BaseCurrency,
  accountId?: string
): { date: string; netInflow: number; costBasis: number }[] => {
  let transactions = [...db.getTransactions()].sort((a, b) =>
    a.executedAt.localeCompare(b.executedAt)
  );
  if (accountId) {
    transactions = transactions.filter((t) => t.accountId === accountId);
  }

  let netInflow = 0;
  let costBasis = 0;
  const points: { date: string; netInflow: number; costBasis: number }[] = [];

  for (const txn of transactions) {
    const amount = convertAmount(txn.quantity * txn.price, txn.currency, baseCurrency);
    const fee = convertAmount(txn.fee, txn.currency, baseCurrency);

    switch (txn.type) {
      case "deposit":
      case "transfer_in":
        netInflow += amount;
        break;
      case "withdrawal":
      case "transfer_out":
        netInflow -= amount;
        break;
      case "buy":
        costBasis += amount + fee;
        break;
      case "sell":
        costBasis -= amount - fee;
        break;
    }

    points.push({
      date: txn.executedAt.substring(0, 10),
      netInflow: round(netInflow, 2),
      costBasis: round(costBasis, 2)
    });
  }

  return points;
};

export const getRecentTransactions = () =>
  [...db.getTransactions()].sort((a, b) => b.executedAt.localeCompare(a.executedAt));
