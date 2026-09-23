import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PulseCalendar from "./PulseCalendar";

const days = [
  { date: "2026-02-28", status: "actual", available_today: 100, used_today: 40, remaining_today: 60 },
  { date: "2026-03-01", status: "actual", available_today: 100, used_today: 120, remaining_today: -20 },
];

describe("PulseCalendar", () => {
  it("selects real cycle days and exposes non-color status labels", () => {
    const onSelect = vi.fn();
    render(<PulseCalendar days={days} selectedDate="2026-03-01" onSelect={onSelect} />);

    const selected = screen.getByRole("button", { name: /March 1, 2026, over allowance/i });
    expect(selected).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(selected);
    expect(onSelect).toHaveBeenCalledWith(days[1]);
  });

  it("navigates across a month boundary without selecting a day", () => {
    const onSelect = vi.fn();
    render(<PulseCalendar days={days} selectedDate="2026-03-01" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: "Previous month" }));
    expect(screen.getByText(/February 2026/i)).toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("groups numbered days into month-pulse weeks with dynamic totals", () => {
    render(<PulseCalendar days={days} selectedDate="2026-03-01" />);

    expect(screen.getByText("EGP 120")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /March 1, 2026/i })).toHaveTextContent("1");
  });

  it("removes financial values from accessible day labels while privacy mode is active", () => {
    render(<PulseCalendar days={days} selectedDate="2026-03-01" amountsHidden />);

    expect(screen.getByRole("button", { name: /March 1, 2026, over allowance, amounts hidden/i }))
      .toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /used EGP/i })).not.toBeInTheDocument();
  });
});
