import { create } from "zustand";
import type { User } from "@/api/types";

type Status = "loading" | "authenticated" | "anonymous";

// The refresh cookie is httpOnly, so JS cannot see it. This non-secret flag only records
// that a session may exist, so anonymous visitors skip a refresh call that would 401.
const SESSION_HINT = "hike.session";

export function hasSessionHint(): boolean {
  try {
    return localStorage.getItem(SESSION_HINT) === "1";
  } catch {
    return false;
  }
}

function setHint(on: boolean) {
  try {
    if (on) localStorage.setItem(SESSION_HINT, "1");
    else localStorage.removeItem(SESSION_HINT);
  } catch {
    /* storage unavailable (private mode): the refresh call still works */
  }
}

interface AuthState {
  // The access token lives only in memory; the refresh token is an httpOnly cookie.
  accessToken: string | null;
  user: User | null;
  status: Status;
  setSession: (token: string, user: User) => void;
  setUser: (user: User) => void;
  clear: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  status: "loading",
  setSession: (accessToken, user) => {
    setHint(true);
    set({ accessToken, user, status: "authenticated" });
  },
  setUser: (user) => set({ user }),
  clear: () => {
    setHint(false);
    set({ accessToken: null, user: null, status: "anonymous" });
  },
}));
