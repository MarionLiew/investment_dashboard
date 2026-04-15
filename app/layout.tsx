import type { Metadata } from "next";
import "@/app/globals.css";
import { Navigation } from "@/components/navigation";

export const metadata: Metadata = {
  title: "全品类投资统计",
  description: "股票、基金、加密货币综合收益仪表盘"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="app-shell">
          <Navigation />
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
