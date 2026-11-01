import {
  Activity,
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
  end?: boolean;
}

export const NAV: Record<Role, NavItem[]> = {
  seeker: [
    { to: "/jobs", label: "Dashboard", short: "Jobs", icon: LayoutList },
    { to: "/applications", label: "My Applications", short: "Applied", icon: ClipboardList },
    { to: "/saved", label: "Saved Jobs", short: "Saved", icon: Bookmark },
    { to: "/profile", label: "Profile", short: "Profile", icon: User },
    { to: "/resume", label: "Resume", short: "Resume", icon: FileText },
  ],
  recruiter: [
    { to: "/recruiter", label: "Pipeline", short: "Pipeline", icon: Kanban, end: true },
    { to: "/recruiter/jobs", label: "My jobs", short: "Jobs", icon: Briefcase, end: true },
    { to: "/recruiter/jobs/new", label: "Post a job", short: "Post", icon: PlusSquare },
  ],
  admin: [
    { to: "/admin/users", label: "Users", short: "Users", icon: Users },
    { to: "/admin/jobs", label: "Jobs", short: "Jobs", icon: Briefcase },
    { to: "/admin/applications", label: "Applications", short: "Apps", icon: Send },
    { to: "/admin/system", label: "System", short: "System", icon: Activity },
  ],
};

export function homeFor(role: Role): string {
  return { seeker: "/jobs", recruiter: "/recruiter", admin: "/admin/users" }[role];
}
