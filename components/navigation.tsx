import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/", label: "总览" },
  { to: "/positions", label: "持仓" },
  { to: "/accounts", label: "账户" },
  { to: "/transactions", label: "流水" },
  { to: "/data-sources", label: "数据源" }
];

export function Navigation() {
  return (
    <nav className="nav-shell">
      <div className="nav-brand">
        <div className="nav-brand-icon">投</div>
        <div className="nav-brand-text">
          <span className="nav-brand-title">全品类投资统计</span>
          <span className="nav-brand-sub">Investment Console</span>
        </div>
      </div>
      <div className="nav-links">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
          >
            {item.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
