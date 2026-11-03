import {
  Activity,
  BarChart3,
  Building2,
  CalendarClock,
  ScrollText,
  Bookmark,
  Briefcase,
  ClipboardList,
  FileText,
  Kanban,
  LayoutList,
  type LucideIcon,
  PlusSquare,
  Send,
  User,
  Users,
} from "lucide-react";
import type { Role } from "@/api/types";

export interface NavItem {
  to: string;
  label: string;
  short: string; // bottom tab bar label
  icon: LucideIcon;
  group: string; // sidebar section heading; items of a group are listed together
  end?: boolean;
}

export const NAV: Record<Role, NavItem[]> = {
  seeker: [
    { to: "/jobs", label: "Dashboard", short: "Jobs", icon: LayoutList, group: "Job search" },
    {
      to: "/applications",
      label: "My Applications",
      short: "Applied",
      icon: ClipboardList,
      group: "Job search",
    },
    { to: "/saved", label: "Saved Jobs", short: "Saved", icon: Bookmark, group: "Job search" },
    { to: "/profile", label: "Profile", short: "Profile", icon: User, group: "Account" },
    { to: "/resume", label: "Resume", short: "Resume", icon: FileText, group: "Account" },
  ],
  recruiter: [
    {
      to: "/recruiter",
      label: "Pipeline",
      short: "Pipeline",
      icon: Kanban,
      group: "Hiring",
      end: true,
    },
    {
      to: "/recruiter/jobs",
      label: "My jobs",
      short: "Jobs",
      icon: Briefcase,
      group: "Hiring",
      end: true,
    },
    {
      to: "/recruiter/jobs/new",
      label: "Post a job",
      short: "Post",
      icon: PlusSquare,
      group: "Hiring",
    },
    {
      to: "/recruiter/interviews",
      label: "Interviews",
      short: "Interviews",
      icon: CalendarClock,
      group: "Hiring",
    },
    {
      to: "/recruiter/analytics",
      label: "Analytics",
      short: "Stats",
      icon: BarChart3,
      group: "Organisation",
    },
    {
      to: "/recruiter/company",
      label: "Company profile",
      short: "Company",
      icon: Building2,
      group: "Organisation",
    },
  ],
  admin: [
    { to: "/admin/users", label: "Users", short: "Users", icon: Users, group: "Manage" },
    { to: "/admin/jobs", label: "Jobs", short: "Jobs", icon: Briefcase, group: "Manage" },
    {
      to: "/admin/applications",
      label: "Applications",
      short: "Apps",
      icon: Send,
      group: "Manage",
    },
    { to: "/admin/system", label: "System", short: "System", icon: Activity, group: "Platform" },
    {
      to: "/admin/audit",
      label: "Audit log",
      short: "Audit",
      icon: ScrollText,
      group: "Platform",
    },
  ],
};

export const ROLE_LABELS: Record<Role, string> = {
  seeker: "Job seeker",
  recruiter: "Recruiter",
  admin: "Administrator",
};

/** Sidebar sections in NAV order. */
export function navGroups(role: Role): { group: string; items: NavItem[] }[] {
  const out: { group: string; items: NavItem[] }[] = [];
  for (const item of NAV[role]) {
    const last = out[out.length - 1];
    if (last && last.group === item.group) last.items.push(item);
    else out.push({ group: item.group, items: [item] });
  }
  return out;
}

export interface Crumb {
  label: string;
  to?: string;
}

/** Breadcrumbs for the top bar: section, page and (on detail routes) the detail view. */
export function breadcrumbsFor(role: Role, pathname: string): Crumb[] {
  const items = NAV[role];
  const exact = items.find((i) => i.to === pathname);
  if (exact) return [{ label: exact.group }, { label: exact.label }];

  const detail: [RegExp, string, string | null][] = [
    [/^\/recruiter\/jobs\/[^/]+\/edit$/, "Edit job", "/recruiter/jobs"],
    [/^\/recruiter\/jobs\/[^/]+$/, "Candidates", "/recruiter/jobs"],
    [/^\/jobs\/[^/]+$/, "Job details", "/jobs"],
    [/^\/companies\/[^/]+$/, "Company", null],
  ];
  for (const [re, label, parentTo] of detail) {
    if (!re.test(pathname)) continue;
    const parent = parentTo ? items.find((i) => i.to === parentTo) : undefined;
    return parent
      ? [{ label: parent.group }, { label: parent.label, to: parent.to }, { label }]
      : [{ label }];
  }
  return [];
}

export function homeFor(role: Role): string {
  return { seeker: "/jobs", recruiter: "/recruiter", admin: "/admin/users" }[role];
}
