import { api } from "./client";

/**
 * Asks the API for a short-lived signed link to the file, then opens it in a new tab.
 * The link works without the bearer token and expires after a few minutes.
 */
export async function openResumeFile(resumeId: number): Promise<void> {
  // Open the tab synchronously so pop-up blockers treat it as user-initiated.
  const tab = window.open("", "_blank");
  try {
    const { data } = await api.post<{ url: string; expires_at: number }>(
      `/api/resumes/${resumeId}/link`,
    );
    if (tab) {
      tab.opener = null;
      tab.location.href = data.url;
    } else window.location.href = data.url;
  } catch (err) {
    tab?.close();
    throw err;
  }
}

/** Download an interview's .ics invite (needs the bearer token, so it goes through axios). */
export async function downloadInterviewIcs(interviewId: number): Promise<void> {
  const res = await api.get<Blob>(`/api/interviews/${interviewId}/ics`, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = `interview-${interviewId}.ics`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
