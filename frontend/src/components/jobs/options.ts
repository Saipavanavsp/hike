import type { ChipOption } from "./FilterChip";

export const CITIES = ["Bengaluru", "Hyderabad", "Chennai", "Pune"];

export const LOCATION_OPTIONS: ChipOption[] = [
  ...CITIES.map((c) => ({ value: c, label: c })),
  { value: "Remote", label: "Remote" },
];

export const ROLE_OPTIONS: ChipOption[] = [
  { value: "backend", label: "Backend" },
  { value: "frontend", label: "Frontend" },
  { value: "fullstack", label: "Full-Stack" },
  { value: "data_ml", label: "Data/ML" },
  { value: "devops", label: "DevOps" },
  { value: "mobile", label: "Mobile" },
  { value: "qa", label: "QA" },
];

export const EXPERIENCE_OPTIONS: ChipOption[] = [
  { value: "0", label: "Fresher" },
  { value: "1", label: "1 year" },
  { value: "2", label: "2 years" },
  { value: "3", label: "3 years" },
  { value: "5", label: "5 years" },
  { value: "8", label: "8 years" },
  { value: "10", label: "10+ years" },
];

export const REMOTE_OPTIONS: ChipOption[] = [
  { value: "onsite", label: "On-site" },
  { value: "hybrid", label: "Hybrid" },
  { value: "remote", label: "Remote" },
];
