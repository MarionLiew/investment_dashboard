import { buildPositions } from "@/lib/services/portfolio";
import type { BaseCurrency } from "@/lib/types";
import { currencyFormatter, numberFormatter, percentFormatter } from "@/lib/utils";

export function PositionsTable({
  baseCurrency,
  accountId,
  assetType
}: {
  baseCurrency: BaseCurrency;
  accountId?: string;
  assetType?: string;
}) {
  const formatter = currencyFormatter(baseCurrency);
  const allPositions = buildPositions(baseCurrency);

  const positions = allPositions.filter((position) => {
    if (position.quantity <= 0) return false;
    if (accountId && position.accountId !== accountId) return false;
    if (assetType && position.assetType !== assetType) return false;
    return true;
  });

  const closedPositions = allPositions.filter((p) => p.quantity <= 0 && p.soldQuantity > 0);

  return (
    <div className="page-grid">
      <div className="panel">
        <div className="panel-heading">
          <h3>当前持仓</h3>
          <span>{positions.length} 条记录</span>
        </div>
        {positions.length === 0 ? (
          <p style={{ color: "var(--ink-tertiary)", fontSize: 13 }}>暂无符合条件的持仓</p>
        ) : (
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>标的</th>
                  <th>账户</th>
                  <th>数量</th>
                  <th>成本</th>
                  <th>现价</th>
                  <th>市值</th>
                  <th>浮盈亏</th>
                  <th>已实现</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((position) => (
                  <tr key={`${position.accountId}-${position.assetId}`}>
                    <td>
                      <strong>{position.symbol}</strong>
                      <p>{position.name}</p>
                    </td>
                    <td>{position.accountName}</td>
                    <td>{numberFormatter.format(position.quantity)}</td>
                    <td>{formatter.format(position.costBasisBase)}</td>
                    <td>
                      {position.latestPrice
                        ? `${position.latestPriceCurrency} ${numberFormatter.format(position.latestPrice)}`
                        : "暂无行情"}
                    </td>
                    <td>
                      {position.marketValueBase === null
                        ? "暂无行情"
                        : formatter.format(position.marketValueBase)}
                    </td>
                    <td>
                      {position.unrealizedPnlBase === null ? (
                        "暂无行情"
                      ) : (
                        <span className={position.unrealizedPnlBase >= 0 ? "positive" : "negative"}>
                          {formatter.format(position.unrealizedPnlBase)}
                          {position.unrealizedPnlRate !== null && (
                            <> / {percentFormatter.format(position.unrealizedPnlRate)}</>
                          )}
                        </span>
                      )}
                    </td>
                    <td>
                      {position.soldQuantity > 0 ? (
                        <span className={position.realizedPnlBase >= 0 ? "positive" : "negative"}>
                          {formatter.format(position.realizedPnlBase)}
                        </span>
                      ) : (
                        <span style={{ color: "var(--ink-tertiary)" }}>—</span>
                      )}
                    </td>
                    <td>{position.stalePrice ? "缓存行情" : "正常"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {closedPositions.length > 0 && !accountId && !assetType && (
        <div className="panel">
          <div className="panel-heading">
            <h3>已清仓</h3>
            <span>{closedPositions.length} 条记录</span>
          </div>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>标的</th>
                  <th>账户</th>
                  <th>已卖数量</th>
                  <th>已实现盈亏</th>
                </tr>
              </thead>
              <tbody>
                {closedPositions.map((position) => (
                  <tr key={`closed-${position.accountId}-${position.assetId}`}>
                    <td>
                      <strong>{position.symbol}</strong>
                      <p>{position.name}</p>
                    </td>
                    <td>{position.accountName}</td>
                    <td>{numberFormatter.format(position.soldQuantity)}</td>
                    <td>
                      <span className={position.realizedPnlBase >= 0 ? "positive" : "negative"}>
                        {formatter.format(position.realizedPnlBase)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
