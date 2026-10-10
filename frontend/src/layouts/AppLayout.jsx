import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  FaTachometerAlt, FaCog, FaSearch, FaMoon, FaSun,
  FaSignOutAlt, FaBars, FaChevronLeft, FaMapMarkerAlt, FaTicketAlt, FaTimes, FaBell
} from "react-icons/fa";
import { useStore } from "../store";
import Logo from "../components/Logo";

const NAV = [
  { path: "/dashboard", label: "Overview", kicker: "Ferguson Network Operations", icon: FaTachometerAlt },
  { path: "/alerts", label: "Alerts Console", kicker: "Alert Investigation", icon: FaBell },
  { path: "/sites", label: "Sites", kicker: "Site Explorer", icon: FaMapMarkerAlt },
  { path: "/tickets", label: "Tickets", kicker: "Ticket Explorer", icon: FaTicketAlt },
  { path: "/admin", label: "Admin", kicker: "System Administration", icon: FaCog, adminOnly: true },
];

function applyTheme(dark) {
  const root = document.documentElement;
  root.classList.toggle("dark", dark);
  try {
    localStorage.setItem("naap.theme", dark ? "dark" : "light");
  } catch {
    /* ignore private-mode storage errors */
  }
}

export default function AppLayout() {
  const { me, logout, toast, setMe, refreshMe } = useStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains("dark"));
  const [topSearch, setTopSearch] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef(null);

  const toggleTheme = () => {
    const next = !isDark;
    applyTheme(next);
    setIsDark(next);
  };

  useEffect(() => {
    const handleUnauthorized = () => {
      setMe(null);
      navigate("/login", { replace: true });
    };
    window.addEventListener("naap:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("naap:unauthorized", handleUnauthorized);
  }, [navigate, setMe]);

  // Revalidate the stored session against the backend once on mount.
  useEffect(() => { refreshMe(); }, [refreshMe]);

  useEffect(() => {
    const onClick = (event) => {
      if (profileRef.current && !profileRef.current.contains(event.target)) setProfileOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const items = me.role === "ADMIN" ? NAV : NAV.filter((item) => !item.adminOnly);
  const isAlertDetail = /^\/alerts\/event\/[^/]+/.test(location.pathname);
  const currentPage = isAlertDetail
    ? { label: "Alert Details", kicker: "Alert Investigation" }
    : NAV.find((item) => item.path === location.pathname);

  // The top-bar search jumps to the Alerts Console pre-filtered, mirroring the
  // filters there: an all-numeric query is treated as an event ID, an IP-like
  // query as an IP address prefix, and anything else as free text.
  const handleTopSearch = (event) => {
    event.preventDefault();
    const query = topSearch.trim();
    if (!query) return;
    const nextParams = new URLSearchParams();
  // Detect a partial IPv4 while it is being typed — every complete-looking
  // dotted group so far counts (e.g. "10.43", "10.43.1", "10.43.1.").
  const looksLikeIp = /^(\d{1,3}\.){0,3}\d{0,3}\.?$/.test(query) && query.includes(".");
  if (/^\d+$/.test(query)) nextParams.set("event_id", query);
    else if (looksLikeIp) nextParams.set("ip_address", query.replace(/\.$/, ""));
    else nextParams.set("search", query);
    navigate(`/alerts?${nextParams.toString()}`);
  };

  const clearTopSearch = () => setTopSearch("");

  return (
    <div className="flex h-screen overflow-hidden bg-canvas text-ink dark:bg-[#061724] dark:text-white">
      {/* Rail */}
      <aside
        className={`z-30 flex flex-col bg-brand text-white shadow-xl transition-[width] duration-300 dark:bg-[#00283f] ${
          collapsed ? "w-[76px]" : "w-60"
        }`}
      >
        <div className="flex flex-col items-center gap-2.5 border-b border-white/10 px-4 py-4">
          {collapsed ? (
            <Logo white className="mx-auto h-7 w-auto" />
          ) : (
            <>
              <Logo white className="h-7 w-auto" />
              
              <div className="flex mt-2 flex-col mx-auto w-full border-t leading-tight">
                <span className="text-[20px] mt-3 mx-auto  font-extrabold tracking-wide">NOCTURNE</span>
                <span className="text-[11px] mx-auto mt-1 text-white/60">NOC Portal</span>
              </div>
            </>
          )}
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-2.5 py-4">
          {!collapsed && (
            <div className="px-3 pb-1 text-[11px] font-semibold tracking-wider text-white/45 uppercase">
              Operations
            </div>
          )}
          {items.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-[14px] font-medium transition-colors ${
                  isActive
                    ? "bg-white text-brand shadow-sm dark:bg-[#0f3a58] dark:text-white"
                    : "text-white/80 hover:bg-white/10 hover:text-white"
                } ${collapsed ? "justify-center" : ""}`
              }
            >
              <Icon className="text-[17px] flex-none" />
              {!collapsed && <span className="truncate">{label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-white/10 p-2.5">
          <button
            onClick={() => setCollapsed((value) => !value)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-white/70 transition-colors hover:bg-white/10 hover:text-white"
          >
            {collapsed ? <FaBars /> : <><FaChevronLeft /><span className="text-[13px]">Collapse</span></>}
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="z-10 flex items-center gap-3 border-b border-line/70 bg-canvas/80 px-5 py-3 backdrop-blur-md dark:border-white/10 dark:bg-[#061724]/80">
          <div className="min-w-0 flex-1">
            {currentPage && (
              <>
                <div className="text-[11.5px] text-ink-3">{currentPage.kicker}</div>
                <h1 className="truncate text-[18px] font-bold tracking-tight text-ink dark:text-white">
                  {currentPage.label}
                </h1>
              </>
            )}
          </div>

          <form onSubmit={handleTopSearch} className="relative hidden md:block">
            <FaSearch className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-3" />
            <input
              type="text"
              placeholder="Search alerts, device, IP or event ID…"
              aria-label="Search alerts"
              value={topSearch}
              onChange={(event) => setTopSearch(event.target.value)}
              className="w-72 rounded-lg border border-line bg-paper py-2 pr-9 pl-9 text-[13.5px] text-ink shadow-card outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-white/10 dark:bg-white/5 dark:text-white"
            />
            {topSearch && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={clearTopSearch}
                className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 text-ink-3 transition-colors hover:text-ink"
              >
                <FaTimes className="text-[13px]" />
              </button>
            )}
          </form>

          <button
            onClick={toggleTheme}
            aria-label="Toggle day / night theme"
            className="grid h-10 w-10 place-items-center rounded-lg border border-line bg-paper text-ink-2 transition-colors hover:border-brand hover:text-brand dark:border-white/10 dark:bg-white/5"
          >
            {isDark ? <FaSun className="text-[17px]" /> : <FaMoon className="text-[17px]" />}
          </button>

          <div className="relative" ref={profileRef}>
            <button
              onClick={() => setProfileOpen((value) => !value)}
              className="grid h-10 w-10 place-items-center rounded-full bg-brand font-bold text-white ring-2 ring-transparent transition hover:ring-brand/30"
              aria-label="Account menu"
            >
              {me.name.charAt(0).toUpperCase()}
            </button>

            {profileOpen && (
              <div className="animate-fade absolute right-0 mt-2 w-56 overflow-hidden rounded-xl border border-line bg-paper shadow-pop dark:border-white/10 dark:bg-[#0c2435]">
                <div className="border-b border-line px-4 py-3 dark:border-white/10">
                  <p className="truncate text-[14px] font-semibold text-ink dark:text-white">{me.name}</p>
                  <p className="truncate text-[12px] text-ink-3">
                    {me.username} · {me.role === "ADMIN" ? "Administrator" : "Analyst"}
                  </p>
                </div>
                <button
                  onClick={() => {
                    setProfileOpen(false);
                    logout();
                    navigate("/login");
                  }}
                  className="flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-[13.5px] font-medium text-p1 hover:bg-p1-bg"
                >
                  <FaSignOutAlt /> Sign out
                </button>
              </div>
            )}
          </div>
        </header>

        <main className="flex-1 overflow-y-auto px-5 py-6">
          <div className="mx-auto max-w-[1600px]">
            <Outlet />
          </div>
        </main>
      </div>

      {toast && (
        <div className="animate-rise fixed right-5 bottom-5 z-50 flex items-center gap-3 overflow-hidden rounded-xl border border-line bg-paper py-3 pr-4 pl-0 text-[14px] text-ink shadow-pop dark:border-white/10 dark:bg-[#0c2435] dark:text-white">
          <span className="h-full w-1 self-stretch bg-brand" />
          <span className="pr-1">{toast}</span>
        </div>
      )}
    </div>
  );
}
