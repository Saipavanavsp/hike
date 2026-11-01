import { api } from "./client";

/** Resume files need the bearer token, so they are fetched as a blob and opened in a new tab. */
export async function openResumeFile(resumeId: number): Promise<void> {
  // Open the tab synchronously so pop-up blockers treat it as user-initiated.
  const tab = window.open("", "_blank");
  try {
    const res = await api.get<Blob>(`/api/resumes/${resumeId}/file`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    if (tab) tab.location.href = url;
    else window.location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (err) {
    tab?.close();
    throw err;
  }
}
