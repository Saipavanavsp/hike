import type { ApplicationStatus } from "@/api/types";

export const COLUMNS: ApplicationStatus[] = [
  "applied",
  "shortlisted",
  "interview",
  "offer",
  "rejected",
];

/** Mirrors TRANSITIONS in backend/app/services/applications.py (the server is the authority). */
export const TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  applied: ["shortlisted", "rejected"],
  shortlisted: ["interview", "rejected", "applied"],
  interview: ["offer", "rejected", "shortlisted"],
  offer: ["interview"],
  rejected: ["applied", "shortlisted", "interview"],
};

export function canMove(from: ApplicationStatus, to: ApplicationStatus): boolean {
  return from === to || TRANSITIONS[from].includes(to);
}
