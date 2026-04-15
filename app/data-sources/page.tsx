import { DataSourcesPanel } from "@/components/data-sources-panel";

export default function DataSourcesPage() {
  return (
    <div className="page-grid">
      <section className="hero-card compact">
        <div className="hero-copy">
          <p className="eyebrow">Connectors</p>
          <h2>数据源配置与同步日志</h2>
          <p>OKX 已预置连接器接口，当前用模拟同步数据展示接入链路。</p>
        </div>
      </section>
      <DataSourcesPanel />
      <section className="panel">
        <div className="panel-heading">
          <h3>同步接口示例</h3>
        </div>
        <pre className="code-block">{`POST /api/connectors/okx/sync
{
  "accountId": "acct_okx"
}`}</pre>
      </section>
    </div>
  );
}
