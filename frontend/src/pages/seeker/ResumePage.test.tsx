import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/api/client";
import type { Resume } from "@/api/types";
import ResumePage from "./ResumePage";

function resume(status: Resume["status"], extra: Partial<Resume> = {}): Resume {
  return {
    id: 5,
    original_filename: "cv.pdf",
    mime_type: "application/pdf",
    size_bytes: 1000,
    status,
    parse_error: null,
    consent_at: "2026-11-01T10:00:00Z",
    parsed: {
      name: "Priya Sharma",
      email: null,
      phone: null,
      location: null,
      years_experience: 3,
      skills: [],
      education: [],
    },
    skills: ["Python"],
    years_experience: 3,
    is_current: false,
    confirmed_at: null,
    created_at: "2026-11-01T10:00:00Z",
    predicted_category: null,
    category_confidence: null,
    ...extra,
  };
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ResumePage />
    </QueryClientProvider>,
  );
}

const file = () => new File(["%PDF-1.4 test"], "cv.pdf", { type: "application/pdf" });

afterEach(() => vi.restoreAllMocks());

describe("ResumePage upload", () => {
  it("requires consent before a file can be uploaded", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: [] });
    const post = vi.spyOn(api, "post");
    const user = userEvent.setup();
    renderPage();
    const choose = await screen.findByRole("button", { name: "Choose file" });
    expect(choose).toBeDisabled();
    await user.upload(screen.getByLabelText("Resume file"), file());
    expect(screen.getByRole("alert")).toHaveTextContent("agree to resume processing");
    expect(post).not.toHaveBeenCalled();

    await user.click(screen.getByRole("checkbox", { name: /I agree that Hike may scan/ }));
    expect(choose).toBeEnabled();
  });

  it("sends consent, waits while the file is processed, then opens the review", async () => {
    let polls = 0;
    vi.spyOn(api, "get").mockImplementation(async (url: string) => {
      if (url === "/api/resumes/5") {
        polls += 1;
        return { data: polls === 1 ? resume("processing") : resume("ready") };
      }
      return { data: [] };
    });
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: resume("processing") });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("checkbox", { name: /I agree/ }));
    await user.upload(screen.getByLabelText("Resume file"), file());

    const form = post.mock.calls[0][1] as FormData;
    expect(form.get("consent")).toBe("true");
    expect(await screen.findByRole("status")).toHaveTextContent("Reading your resume");
    expect(await screen.findByText("Review: cv.pdf", {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it("shows why a file could not be read", async () => {
    vi.spyOn(api, "get").mockImplementation(async (url: string) =>
      url === "/api/resumes/5"
        ? { data: resume("failed", { parse_error: "No readable text found." }) }
        : { data: [] },
    );
    vi.spyOn(api, "post").mockResolvedValue({ data: resume("processing") });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("checkbox", { name: /I agree/ }));
    await user.upload(screen.getByLabelText("Resume file"), file());
    expect(
      await screen.findByText(/No readable text found\. Try another file\./),
    ).toBeInTheDocument();
  });
});
