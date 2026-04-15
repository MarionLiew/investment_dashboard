# 全品类投资看板

个人多资产类别投资统计平台，覆盖 A 股、美股衍生品、大宗商品和加密货币，支持 OKX 实盘数据同步。

---

## 技术架构

```
┌─────────────────────────────────────────────────────┐
│                   浏览器 / 用户                      │
└────────────┬────────────────────────┬───────────────┘
             │                        │
    ┌────────▼────────┐      ┌────────▼────────┐
    │  React / Vite   │      │   Python Dash   │
    │  port 5173      │      │   port 8050     │
    │  Recharts 图表  │      │  Plotly 图表    │
    └────────┬────────┘      └────────┬────────┘
             │                        │
    ┌────────▼────────┐      ┌────────▼────────┐
    │  Hono API 服务  │      │  services/ 层   │
    │  port 3001      │      │  Python 直调    │
    │  store.json 读写│      │  store.json 读写│
    └────────┬────────┘      └─────────────────┘
             │
    ┌────────▼────────┐
    │  data/store.json│  ← 统一数据层（JSON 文件）
    └─────────────────┘
             │
    ┌────────▼────────┐
    │   OKX REST v5   │  ← 外部 API
    │  open.er-api.com│
    └─────────────────┘
```

**双前端并行：**
- **React/Vite（主）**：交互式看板，客户端计算持仓/盈亏
- **Python Dash（辅）**：数据分析视角，服务端计算，Plotly 图表

---

## 快速启动

### 前置要求
- Node.js ≥ 18（见 `.nvmrc`）
- Python ≥ 3.9

### React + Hono 前端（port 5173 + 3001）

```bash
npm install
npm run dev
```

打开 http://localhost:5173

### Python Dash 前端（port 8050）

```bash
pip install -r requirements.txt
python app.py
```

打开 http://localhost:8050

### OKX 实盘同步配置

在项目根目录创建 `.env.local`：

```
OKX_API_KEY=your_api_key
OKX_SECRET_KEY=your_secret_key
OKX_PASSPHRASE=your_passphrase
```

OKX API 权限要求：**读取 + 交易记录 + 资金账户**（需勾选 Funding 权限，否则入金记录会 403）

---

## 目录结构

```
investment_dashboard/
├── app.py                  # Python Dash 入口（port 8050）
├── server/index.ts         # Hono API 服务入口（port 3001）
├── src/
│   ├── main.tsx            # React 入口
│   └── App.tsx             # React 路由
├── components/             # React UI 组件（TSX）
│   ├── dashboard.tsx       # 主看板
│   ├── portfolio-charts.tsx# Recharts 图表
│   ├── market-clock.tsx    # 实时市场时钟
│   ├── positions-table.tsx # 持仓表格
│   └── transactions-table.tsx
├── lib/
│   ├── types.ts            # TypeScript 类型定义
│   ├── db.ts               # 客户端内存 store + Hono 同步
│   ├── utils.ts            # 格式化工具（fmtCST 等）
│   └── services/
│       ├── portfolio.ts    # 持仓/盈亏计算（TS 版）
│       ├── fx.ts           # 汇率转换
│       └── pricing.ts      # 价格查询
├── services/               # Python 计算层
│   ├── db.py               # JSON 文件读写（线程安全）
│   ├── portfolio.py        # 持仓/盈亏计算（Python 版）
│   ├── okx.py              # OKX API 同步
│   └── fx.py               # 汇率查询
├── dash_pages/             # Python Dash 页面
│   ├── home.py             # 综合看板（/）
│   ├── positions.py        # 持仓列表（/positions）
│   ├── transactions.py     # 交易流水（/transactions）
│   ├── accounts.py         # 账户管理（/accounts）
│   └── data_sources.py     # 数据源/同步（/data-sources）
├── data/
│   └── store.json          # 统一数据文件（gitignored）
└── assets/style.css        # Dash 全局样式
```

---

## 关键外部 API

### OKX REST API v5

认证方式：HMAC-SHA256 签名
```
签名 = Base64(HMAC-SHA256(timestamp + "GET" + path, secret_key))
Headers: OK-ACCESS-KEY / OK-ACCESS-SIGN / OK-ACCESS-TIMESTAMP / OK-ACCESS-PASSPHRASE
```

| 端点 | 用途 | 注意事项 |
|------|------|----------|
| `GET /api/v5/account/balance` | 账户总权益 + 现货余额快照 | `details` 字段包含各 ccy 余额，是获取现货持仓的唯一方式 |
| `GET /api/v5/account/positions` | 当前开仓衍生品持仓 | 只返回衍生品（SWAP/FUTURES/MARGIN），**不包含现货**；`instType=SPOT` 会返回 error 51000 |
| `GET /api/v5/account/positions-history` | 历史持仓记录 | 用于补全 >90 天前开仓的记录，配合 fills-history 拼接完整持仓 |
| `GET /api/v5/trade/fills-history` | 成交记录 | 仅返回近 90 天；更早的仓位用 positions-history 合成开仓记录 |
| `GET /api/v5/account/bills-archive` | 账单流水 | type=2/subType=5 为已实现盈亏；type=8 为资金费用；用于 TWR 计算 |
| `GET /api/v5/asset/deposit-history` | 入金记录 | 需要 **Funding** 权限，缺失时返回 403 |
| `GET /api/v5/public/instruments` | 合约规格（ctVal 面值）| SWAP/FUTURES 成交量是"张数"，须乘以 ctVal 换算为实际资产数量 |
| `GET /api/v5/market/ticker` | 实时行情 | 公开接口无需认证；stablecoin（USDT/USDC）固定返回 1.0 |

### 汇率 API

```
GET https://open.er-api.com/v6/latest/USD
```

免费公开接口，无需 API Key，结果缓存到 `fxRates` 表，同步时刷新。

---

## 核心数据模型（store.json）

```typescript
{
  accounts:         Account[]          // 账户（manual / okx）
  assets:           Asset[]            // 资产定义（symbol + market 唯一）
  transactions:     Transaction[]      // 全部交易流水（buy/sell/deposit/...）
  prices:           PriceSnapshot[]    // 最新价格快照
  fxRates:          FxRateSnapshot[]   // 汇率（USD/CNY 等）
  connectorConfigs: ConnectorConfig[]  // OKX 连接器配置 + 同步快照
  syncLogs:         SyncLog[]          // 同步日志
}

// ConnectorConfig 同步后额外字段：
{
  openInstIds:          string[]           // 有持仓的衍生品 instId（权威真值）
  spotBalances:         {[ccy]: number}    // 现货余额快照（权威真值）
  dailyPortfolioValues: DailyPortfolioValue[] // 日收益率历史
  realizedTwr:          number | null      // 时间加权收益率
  accountEquityUsd:     number             // OKX 账户总权益（USD）
}
```

---

## 开发过程中的典型错误

记录本项目开发中踩过的坑，避免重复。

### 1. Dash 组件是 falsy（`dcc.Graph or fallback` 永远走 fallback）

**现象：** 资产配置图、盈亏分解图始终显示"暂无数据"，即使数据正常。

**根因：** Dash 组件重写了 `__bool__`，`bool(dcc.Graph(...))` 返回 `False`。
```python
# 错误写法
chart = _build_chart(data)
return chart or html.P("无数据")  # chart 永远是 falsy！

# 正确写法
chart = _build_chart(data)
return chart if chart is not None else html.P("无数据")
```

---

### 2. UTC 时间戳直接截断当北京时间显示（差 8 小时）

**现象：** 交易流水、同步日志时间比实际北京时间早 8 小时。

**根因：** `executedAt` 存的是带 `+00:00` 的 UTC ISO 字符串，直接截取前 16 位当成北京时间显示。
```python
# 错误
txn["executedAt"][:16].replace("T", " ")

# 正确
from datetime import datetime, timezone, timedelta
dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
cst = dt.astimezone(timezone(timedelta(hours=8)))
return cst.strftime("%Y-%m-%d %H:%M")
```

---

### 3. 链式 TWR 在子账户互转时出现 -100%

**现象：** 时间加权收益率显示 -100% 或 NaN。

**根因：** OKX 子账户之间互转（资金划入/划出）导致某个计算区间的净投入为 0，链式 TWR 分母为 0，出现 -∞ 或 −100%。

**修复：** 改用累计方式：`realized_twr = cum_realized_pnl / total_net_inflow`，绕过区间链式计算。

---

### 4. 裸 `except: pass` 吞掉 NameError，TWR 始终为 None

**现象：** 同步后 `twr_rate` 始终为 None，无报错。

**根因：** `build_portfolio_summary()` 中引用了未定义的变量 `configs`，抛出 `NameError`，被 `except Exception: pass` 静默吞掉。

**修复：** 去掉裸 except，至少 `except Exception as e: logger.warning(e)`。

---

### 5. 衍生品过滤器误杀现货持仓

**现象：** XAUT（现货黄金）余额同步后归零。

**根因：** `openInstIds` 快照来自 `/account/positions`，只包含衍生品。将"不在快照中即归零"的逻辑错误地套用到 XAUT 现货上。

**修复：** 过滤器前先判断 `is_okx_derivative = asset.get("market") in _DERIVATIVE_MARKETS`，现货不走衍生品过滤逻辑。

---

### 6. OKX 无现货持仓接口（`instType=SPOT` 返回 error 51000）

**现象：** 调用 `/account/positions?instType=SPOT` 返回错误码 51000。

**根因：** OKX 的 `/account/positions` 接口只支持衍生品，不支持现货。

**正确做法：** 用 `/account/balance` 的 `details` 数组获取各币种余额作为现货持仓，存入 `spotBalances` 快照。

---

### 7. 幽灵仓位（浮点残留导致持仓未归零）

**现象：** `XAUT.MARGIN` 显示持仓 0.000047，实际 OKX 已无持仓。

**根因：** 买入/卖出流水中的浮点运算累积误差导致净持仓非零。

**修复：** 以 OKX `openInstIds` 快照为权威真值，凡不在快照中的合约一律强制归零。

---

### 8. OKX fills-history 只有 90 天，更早的开仓记录缺失

**现象：** 90 天前建仓的合约，平仓记录被识别为"做空建仓"，持仓方向反转。

**根因：** `/trade/fills-history` 最多返回近 90 天的成交，更早的建仓找不到对应开仓记录，平仓 SELL 被误当成建仓 SHORT。

**修复：** 用 `/account/positions-history` 获取历史持仓的 `openAvgPx`（均价）合成缺失的开仓流水。

---

### 9. 合约张数未乘以 ctVal，持仓数量错误数百倍

**现象：** BTC.SWAP 显示持仓 12 BTC，实际只有 0.12 BTC。

**根因：** OKX SWAP/FUTURES 成交量单位是"张"（contract），需乘以 `ctVal`（合约面值）。BTC-USDT-SWAP 的 `ctVal = 0.01`，即 1 张 = 0.01 BTC。

**修复：** 从 `/public/instruments` 获取每个合约的 `ctVal` 并缓存，计算时乘以换算。

---

### 10. 双计算层（Python + TypeScript）独立维护，容易不同步

**现象：** Python Dash 看板和 React 看板显示的数字不一致。

**根因：** `services/portfolio.py` 和 `lib/services/portfolio.ts` 分别独立实现了相同的持仓/盈亏计算逻辑，修改一处另一处不同步。

**建议方向：** 统一计算层（Python 暴露 API，React 通过 Hono 消费），或两侧共用同一套测试用例验证一致性。

---

## 安全注意事项

- `data/store.json` 包含 OKX API Key，已加入 `.gitignore`，**严禁提交到 git**
- `.env.local` 包含 API 凭证，已加入 `.gitignore`
- 生产环境建议将 API Key 迁移到 OS Keychain 或加密存储，不要明文存 JSON
- Hono 开发服务器（port 3001）无鉴权，仅供本地使用

---

## 待改进项（Roadmap）

### 投资看板功能
- [ ] 组合净值曲线（历史每日总资产绝对值）
- [ ] 最大回撤（Max Drawdown）
- [ ] 基准对比（CSI300 / S&P500 / BTC）
- [ ] 年化收益率
- [ ] 交易费用单独统计
- [ ] 夏普比率（Sharpe Ratio）
- [ ] 杠杆暴露比例
- [ ] 分红/利息收入拆解

### 工程改进
- [ ] 添加单元测试（pytest + vitest）
- [ ] 用 SQLite 替换 JSON 文件数据库
- [ ] 消除双计算层，统一到服务端
- [ ] 用 `logging` 模块替换 `except: pass`
- [ ] 添加 `ruff`（Python）和 `eslint`（TypeScript）
- [ ] 统一启动脚本（`make dev` 同时启动三个服务）
