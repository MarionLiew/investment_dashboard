import { Hono } from "hono";
import { serve } from "@hono/node-server";
import { cors } from "hono/cors";
import crypto from "crypto";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_FILE = path.resolve(__dirname, "../data/store.json");
const OKX_BASE = "https://www.okx.com";

const app = new Hono();

app.use("*", cors({ origin: ["http://localhost:5173", "http://127.0.0.1:5173"] }));

// ── Store endpoints ──────────────────────────────────────────

app.get("/api/store", (c) => {
  if (!fs.existsSync(DATA_FILE)) return c.json(null);
  try {
    return c.json(JSON.parse(fs.readFileSync(DATA_FILE, "utf-8")));
  } catch {
    return c.json(null);
  }
});

app.put("/api/store", async (c) => {
  const body = await c.req.json();
  fs.mkdirSync(path.dirname(DATA_FILE), { recursive: true });
  fs.writeFileSync(DATA_FILE, JSON.stringify(body, null, 2));
  return c.json({ ok: true });
});

// ── OKX proxy ────────────────────────────────────────────────

function okxSign(
  method: string,
  path: string,
  creds: { apiKey: string; secretKey: string; passphrase: string },
  body = ""
) {
  const timestamp = new Date().toISOString();
  const message = timestamp + method + path + body;
  const sign = crypto
    .createHmac("sha256", creds.secretKey)
    .update(message)
    .digest("base64");
  return {
    "OK-ACCESS-KEY": creds.apiKey,
    "OK-ACCESS-SIGN": sign,
    "OK-ACCESS-TIMESTAMP": timestamp,
    "OK-ACCESS-PASSPHRASE": creds.passphrase,
    "Content-Type": "application/json"
  };
}

// Generic GET proxy for OKX — /api/okx/* maps to OKX /api/v5/*
// Credentials can come from request headers (UI-configured) or env vars (fallback)
app.get("/api/okx/*", async (c) => {
  const url = new URL(c.req.url);
  const okxPath = url.pathname.replace(/^\/api\/okx/, "") + (url.search ?? "");
  const creds = {
    apiKey: c.req.header("X-OKX-API-KEY") || process.env.OKX_API_KEY || "",
    secretKey: c.req.header("X-OKX-SECRET-KEY") || process.env.OKX_SECRET_KEY || "",
    passphrase: c.req.header("X-OKX-PASSPHRASE") || process.env.OKX_PASSPHRASE || ""
  };
  try {
    const res = await fetch(OKX_BASE + okxPath, {
      headers: okxSign("GET", okxPath, creds)
    });
    const data = await res.json();
    return c.json(data);
  } catch (err) {
    return c.json({ error: String(err) }, 502);
  }
});

serve({ fetch: app.fetch, port: 3001 }, () => {
  console.log("  Store server: http://localhost:3001");
  if (process.env.OKX_API_KEY) {
    console.log("  OKX API: configured ✓");
  } else {
    console.log("  OKX API: not configured (missing .env.local)");
  }
});
