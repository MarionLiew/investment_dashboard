import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { makeId } from "@/lib/utils";
import { Account, BaseCurrency } from "@/lib/types";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as Partial<Account>;

  if (!body.name || !body.sourceType) {
    return NextResponse.json(
      { error: "name 和 sourceType 为必填字段" },
      { status: 400 }
    );
  }

  const account: Account = {
    id: makeId("acct"),
    name: body.name,
    sourceType: body.sourceType,
    baseCurrency:
      body.baseCurrency === "USD" || body.baseCurrency === "CNY"
        ? (body.baseCurrency as BaseCurrency)
        : "CNY",
    status: "active",
    updatedAt: new Date().toISOString()
  };

  db.addAccount(account);
  return NextResponse.json(account, { status: 201 });
}
