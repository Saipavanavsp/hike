import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import type { ApplicationStatus, RecruiterApplication } from "@/api/types";
import { KanbanBoard } from "./KanbanBoard";
import { canMove } from "./pipeline";

function app(
  id: number,
  name: string,
  status: ApplicationStatus,
  score: number,
): RecruiterApplication {
  return {
    id,
    job_id: 1,
    status,
    note: null,
    applied_at: "2026-10-30T10:00:00Z",
    updated_at: "2026-10-30T10:00:00Z",
    candidate: {
      id,
      name,
      email: `${id}@example.com`,
      phone: null,
      location: "Pune",
      years_experience: 3,
    },
    resume: {
      id: id * 10,
      filename: "cv.pdf",
      skills: ["Python", "Django", "Redis", "Docker", "AWS"],
      predicted_category: "backend",
    },
    match: {
      score,
      skills_matched: [],
      skills_missing: [],
      skills_ratio: "3/4",
      experience_ok: true,
      location_ok: true,
    },
  };
}

function Board({ onMove }: { onMove: (id: number, to: ApplicationStatus) => void }) {
  const [apps, setApps] = useState([
    app(1, "Priya Sharma", "applied", 84),
    app(2, "Arjun Menon", "interview", 61),
  ]);
  return (
    <KanbanBoard
      applications={apps}
      onOpenResume={() => {}}
      onInvalidMove={() => {}}
      onMove={(id, to) => {
        onMove(id, to);
        setApps((prev) => prev.map((a) => (a.id === id ? { ...a, status: to } : a)));
      }}
    />
  );
}

describe("KanbanBoard", () => {
  it("renders five columns with counts and dense cards", () => {
    render(<Board onMove={() => {}} />);
    const applied = screen.getByRole("region", { name: /Applied column, 1 candidates/ });
    expect(within(applied).getByText("Priya Sharma")).toBeInTheDocument();
    expect(within(applied).getByText("84%")).toBeInTheDocument();
    // Only the top 4 skills are shown.
    expect(within(applied).queryByText("AWS")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: /Offer column, 0 candidates/ })).toBeInTheDocument();
  });

  it("moves a candidate to Shortlisted from the card menu", async () => {
    const user = userEvent.setup();
    const onMove = vi.fn();
    render(<Board onMove={onMove} />);
    await user.click(screen.getByRole("button", { name: "Actions for Priya Sharma" }));
    // Only allowed transitions are offered: Applied cannot jump to Offer.
    expect(screen.queryByRole("menuitem", { name: "Move to Offer" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("menuitem", { name: "Move to Shortlisted" }));
    expect(onMove).toHaveBeenCalledWith(1, "shortlisted");
    const shortlisted = screen.getByRole("region", { name: /Shortlisted column, 1 candidates/ });
    expect(within(shortlisted).getByText("Priya Sharma")).toBeInTheDocument();
  });

  it("exposes cards to keyboard users as draggable", () => {
    render(<Board onMove={() => {}} />);
    const handle = screen.getByRole("button", { name: "Priya Sharma" });
    expect(handle).toHaveAttribute("aria-roledescription", "Draggable candidate");
    expect(handle).toHaveAttribute("tabindex", "0");
  });
});

describe("pipeline transitions", () => {
  it("mirrors the server rules", () => {
    expect(canMove("applied", "shortlisted")).toBe(true);
    expect(canMove("applied", "offer")).toBe(false);
    expect(canMove("interview", "offer")).toBe(true);
    expect(canMove("offer", "applied")).toBe(false);
    expect(canMove("rejected", "shortlisted")).toBe(true);
  });
});
