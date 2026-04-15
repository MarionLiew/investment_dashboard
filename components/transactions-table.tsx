import { useState } from "react";
import { getRecentTransactions } from "@/lib/services/portfolio";
import { currencyFormatter, numberFormatter, fmtCST } from "@/lib/utils";
import { db } from "@/lib/db";

const TYPE_LABELS: Record<string, string> = {
  buy: "买入",
  sell: "卖出",
  dividend: "分红",
  interest: "利息",
  fee: "手续费",
  transfer_in: "转入",
  transfer_out: "转出",
  deposit: "入金",
  withdrawal: "出金"
};

export function TransactionsTable() {
  const [version, setVersion] = useState(0);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const assets = db.getAssets();
  const accounts = db.getAccounts();
  const transactions = getRecentTransactions();

  function handleDelete(id: string) {
    db.deleteTransaction(id);
    setConfirmDelete(null);
    setVersion((v) => v + 1);
  }

  return (
    <div className="panel" key={version}>
      <div className="panel-heading">
        <h3>统一交易流水</h3>
        <span>手动录入与 API 同步共用同一套核算口径</span>
      </div>
      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>账户</th>
              <th>标的</th>
              <th>类型</th>
              <th>数量</th>
              <th>价格</th>
              <th>费用</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((transaction) => {
              const asset = assets.find((item) => item.id === transaction.assetId);
              const account = accounts.find((item) => item.id === transaction.accountId);
              const formatter = currencyFormatter(transaction.currency);
              const isConfirming = confirmDelete === transaction.id;

              return (
                <tr key={transaction.id}>
                  <td>{fmtCST(transaction.executedAt)}</td>
                  <td>{account?.name ?? transaction.accountId}</td>
                  <td>{asset?.symbol ?? transaction.assetId}</td>
                  <td>{TYPE_LABELS[transaction.type] ?? transaction.type}</td>
                  <td>{numberFormatter.format(transaction.quantity)}</td>
                  <td>{formatter.format(transaction.price)}</td>
                  <td>{formatter.format(transaction.fee)}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {!isConfirming ? (
                      <button
                        className="chip"
                        style={{ fontSize: 11, color: "var(--negative)", padding: "2px 8px" }}
                        onClick={() => setConfirmDelete(transaction.id)}
                      >
                        删除
                      </button>
                    ) : (
                      <span style={{ display: "flex", gap: 4 }}>
                        <button
                          className="chip"
                          style={{ fontSize: 11, color: "var(--negative)", fontWeight: 600, padding: "2px 8px" }}
                          onClick={() => handleDelete(transaction.id)}
                        >
                          确认
                        </button>
                        <button
                          className="chip"
                          style={{ fontSize: 11, padding: "2px 8px" }}
                          onClick={() => setConfirmDelete(null)}
                        >
                          取消
                        </button>
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
