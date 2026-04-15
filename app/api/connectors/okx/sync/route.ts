import { NextRequest, NextResponse } from "next/server";
import { okxConnector } from "@/lib/connectors/okx";
import { db } from "@/lib/db";
import { makeId } from "@/lib/utils";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as { accountId?: string };

  if (!body.accountId) {
    return NextResponse.json({ error: "accountId 为必填字段" }, { status: 400 });
  }

  const account = db.getAccounts().find((item) => item.id === body.accountId);
  if (!account) {
    return NextResponse.json({ error: "account 不存在" }, { status: 404 });
  }

  try {
    const result = await okxConnector.syncAccount(body.accountId);
    const config = db.getConnectorConfigs().find((item) => item.accountId === body.accountId);
    if (config) {
      db.upsertConnectorConfig({
        ...config,
        lastSyncedAt: new Date().toISOString(),
        status: "configured",
        lastError: undefined
      });
    }
    db.addSyncLog({
      id: makeId("sync"),
      accountId: body.accountId,
      connector: "okx",
      status: "success",
      message: result.message,
      createdAt: new Date().toISOString()
    });

    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "OKX 同步失败";
    db.addSyncLog({
      id: makeId("sync"),
      accountId: body.accountId,
      connector: "okx",
      status: "error",
      message,
      createdAt: new Date().toISOString()
    });
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
