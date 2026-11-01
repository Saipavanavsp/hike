import { create } from "zustand";
import type { User } from "@/api/types";

type Status = "loading" | "authenticated" | "anonymous";

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
  setSession: (accessToken, user) => set({ accessToken, user, status: "authenticated" }),
  setUser: (user) => set({ user }),
  clear: () => set({ accessToken: null, user: null, status: "anonymous" }),
}));
