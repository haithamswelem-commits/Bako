import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildPulseCategories } from "../utils/spendingPulse";
import SpendingAnalysis from "./SpendingAnalysis";

const analysis = {
  total_spent: 1000,
  by_category: [
    { category: "Food", amount: 100 },
    { category: "Home", amount: 480 },
    { category: "Savings", amount: 250 },
    { category: "Zero", amount: 0 },
    { category: "Travel", amount: 170 }
  ],
  by_subcategory: [
    {
      category: "Home",
      subcategory: "Building fees",
      amount: 480,
      percentage_of_category: 100
    }
  ]
};

describe("SpendingAnalysis", () => {
  it("renders one decorative Pulse Line with sorted accessible categories", () => {
    const { container } = render(<SpendingAnalysis analysis={analysis} cycleName="August" />);

    expect(screen.getByText("August")).toHaveClass("spending-pulse-cycle");
    expect(screen.getByText("Total Spent")).toBeInTheDocument();
    expect(container.querySelectorAll(".spending-pulse-connectors")).toHaveLength(1);
    expect(container.querySelector(".spending-pulse-connectors")).toHaveAttribute("aria-hidden", "true");
    expect(container.querySelectorAll(".spending-pulse-anchor")).toHaveLength(0);

    const categoryButtons = screen.getAllByRole("button");
    expect(categoryButtons[0]).toHaveAccessibleName(/Home, 48 percent, EGP\s+480\.00/i);
    expect(categoryButtons[1]).toHaveAccessibleName(/Savings, 25 percent, EGP\s+250\.00/i);
    expect(categoryButtons.some((button) => button.textContent.includes("Zero"))).toBe(false);
  });

  it("keeps the existing category drill-down behavior", () => {
    render(<SpendingAnalysis analysis={analysis} />);

    fireEvent.click(screen.getByRole("button", { name: /Home, 48 percent/i }));
    expect(screen.getByText("Building fees")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to categories" })).toBeInTheDocument();
  });

  it("aggregates small categories into a calculated Other item", () => {
    const categories = buildPulseCategories({
      total_spent: 100,
      by_category: [
        { category: "A", amount: 30 },
        { category: "B", amount: 20 },
        { category: "C", amount: 15 },
        { category: "D", amount: 10 },
        { category: "E", amount: 8 },
        { category: "F", amount: 7 },
        { category: "G", amount: 5 }
      ]
    });

    expect(categories).toHaveLength(6);
    expect(categories.at(-1)).toMatchObject({
      category: "Other",
      amount: 17,
      isAggregate: true
    });
    expect(categories.reduce((sum, item) => sum + item.percentage, 0)).toBe(100);
  });

  it("preserves an empty selected cycle state", () => {
    render(<SpendingAnalysis analysis={{ total_spent: 0, by_category: [] }} />);

    expect(screen.getByText("No spending data yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
