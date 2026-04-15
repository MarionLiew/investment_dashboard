import { NextRequest, NextResponse } from "next/server";
import { searchAssets } from "@/lib/services/assets";

export async function GET(request: NextRequest) {
  const keyword = request.nextUrl.searchParams.get("keyword") ?? "";
  return NextResponse.json({
    items: searchAssets(keyword)
  });
}
