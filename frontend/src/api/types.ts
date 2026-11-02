export type Role = "seeker" | "recruiter" | "admin";
export type RemoteType = "onsite" | "hybrid" | "remote";
export type RoleCategory =
  "backend" | "frontend" | "fullstack" | "data_ml" | "devops" | "mobile" | "qa";
export type ApplicationStatus = "applied" | "shortlisted" | "interview" | "offer" | "rejected";

export interface CompanyBrief {
  id: number;
  name: string;
  slug: string;
  logo_url: string | null;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  company: CompanyBrief | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface JobListItem {
  id: number;
  title: string;
  company: CompanyBrief;
  role_category: RoleCategory;
  location: string;
  remote_type: RemoteType;
  experience_min: number;
  experience_max: number;
  salary_min: number;
  salary_max: number;
  skills: string[];
  status: "open" | "closed";
  posted_at: string;
  match_score: number | null;
}

export interface ScoreComponent {
  key: "semantic" | "skills" | "experience" | "location";
  label: string;
  weight: number;
  points: number;
  detail: string;
}

export interface MatchBreakdown {
  score: number;
  components: ScoreComponent[];
  skills_matched: string[];
  skills_missing: string[];
  skills_ratio: string;
  experience_ok: boolean;
  experience_years: number | null;
  location_ok: boolean;
  semantic: number;
  cosine: number | null;
  skill_overlap: number;
  experience_fit: number;
  location_fit: number;
}

export interface JobDetail extends JobListItem {
  description_md: string;
  recruiter_id: number;
  is_saved: boolean;
  application_status: ApplicationStatus | null;
  application_id: number | null;
  match: MatchBreakdown | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  /** Job search only: set when a misspelt word was corrected. */
  corrected_query?: string | null;
}

export interface SavedJobItem extends JobListItem {
  saved_at: string;
}

export interface Suggestion {
  text: string;
  kind: "title" | "skill";
}

export interface RecruiterJobItem extends JobListItem {
  applications_count: number;
  new_count: number;
}

export interface ParsedFields {
  name: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  years_experience: number | null;
  skills: string[];
  education: string[];
}

export type ResumeStatus = "processing" | "ready" | "failed";

export interface Resume {
  id: number;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  status: ResumeStatus;
  parse_error: string | null;
  consent_at: string | null;
  parsed: ParsedFields;
  skills: string[];
  years_experience: number | null;
  is_current: boolean;
  confirmed_at: string | null;
  created_at: string;
  predicted_category: RoleCategory | null;
  category_confidence: number | null;
}

export interface HistoryItem {
  from_status: ApplicationStatus | null;
  to_status: ApplicationStatus;
  changed_at: string;
  changed_by_name: string | null;
  changed_by_role: Role | null;
}

export interface SeekerApplication {
  id: number;
  status: ApplicationStatus;
  note: string | null;
  applied_at: string;
  updated_at: string;
  job: JobListItem;
  history: HistoryItem[];
}

export interface RecruiterApplication {
  id: number;
  job_id: number;
  status: ApplicationStatus;
  note: string | null;
  applied_at: string;
  updated_at: string;
  candidate: {
    id: number;
    name: string;
    email: string;
    phone: string | null;
    location: string | null;
    years_experience: number | null;
  };
  /** null when the candidate has deleted the resume they applied with. */
  resume: {
    id: number;
    filename: string;
    skills: string[];
    predicted_category: RoleCategory | null;
  } | null;
  match: {
    score: number;
    components: ScoreComponent[];
    skills_matched: string[];
    skills_missing: string[];
    skills_ratio: string;
    experience_ok: boolean;
    location_ok: boolean;
  } | null;
}

export interface DayCount {
  date: string;
  count: number;
}

export interface NotificationItem {
  id: number;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  read_at: string | null;
  created_at: string;
}

export interface PublicStats {
  open_jobs: number;
  companies: number;
  recruiters: number;
  candidates: number;
  precision_at_5: number | null;
  tfidf_precision_at_5: number | null;
  eval_run_at: string | null;
}

export interface Profile {
  full_name: string;
  email: string;
  headline: string | null;
  current_location: string | null;
  preferred_locations: string[];
  open_to_remote: boolean;
  years_experience: number | null;
  phone: string | null;
}

export interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  company: string | null;
}

export interface AdminJob {
  id: number;
  title: string;
  company: string;
  recruiter: string;
  location: string;
  status: "open" | "closed";
  posted_at: string;
  applications: number;
}

export interface AdminTask {
  id: string;
  kind: string;
  /** rejected = the input was refused (e.g. unreadable file); failed = something broke. */
  status: "queued" | "running" | "retrying" | "succeeded" | "rejected" | "failed";
  attempts: number;
  error: string | null;
  ref_type: string | null;
  ref_id: number | null;
  created_at: string;
  finished_at: string | null;
  retried_as: string | null;
}

export interface SystemOverview {
  dependencies: {
    postgres: { ok: boolean; latency_ms: number };
    redis: { ok: boolean; latency_ms: number };
    clamav: { ok: boolean } | null;
  };
  worker: "ok" | "down" | "inline";
  queue_depth: number | null;
  tasks_last_24h: Record<AdminTask["status"], number>;
  recent_failures: AdminTask[];
  dead_letter: number;
  security: {
    malware_scan: string;
    parser_isolation: string;
    files_encrypted: boolean;
    signed_url_ttl_seconds: number;
  };
  retention: { unconfirmed_days: number; old_resume_days: number; inactive_seeker_days: number };
}

export type InterviewMode = "video" | "phone" | "onsite";

export interface Interview {
  id: number;
  application_id: number;
  job_id: number;
  job_title: string;
  company: string;
  candidate_name: string;
  starts_at: string;
  duration_minutes: number;
  mode: InterviewMode;
  location: string | null;
  notes: string | null;
  status: "scheduled" | "cancelled";
  google_calendar_url: string;
}

export interface SearchFilters {
  q: string;
  location: string[];
  role: RoleCategory[];
  remote: RemoteType[];
  experience: number | null;
}

export interface SavedSearch {
  id: number;
  name: string;
  params: SearchFilters;
  summary: string;
  alerts_enabled: boolean;
  last_alert_at: string | null;
  created_at: string;
}

export interface FunnelStep {
  stage: "applied" | "shortlisted" | "interview" | "offer";
  count: number;
  conversion_from_previous: number | null;
}

export interface RecruiterAnalytics {
  total_applications: number;
  funnel: FunnelStep[];
  rejected: number;
  offer_rate: number | null;
  median_days_to_first_response: number | null;
  median_days_to_offer: number | null;
  offers_measured: number;
  avg_days_in_stage: Partial<Record<ApplicationStatus, number>>;
  by_job: {
    job_id: number;
    title: string;
    applications: number;
    interviews: number;
    offers: number;
    median_days_to_offer: number | null;
  }[];
}

export interface Company {
  id: number;
  name: string;
  slug: string;
  logo_url: string | null;
  website: string | null;
  industry: string | null;
  size_range: string | null;
  hq_city: string | null;
  about: string | null;
}

export interface CompanyPage {
  company: Company;
  open_jobs: JobListItem[];
  recruiters: number;
}

export interface AuditEntry {
  id: number;
  created_at: string;
  actor: string | null;
  actor_role: Role | null;
  action: string;
  target_type: string | null;
  target_id: number | null;
  details: Record<string, unknown>;
  ip: string | null;
  request_id: string | null;
}

export interface AdminApplication {
  id: number;
  candidate: string;
  candidate_email: string;
  job_title: string;
  company: string;
  status: ApplicationStatus;
  applied_at: string;
}
