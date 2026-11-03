import { Bell, BellOff, ChevronDown, ChevronRight, LogOut, Moon, Search, Sun } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useMatches, useNavigate } from "react-router-dom";
import { api } from "@/api/client";
import { useMarkAllRead, useNotifications } from "@/api/queries";
import { icon } from "@/components/ui/icon";
import { Dropdown } from "@/components/ui/Dropdown";
import { RelativeTime } from "@/components/ui/Misc";
import { cn } from "@/lib/cn";
import { initials } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { useTheme } from "@/stores/theme";
import { CommandPalette } from "./CommandPalette";
import { Logo } from "./Logo";
import { breadcrumbsFor, homeFor, NAV, navGroups, ROLE_LABELS } from "./nav";

function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full bg-accent-brand/15 text-xs font-semibold text-accent",
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}

export function Sidebar() {
  const user = useAuth((s) => s.user)!;
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] flex-col border-r border-sidebar-border bg-sidebar text-sidebar-fg md:flex">
      <div className="flex h-14 items-center px-5">
        <Logo to={homeFor(user.role)} className="text-sidebar-fg hover:text-sidebar-fg" />
      </div>
      <nav aria-label="Main" className="flex-1 space-y-5 overflow-y-auto px-3 py-3">
        {navGroups(user.role).map(({ group, items }) => (
          <div key={group}>
            <p className="mb-1.5 px-3 text-2xs font-semibold uppercase tracking-[0.08em] text-sidebar-muted/80">
              {group}
            </p>
            <ul className="space-y-0.5">
              {items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      cn(
                        "group relative flex h-9 items-center gap-3 rounded-md px-3 text-sm transition-colors",
                        "focus-visible:ring-offset-sidebar",
                        isActive
                          ? "bg-sidebar-active font-medium text-white hover:text-white"
                          : "text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg",
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <span
                            aria-hidden
                            className="absolute inset-y-2 left-0 w-[3px] rounded-r-full bg-accent-brand"
                          />
                        )}
                        <item.icon
                          {...icon}
                          className={
                            isActive
                              ? "text-accent-brand"
                              : "text-sidebar-muted group-hover:text-sidebar-fg"
                          }
                        />
                        {item.label}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-3 rounded-md px-2 py-2">
          <Avatar name={user.full_name} className="h-8 w-8 bg-accent-brand/20 text-[#5ED3C4]" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-sidebar-fg">{user.full_name}</p>
            <p className="truncate text-xs text-sidebar-muted">
              {user.company ? user.company.name : ROLE_LABELS[user.role]}
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}

export function BottomTabBar() {
  const user = useAuth((s) => s.user)!;
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-30 flex h-16 border-t border-border bg-bg/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
    >
      {NAV[user.role].map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            cn(
              "flex min-w-0 flex-1 flex-col items-center justify-center gap-1 text-2xs font-medium transition-colors",
              isActive ? "text-accent" : "text-ink-secondary hover:text-ink",
            )
          }
        >
          {({ isActive }) => (
            <>
              <span
                className={cn(
                  "flex h-7 w-12 items-center justify-center rounded-full transition-colors",
                  isActive && "bg-accent-tint",
                )}
              >
                <item.icon {...icon} />
              </span>
              <span className="max-w-full truncate px-0.5">{item.short}</span>
            </>
          )}
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
        className={cn(
          "relative inline-flex h-9 w-9 items-center justify-center rounded-md text-ink-secondary transition-colors hover:bg-surface hover:text-ink",
          open && "bg-surface text-ink",
        )}
      >
        <Bell {...icon} />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 font-mono text-[10px] font-semibold leading-none text-accent-fg ring-2 ring-bg">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 z-40 mt-2 w-[min(360px,calc(100vw-2rem))] origin-top-right animate-scale-in overflow-hidden rounded-xl border border-border bg-bg shadow-overlay">
            <div className="flex h-12 items-center justify-between border-b border-border px-4 text-sm">
              <span className="font-semibold">Notifications</span>
              {unread > 0 && (
                <button
                  className="text-xs font-medium text-accent hover:text-accent-hover"
                  onClick={() => markAll.mutate()}
                >
                  Mark all as read
                </button>
              )}
            </div>
            <ul className="max-h-[380px] divide-y divide-border overflow-y-auto">
              {(data?.items ?? []).length === 0 && (
                <li className="flex flex-col items-center gap-2 px-4 py-10 text-center text-sm text-ink-secondary">
                  <BellOff {...icon} size={20} className="text-ink-muted" />
                  No notifications yet.
                </li>
              )}
              {(data?.items ?? []).map((n) => (
                <li key={n.id}>
                  <button
                    className={cn(
                      "block w-full px-4 py-3 text-left transition-colors hover:bg-surface",
                      !n.read_at && "bg-accent-tint/40",
                    )}
                    onClick={() => {
                      setOpen(false);
                      if (n.link) navigate(n.link);
                    }}
                  >
                    <div className="flex items-start gap-2.5">
                      <span
                        className={cn(
                          "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                          n.read_at ? "bg-transparent" : "bg-accent",
                        )}
                        aria-label={n.read_at ? undefined : "Unread"}
                      />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-ink">{n.title}</p>
                        {n.body && (
                          <p className="mt-0.5 line-clamp-2 text-xs text-ink-secondary">{n.body}</p>
                        )}
                        <RelativeTime
                          iso={n.created_at}
                          className="mt-1 block text-2xs text-ink-muted"
                        />
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

function ThemeToggle() {
  const { dark, toggle } = useTheme();
  const label = dark ? "Switch to light theme" : "Switch to dark theme";
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={toggle}
      className="inline-flex h-9 w-9 items-center justify-center rounded-md text-ink-secondary transition-colors hover:bg-surface hover:text-ink"
    >
      {dark ? <Sun {...icon} /> : <Moon {...icon} />}
    </button>
  );
}

function Breadcrumbs() {
  const user = useAuth((s) => s.user);
  const { pathname } = useLocation();
  if (!user) return null;
  const crumbs = breadcrumbsFor(user.role, pathname);
  if (!crumbs.length) return null;
  return (
    <nav aria-label="Breadcrumb" className="hidden min-w-0 md:block">
      <ol className="flex min-w-0 items-center gap-1.5 text-sm">
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <li key={i} className="flex min-w-0 items-center gap-1.5">
              {i > 0 && <ChevronRight {...icon} size={14} className="shrink-0 text-ink-muted" />}
              {c.to && !last ? (
                <Link to={c.to} className="truncate text-ink-secondary hover:text-ink">
                  {c.label}
                </Link>
              ) : (
                <span
                  aria-current={last ? "page" : undefined}
                  className={cn("truncate", last ? "font-medium text-ink" : "text-ink-secondary")}
                >
                  {c.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function TopBar({ onOpenSearch }: { onOpenSearch: () => void }) {
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
    // A div with the banner role, not <header>: page content uses <header> for its own titles.
    <div
      role="banner"
      className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-border bg-bg/85 px-4 backdrop-blur-md md:px-6"
    >
      <div className="flex min-w-0 items-center gap-3">
        <div className="md:hidden">
          <Logo to={user ? homeFor(user.role) : "/"} />
        </div>
        <Breadcrumbs />
      </div>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={onOpenSearch}
          aria-label="Open command menu (Ctrl+K)"
          className="mr-1 inline-flex h-9 items-center gap-2 rounded-md border border-border bg-canvas px-2.5 text-sm text-ink-muted shadow-xs transition-colors hover:border-border-strong hover:text-ink-secondary sm:w-56 lg:w-64"
        >
          <Search {...icon} />
          <span className="hidden flex-1 text-left sm:inline">
            {user?.role === "seeker" ? "Search or jump to…" : "Jump to…"}
          </span>
          <kbd className="hidden rounded border border-border bg-bg px-1.5 font-mono text-2xs text-ink-secondary sm:inline">
            Ctrl K
          </kbd>
        </button>
        <ThemeToggle />
        <NotificationsMenu />
        <span aria-hidden className="mx-1.5 hidden h-6 w-px bg-border sm:block" />
        <Dropdown
          header={
            <span className="block">
              <span className="block truncate font-medium text-ink">{user?.full_name}</span>
              <span className="block truncate">{user?.email}</span>
            </span>
          }
          trigger={(p) => (
            <button
              type="button"
              {...p}
              className="inline-flex h-9 items-center gap-2 rounded-md pl-1 pr-1.5 text-sm transition-colors hover:bg-surface sm:pr-2"
            >
              <Avatar name={user?.full_name ?? ""} className="h-7 w-7" />
              <span className="sr-only max-w-[160px] truncate font-medium sm:not-sr-only">
                {user?.full_name}
              </span>
              <ChevronDown {...icon} size={14} className="text-ink-muted" />
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
              danger: true,
            },
          ]}
        />
      </div>
    </div>
  );
}

/** Fades each page in when the route (not just its search params) changes. */
function PageTransition() {
  const matches = useMatches();
  const routeId = matches[matches.length - 1]?.id;
  return (
    <div key={routeId} className="animate-fade-up">
      <Outlet />
    </div>
  );
}

export function AppShell() {
  const user = useAuth((s) => s.user)!;
  const [paletteOpen, setPaletteOpen] = useState(false);
  const closePalette = useCallback(() => setPaletteOpen(false), []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="min-h-screen bg-canvas">
      <Sidebar />
      <div className="md:pl-[248px]">
        <TopBar onOpenSearch={() => setPaletteOpen(true)} />
        <main className="mx-auto max-w-[1320px] px-4 pb-24 pt-6 md:px-8 md:pb-10 md:pt-8">
          <PageTransition />
        </main>
      </div>
      <BottomTabBar />
      <CommandPalette role={user.role} open={paletteOpen} onClose={closePalette} />
    </div>
  );
}
