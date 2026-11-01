import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  AdminApplication,
  AdminJob,
  AdminUser,
  ApplicationStatus,
  DayCount,
  JobDetail,
  JobListItem,
  NotificationItem,
  Page,
  Profile,
  PublicStats,
  RecruiterApplication,
  RecruiterJobItem,
  Resume,
  SavedJobItem,
  SeekerApplication,
  Suggestion,
} from "./types";

// ---------- public ----------

export function usePublicStats() {
  return useQuery({
    queryKey: ["stats", "public"],
    queryFn: async () => (await api.get<PublicStats>("/api/stats/public")).data,
    staleTime: 60_000,
  });
}

// ---------- jobs ----------

export interface JobSearch {
  q: string;
  location: string[];
  role: string[];
  remote: string[];
  experience: number | null;
  sort: "relevance" | "newest" | "salary" | "match";
  page: number;
}

export function useJobs(params: JobSearch) {
  return useQuery({
    queryKey: ["jobs", params],
    queryFn: async () => {
      const { experience, ...rest } = params;
      const query = experience === null ? rest : { ...rest, experience };
      return (await api.get<Page<JobListItem>>("/api/jobs", { params: query })).data;
    },
    placeholderData: keepPreviousData,
  });
}

export function useAutocomplete(q: string) {
  return useQuery({
    queryKey: ["autocomplete", q],
    queryFn: async () =>
      (await api.get<Suggestion[]>("/api/jobs/autocomplete", { params: { q } })).data,
    enabled: q.trim().length >= 1,
    staleTime: 30_000,
  });
}

export function useJob(id: number) {
  return useQuery({
    queryKey: ["job", id],
    queryFn: async () => (await api.get<JobDetail>(`/api/jobs/${id}`)).data,
  });
}

export function useSavedJobs() {
  return useQuery({
    queryKey: ["saved"],
    queryFn: async () => (await api.get<SavedJobItem[]>("/api/jobs/saved")).data,
  });
}

export function useToggleSave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, saved }: { id: number; saved: boolean }) => {
      if (saved) await api.delete(`/api/jobs/${id}/save`);
      else await api.post(`/api/jobs/${id}/save`);
    },
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["saved"] });
      qc.invalidateQueries({ queryKey: ["job", id] });
    },
  });
}

// ---------- applications ----------

export function useApply() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { job_id: number; note?: string }) =>
      (await api.post<SeekerApplication>("/api/applications", body)).data,
    onSuccess: (_, { job_id }) => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["job", job_id] });
    },
  });
}

export function useMyApplications() {
  return useQuery({
    queryKey: ["applications"],
    queryFn: async () => (await api.get<SeekerApplication[]>("/api/applications")).data,
  });
}

// ---------- resumes & profile ----------

export function useResumes() {
  return useQuery({
    queryKey: ["resumes"],
    queryFn: async () => (await api.get<Resume[]>("/api/resumes")).data,
  });
}

export function useUploadResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return (await api.post<Resume>("/api/resumes", form)).data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["resumes"] }),
  });
}

export function useConfirmResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { id: number; skills: string[]; years_experience: number | null }) =>
      (
        await api.put<Resume>(`/api/resumes/${v.id}`, {
          skills: v.skills,
          years_experience: v.years_experience,
        })
      ).data,
    onSuccess: () => {
      // Match scores depend on the resume, so every job view is stale.
      qc.invalidateQueries({ queryKey: ["resumes"] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["job"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}

export function useSkillSearch(q: string) {
  return useQuery({
    queryKey: ["skills", q],
    queryFn: async () => (await api.get<string[]>("/api/skills", { params: { q } })).data,
    enabled: q.trim().length >= 1,
    staleTime: 300_000,
  });
}

export function useProfile() {
  return useQuery({
    queryKey: ["profile"],
    queryFn: async () => (await api.get<Profile>("/api/profile")).data,
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Partial<Profile>) =>
      (await api.put<Profile>("/api/profile", body)).data,
    onSuccess: (data) => {
      qc.setQueryData(["profile"], data);
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["job"] });
    },
  });
}

// ---------- notifications ----------

export function useNotifications() {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: async () =>
      (await api.get<{ items: NotificationItem[]; unread: number }>("/api/notifications")).data,
    refetchInterval: 30_000,
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => api.post("/api/notifications/read-all"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

// ---------- recruiter ----------

export function useRecruiterJobs() {
  return useQuery({
    queryKey: ["recruiter", "jobs"],
    queryFn: async () => (await api.get<RecruiterJobItem[]>("/api/recruiter/jobs")).data,
  });
}

export function useRecruiterJob(id: number | null) {
  return useQuery({
    queryKey: ["recruiter", "job", id],
    queryFn: async () => (await api.get<JobDetail>(`/api/recruiter/jobs/${id}`)).data,
    enabled: id !== null,
  });
}

export function useJobApplications(jobId: number | null) {
  return useQuery({
    queryKey: ["recruiter", "apps", jobId],
    queryFn: async () =>
      (await api.get<RecruiterApplication[]>(`/api/recruiter/jobs/${jobId}/applications`)).data,
    enabled: jobId !== null,
  });
}

export function useMoveApplication(jobId: number | null) {
  const qc = useQueryClient();
  const key = ["recruiter", "apps", jobId];
  return useMutation({
    mutationFn: async ({ id, status }: { id: number; status: ApplicationStatus }) =>
      (
        await api.patch<RecruiterApplication>(`/api/recruiter/applications/${id}/status`, {
          status,
        })
      ).data,
    // Optimistic move so the card lands in its new column immediately.
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: key });
      const previous = qc.getQueryData<RecruiterApplication[]>(key);
      qc.setQueryData<RecruiterApplication[]>(key, (apps) =>
        apps?.map((a) => (a.id === id ? { ...a, status } : a)),
      );
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(key, ctx.previous);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: key });
      qc.invalidateQueries({ queryKey: ["recruiter", "jobs"] });
    },
  });
}

export function useWeeklyApplications(jobId: number | null) {
  return useQuery({
    queryKey: ["recruiter", "weekly", jobId],
    queryFn: async () =>
      (
        await api.get<DayCount[]>("/api/recruiter/stats/applications-weekly", {
          params: jobId ? { job_id: jobId } : {},
        })
      ).data,
  });
}

export function useJobMutations() {
  const qc = useQueryClient();
  const done = () => {
    qc.invalidateQueries({ queryKey: ["recruiter"] });
    qc.invalidateQueries({ queryKey: ["jobs"] });
  };
  const create = useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await api.post<JobDetail>("/api/recruiter/jobs", body)).data,
    onSuccess: done,
  });
  const update = useMutation({
    mutationFn: async ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      (await api.patch<JobDetail>(`/api/recruiter/jobs/${id}`, body)).data,
    onSuccess: done,
  });
  const setStatus = useMutation({
    mutationFn: async ({ id, open }: { id: number; open: boolean }) =>
      (await api.post<JobDetail>(`/api/recruiter/jobs/${id}/${open ? "reopen" : "close"}`)).data,
    onSuccess: done,
  });
  return { create, update, setStatus };
}

// ---------- admin ----------

export interface AdminQuery {
  q: string;
  sort: string;
  order: "asc" | "desc";
  page: number;
}

function adminList<T>(path: string, params: AdminQuery) {
  return async () => (await api.get<Page<T>>(path, { params })).data;
}

export function useAdminUsers(params: AdminQuery) {
  return useQuery({
    queryKey: ["admin", "users", params],
    queryFn: adminList<AdminUser>("/api/admin/users", params),
    placeholderData: keepPreviousData,
  });
}

export function useAdminJobs(params: AdminQuery) {
  return useQuery({
    queryKey: ["admin", "jobs", params],
    queryFn: adminList<AdminJob>("/api/admin/jobs", params),
    placeholderData: keepPreviousData,
  });
}

export function useAdminApplications(params: AdminQuery) {
  return useQuery({
    queryKey: ["admin", "applications", params],
    queryFn: adminList<AdminApplication>("/api/admin/applications", params),
    placeholderData: keepPreviousData,
  });
}

export function useAdminBulk() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ path, ids }: { path: string; ids: number[] }) =>
      (await api.post<{ updated: number }>(path, { ids })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin"] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}
