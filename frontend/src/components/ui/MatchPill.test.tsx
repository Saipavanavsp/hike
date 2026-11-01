import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MatchPill, matchTone, StatusBadge } from "./Badges";

describe("matchTone thresholds", () => {
  it.each([
    [100, "green"],
    [80, "green"],
    [79, "amber"],
    [60, "amber"],
    [59, "grey"],
    [0, "grey"],
  ])("%i%% -> %s", (score, tone) => {
    expect(matchTone(score)).toBe(tone);
  });
});

describe("MatchPill", () => {
  it("renders the score in the mono font with the right tone", () => {
    render(<MatchPill score={82} />);
    const pill = screen.getByText("82%");
    expect(pill).toHaveAttribute("data-tone", "green");
    expect(pill.className).toContain("font-mono");
  });

  it("uses amber at exactly 60 and grey just below", () => {
    const { rerender } = render(<MatchPill score={60} />);
    expect(screen.getByText("60%")).toHaveAttribute("data-tone", "amber");
    rerender(<MatchPill score={59} />);
    expect(screen.getByText("59%")).toHaveAttribute("data-tone", "grey");
  });

  it("shows a dash when there is no score", () => {
    render(<MatchPill score={null} />);
    expect(screen.getByText("--")).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("labels statuses", () => {
    render(<StatusBadge status="shortlisted" />);
    expect(screen.getByText("Shortlisted")).toHaveAttribute("data-status", "shortlisted");
  });
});
