import { Bell, ChevronDown, LogOut } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "@/api/client";
import { useMarkAllRead, useNotifications } from "@/api/queries";
import { icon } from "@/components/ui/icon";
import { Dropdown } from "@/components/ui/Dropdown";
import { RelativeTime } from "@/components/ui/Misc";
import { cn } from "@/lib/cn";
import { useAuth } from "@/stores/auth";
import { Logo } from "./Logo";
import { homeFor, NAV } from "./nav";

export function Sidebar() {
  const user = useAuth((s) => s.user)!;
  return (
    <aside className="fixed inset-y-0 left-0 hidden w-[240px] flex-col border-r border-border bg-surface md:flex">
      <div className="flex h-12 items-center border-b border-border px-4">
        <Logo to={homeFor(user.role)} />
      </div>
      <nav aria-label="Main" className="flex-1 py-2">
        {NAV[user.role].map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cn(
                "flex h-9 items-center gap-2.5 border-l-2 px-4 text-sm",
                isActive
                  ? "border-accent bg-bg font-medium text-accent hover:text-accent"
                  : "border-transparent text-ink-secondary hover:bg-bg hover:text-ink",
              )
            }
          >
            <item.icon {...icon} />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-border px-4 py-3 text-xs text-ink-secondary">
        Signed in as <span className="font-medium text-ink">{user.role}</span>
      </div>
    </aside>
  );
}

export function BottomTabBar() {
  const user = useAuth((s) => s.user)!;
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-30 flex h-14 border-t border-border bg-bg md:hidden"
    >
      {NAV[user.role].map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            cn(
              "flex flex-1 flex-col items-center justify-center gap-0.5 border-t-2 text-[11px]",
              isActive ? "border-accent text-accent" : "border-transparent text-ink-secondary",
            )
          }
        >
          <item.icon {...icon} />
          {item.short}
        </NavLink>
      ))}
    </nav>
  );
}

function NotificationsMenu() {
  const { data } = useNotifications();
  const markAll = useMarkAllRead();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const unread = data?.unread ?? 0;
  return (
    <div className="relative">
      <button
        type="button"
        aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="relative inline-flex h-8 w-8 items-center justify-center rounded text-ink-secondary hover:bg-surface hover:text-ink"
      >
        <Bell {...icon} />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 min-w-4 rounded-sm bg-accent px-1 font-mono text-[10px] leading-4 text-white">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 z-40 mt-1 w-[340px] rounded border border-border bg-bg shadow-overlay">
            <div className="flex h-9 items-center justify-between border-b border-border px-3 text-sm">
              <span className="font-medium">Notifications</span>
              {unread > 0 && (
                <button
                  className="text-xs text-accent hover:text-accent-hover"
                  onClick={() => markAll.mutate()}
                >
                  Mark all as read
                </button>
              )}
            </div>
            <ul className="max-h-[360px] divide-y divide-border overflow-y-auto">
              {(data?.items ?? []).length === 0 && (
                <li className="px-3 py-6 text-center text-sm text-ink-secondary">
                  No notifications yet.
                </li>
              )}
              {(data?.items ?? []).map((n) => (
                <li key={n.id}>
                  <button
                    className="block w-full px-3 py-2 text-left hover:bg-surface"
                    onClick={() => {
                      setOpen(false);
                      if (n.link) navigate(n.link);
                    }}
                  >
                    <div className="flex items-start gap-2">
                      {!n.read_at && (
                        <span
                          className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-sm bg-accent"
                          aria-label="Unread"
                        />
                      )}
                      <div className="min-w-0">
                        <p className="text-sm text-ink">{n.title}</p>
                        {n.body && <p className="truncate text-xs text-ink-secondary">{n.body}</p>}
                        <RelativeTime iso={n.created_at} className="text-xs text-ink-secondary" />
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}

export function TopBar() {
  const { user, clear } = useAuth();
  const navigate = useNavigate();
  async function logout() {
    try {
      await api.post("/api/auth/logout");
    } finally {
      clear();
      navigate("/login");
    }
  }
  return (
    <header className="sticky top-0 z-20 flex h-12 items-center justify-between border-b border-border bg-bg px-4">
      <div className="md:hidden">
        <Logo to={user ? homeFor(user.role) : "/"} />
      </div>
      <div className="hidden text-sm text-ink-secondary md:block">
        {user?.company ? user.company.name : null}
      </div>
      <div className="flex items-center gap-1">
        <NotificationsMenu />
        <Dropdown
          header={<span className="block truncate">{user?.email}</span>}
          trigger={(p) => (
            <button
              type="button"
              {...p}
              className="inline-flex h-8 items-center gap-1.5 rounded px-2 text-sm hover:bg-surface"
            >
              <span className="max-w-[160px] truncate">{user?.full_name}</span>
              <ChevronDown {...icon} size={14} />
            </button>
          )}
          items={[
            {
              label: (
                <>
                  <LogOut {...icon} /> Sign out
                </>
              ),
              onSelect: logout,
            },
          ]}
        />
      </div>
    </header>
  );
}

export function AppShell() {
  return (
    <div className="min-h-screen bg-bg">
      <Sidebar />
      <div className="md:pl-[240px]">
        <TopBar />
        <main className="mx-auto max-w-[1280px] px-4 pb-20 pt-4 md:pb-8">
          <Outlet />
        </main>
      </div>
      <BottomTabBar />
    </div>
  );
}
