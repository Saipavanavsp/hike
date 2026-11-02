import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ScoreComponent } from "@/api/types";
import { ScoreComponents } from "./ScoreComponents";

const components: ScoreComponent[] = [
  {
    key: "semantic",
    label: "Resume and job description similarity",
    weight: 50,
    points: 31.4,
    detail: "Text similarity 0.46 (scaled from 0.15-0.65)",
  },
  {
    key: "skills",
    label: "Required skills",
    weight: 35,
    points: 28,
    detail: "8 of 10 required skills",
  },
  {
    key: "experience",
    label: "Experience",
    weight: 10,
    points: 10,
    detail: "3 yrs; job asks 2-5 yrs",
  },
  {
    key: "location",
    label: "Location",
    weight: 5,
    points: 0,
    detail: "Job in Pune; not one of the candidate's locations",
  },
];

describe("ScoreComponents", () => {
  it("shows every part with points out of its weight, its reason and the total", () => {
    render(<ScoreComponents components={components} score={69} />);
    const table = screen.getByRole("table", { name: "How the score is calculated" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(5);
    expect(rows[0]).toHaveTextContent("31.4 / 50");
    expect(rows[1]).toHaveTextContent("8 of 10 required skills");
    expect(rows[3]).toHaveTextContent("0.0 / 5");
    expect(rows[4]).toHaveTextContent("Match score69 / 100");
  });

  it("renders nothing without components (old cached scores)", () => {
    const { container } = render(<ScoreComponents components={[]} score={50} />);
    expect(container).toBeEmptyDOMElement();
  });
});
