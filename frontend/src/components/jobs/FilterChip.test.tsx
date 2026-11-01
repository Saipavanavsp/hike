import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { FilterChip } from "./FilterChip";
import { LOCATION_OPTIONS } from "./options";

function Harness({
  multiple = true,
  onChange,
}: {
  multiple?: boolean;
  onChange?: (v: string[]) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  return (
    <FilterChip
      label="Location"
      options={LOCATION_OPTIONS}
      selected={selected}
      multiple={multiple}
      onChange={(v) => {
        setSelected(v);
        onChange?.(v);
      }}
    />
  );
}

describe("FilterChip", () => {
  it("opens a list of options and selects several values", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);

    const chip = screen.getByRole("button", { name: /^Location/ });
    expect(chip).toHaveAttribute("aria-expanded", "false");
    await user.click(chip);
    expect(chip).toHaveAttribute("aria-expanded", "true");

    await user.click(screen.getByRole("checkbox", { name: "Pune" }));
    await user.click(screen.getByRole("checkbox", { name: "Remote" }));
    expect(onChange).toHaveBeenLastCalledWith(["Pune", "Remote"]);
    expect(screen.getByText(": Pune, Remote")).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Pune" }));
    expect(onChange).toHaveBeenLastCalledWith(["Remote"]);
  });

  it("clears with the x button", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /^Location/ }));
    await user.click(screen.getByRole("checkbox", { name: "Chennai" }));
    await user.click(screen.getByRole("button", { name: "Clear Location filter" }));
    expect(onChange).toHaveBeenLastCalledWith([]);
    expect(screen.queryByRole("button", { name: "Clear Location filter" })).not.toBeInTheDocument();
  });

  it("single-select mode replaces the value and closes", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness multiple={false} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /^Location/ }));
    await user.click(screen.getByRole("radio", { name: "Hyderabad" }));
    expect(onChange).toHaveBeenLastCalledWith(["Hyderabad"]);
    expect(screen.queryByRole("radio", { name: "Pune" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^Location/ }));
    await user.click(screen.getByRole("radio", { name: "Pune" }));
    expect(onChange).toHaveBeenLastCalledWith(["Pune"]);
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole("button", { name: /^Location/ }));
    expect(screen.getByRole("group", { name: "Location options" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("group", { name: "Location options" })).not.toBeInTheDocument();
  });
});
