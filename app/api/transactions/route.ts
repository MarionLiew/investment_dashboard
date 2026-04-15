import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { ensureAsset } from "@/lib/services/assets";
import { makeId } from "@/lib/utils";
import { Transaction, TransactionType } from "@/lib/types";

type TransactionRequest = {
  accountId?: string;
  assetId?: string;
  asset?: {
    assetType: "stock" | "fund" | "crypto" | "cash";
    symbol: string;
    name: string;
    market: string;
    currency: string;
  };
  type?: TransactionType;
  quantity?: number;
  price?: number;
  fee?: number;
  currency?: string;
  executedAt?: string;
  note?: string;
};

export async function POST(request: NextRequest) {
  const body = (await request.json()) as TransactionRequest;

  if (
    !body.accountId ||
    !body.type ||
    body.quantity === undefined ||
    body.price === undefined ||
    !body.currency ||
    !body.executedAt
  ) {
    return NextResponse.json({ error: "交易字段不完整" }, { status: 400 });
  }

  const account = db.getAccounts().find((item) => item.id === body.accountId);
  if (!account) {
    return NextResponse.json({ error: "account 不存在" }, { status: 404 });
  }

  const asset =
    (body.assetId && db.getAssets().find((item) => item.id === body.assetId)) ||
    (body.asset ? ensureAsset(body.asset) : null);

  if (!asset) {
    return NextResponse.json({ error: "asset 不存在，请提供 assetId 或 asset" }, { status: 400 });
  }

  const transaction: Transaction = {
    id: makeId("txn"),
    accountId: body.accountId,
    assetId: asset.id,
    type: body.type,
    quantity: body.quantity,
    price: body.price,
    fee: body.fee ?? 0,
    currency: body.currency,
    executedAt: body.executedAt,
    note: body.note
  };

  db.addTransaction(transaction);
  return NextResponse.json(transaction, { status: 201 });
}
