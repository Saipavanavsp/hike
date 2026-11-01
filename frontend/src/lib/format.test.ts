import { describe, expect, it } from "vitest";
import { formatExperience, formatSalaryRange, initials, relativeTime } from "./format";

describe("format helpers", () => {
  it("formats INR salary ranges in LPA", () => {
    expect(formatSalaryRange(1_200_000, 1_800_000)).toBe("₹12–18 LPA");
    expect(formatSalaryRange(850_000, 1_250_000)).toBe("₹8.5–12.5 LPA");
    expect(formatSalaryRange(1_000_000, 1_000_000)).toBe("₹10 LPA");
  });

  it("formats relative times", () => {
    const now = new Date("2026-11-01T12:00:00Z");
    expect(relativeTime("2026-11-01T11:59:50Z", now)).toBe("just now");
    expect(relativeTime("2026-11-01T11:00:00Z", now)).toBe("1h ago");
    expect(relativeTime("2026-10-29T12:00:00Z", now)).toBe("3d ago");
    expect(relativeTime("2026-10-18T12:00:00Z", now)).toBe("2w ago");
  });

  it("formats experience and initials", () => {
    expect(formatExperience(2, 5)).toBe("2–5 yrs");
    expect(formatExperience(0, 0)).toBe("Fresher");
    expect(initials("Nimbus Ledger")).toBe("NL");
    expect(initials("Quillstack")).toBe("Q");
  });
});
