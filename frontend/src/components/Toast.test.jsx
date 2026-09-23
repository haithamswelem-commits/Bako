import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Toast from "./Toast";

describe("Toast", () => {
  it("renders success notifications as a polite status", () => {
    render(<Toast message="Expense updated" />);

    const toast = screen.getByRole("status");
    expect(toast).toHaveClass("pulse-toast", "toast-success");
    expect(toast).toHaveTextContent("Expense updated");
  });

  it("renders error notifications as assertive alerts", () => {
    render(<Toast message="Update failed" type="error" />);

    const toast = screen.getByRole("alert");
    expect(toast).toHaveClass("toast-error");
    expect(toast).toHaveAttribute("aria-live", "assertive");
  });

  it("falls back to the information style for unknown types", () => {
    render(<Toast message="Something changed" type="unknown" />);

    expect(screen.getByRole("status")).toHaveClass("toast-info");
  });
});
