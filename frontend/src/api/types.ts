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

export interface MatchBreakdown {
  score: number;
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

export interface Resume {
  id: number;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
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
  resume: {
    id: number;
    filename: string;
    skills: string[];
    predicted_category: RoleCategory | null;
  };
  match: {
    score: number;
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

export interface AdminApplication {
  id: number;
  candidate: string;
  candidate_email: string;
  job_title: string;
  company: string;
  status: ApplicationStatus;
  applied_at: string;
}
