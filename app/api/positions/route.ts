import { NextRequest, NextResponse } from "next/server";
import { buildPositions } from "@/lib/services/portfolio";
import { BaseCurrency } from "@/lib/types";

export async function GET(request: NextRequest) {
  const value = request.nextUrl.searchParams.get("baseCurrency");
  const baseCurrency: BaseCurrency = value === "USD" ? "USD" : "CNY";
  return NextResponse.json({
    items: buildPositions(baseCurrency)
  });
}
