import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  AdminApplication,
  AdminJob,
  AdminUser,
  ApplicationStatus,
  AuditEntry,
  Company,
  CompanyPage,
  Interview,
  InterviewMode,
  RecruiterAnalytics,
  SavedSearch,
  SearchFilters,
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
  SystemOverview,
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

export function useResumes(enabled = true) {
  return useQuery({
    queryKey: ["resumes"],
    queryFn: async () => (await api.get<Resume[]>("/api/resumes")).data,
    enabled,
  });
}

export function useUploadResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, consent }: { file: File; consent: boolean }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("consent", consent ? "true" : "false");
      return (await api.post<Resume>("/api/resumes", form)).data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["resumes"] }),
  });
}

/** Polls a resume while the background parser is working on it. */
export function useResume(id: number | null) {
  return useQuery({
    queryKey: ["resume", id],
    queryFn: async () => (await api.get<Resume>(`/api/resumes/${id}`)).data,
    enabled: id !== null,
    refetchInterval: (q) => (q.state.data?.status === "processing" ? 1000 : false),
  });
}

export function useDeleteResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => api.delete(`/api/resumes/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["resumes"] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["job"] });
    },
  });
}

export function useDeleteAccount() {
  return useMutation({
    mutationFn: async (password: string) => api.post("/api/account/delete", { password }),
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

export function useSystemOverview() {
  return useQuery({
    queryKey: ["admin", "system"],
    queryFn: async () => (await api.get<SystemOverview>("/api/admin/system")).data,
    refetchInterval: 15_000,
  });
}

export function useRunRetention() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => (await api.post<{ task_id: string }>("/api/admin/retention/run")).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "system"] }),
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

// ---------- interviews ----------

export interface InterviewInput {
  starts_at: string;
  duration_minutes: number;
  mode: InterviewMode;
  location: string;
  notes: string;
}

export function useInterviews(upcoming = false) {
  return useQuery({
    queryKey: ["interviews", { upcoming }],
    queryFn: async () =>
      (await api.get<Interview[]>("/api/interviews", { params: { upcoming } })).data,
  });
}

export function useInterviewMutations() {
  const qc = useQueryClient();
  const done = () => qc.invalidateQueries({ queryKey: ["interviews"] });
  const schedule = useMutation({
    mutationFn: async ({ applicationId, body }: { applicationId: number; body: InterviewInput }) =>
      (await api.post<Interview>(`/api/recruiter/applications/${applicationId}/interviews`, body))
        .data,
    onSuccess: done,
  });
  const cancel = useMutation({
    mutationFn: async (id: number) =>
      (await api.post<Interview>(`/api/recruiter/interviews/${id}/cancel`)).data,
    onSuccess: done,
  });
  return { schedule, cancel };
}

// ---------- saved searches ----------

export function useSavedSearches(enabled = true) {
  return useQuery({
    queryKey: ["saved-searches"],
    queryFn: async () => (await api.get<SavedSearch[]>("/api/saved-searches")).data,
    enabled,
  });
}

export function useSavedSearchMutations() {
  const qc = useQueryClient();
  const done = () => qc.invalidateQueries({ queryKey: ["saved-searches"] });
  const create = useMutation({
    mutationFn: async (body: { name: string; params: SearchFilters }) =>
      (await api.post<SavedSearch>("/api/saved-searches", body)).data,
    onSuccess: done,
  });
  const toggle = useMutation({
    mutationFn: async ({ id, alerts_enabled }: { id: number; alerts_enabled: boolean }) =>
      (await api.patch<SavedSearch>(`/api/saved-searches/${id}`, { alerts_enabled })).data,
    onSuccess: done,
  });
  const remove = useMutation({
    mutationFn: async (id: number) => api.delete(`/api/saved-searches/${id}`),
    onSuccess: done,
  });
  return { create, toggle, remove };
}

// ---------- analytics, companies, preferences, audit ----------

export function useRecruiterAnalytics(jobId: number | null) {
  return useQuery({
    queryKey: ["recruiter", "analytics", jobId],
    queryFn: async () =>
      (
        await api.get<RecruiterAnalytics>("/api/recruiter/analytics", {
          params: jobId ? { job_id: jobId } : {},
        })
      ).data,
  });
}

export function useCompanyPage(slug: string) {
  return useQuery({
    queryKey: ["company", slug],
    queryFn: async () => (await api.get<CompanyPage>(`/api/companies/${slug}`)).data,
  });
}

export function useMyCompany() {
  return useQuery({
    queryKey: ["recruiter", "company"],
    queryFn: async () => (await api.get<Company>("/api/recruiter/company")).data,
  });
}

export function useUpdateMyCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Partial<Company>) =>
      (await api.put<Company>("/api/recruiter/company", body)).data,
    onSuccess: (data) => {
      qc.setQueryData(["recruiter", "company"], data);
      qc.invalidateQueries({ queryKey: ["company", data.slug] });
    },
  });
}

export function usePreferences() {
  return useQuery({
    queryKey: ["preferences"],
    queryFn: async () =>
      (await api.get<{ email_notifications: boolean }>("/api/account/preferences")).data,
  });
}

export function useUpdatePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (email_notifications: boolean) =>
      (
        await api.put<{ email_notifications: boolean }>("/api/account/preferences", {
          email_notifications,
        })
      ).data,
    onSuccess: (data) => qc.setQueryData(["preferences"], data),
  });
}

export function useAuditLog(params: { q: string; action: string; page: number }) {
  return useQuery({
    queryKey: ["admin", "audit", params],
    queryFn: async () => (await api.get<Page<AuditEntry>>("/api/admin/audit", { params })).data,
    placeholderData: keepPreviousData,
  });
}
