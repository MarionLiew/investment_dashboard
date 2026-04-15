import { NextRequest, NextResponse } from "next/server";
import { buildAccountPerformance } from "@/lib/services/portfolio";
import { BaseCurrency } from "@/lib/types";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const resolved = await params;
  const value = request.nextUrl.searchParams.get("baseCurrency");
  const baseCurrency: BaseCurrency = value === "USD" ? "USD" : "CNY";
  const account = buildAccountPerformance(baseCurrency).find(
    (item) => item.accountId === resolved.id
  );

  if (!account) {
    return NextResponse.json({ error: "account 不存在" }, { status: 404 });
  }

  return NextResponse.json(account);
}
