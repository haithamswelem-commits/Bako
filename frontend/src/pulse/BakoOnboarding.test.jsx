import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BakoOnboarding } from "./BakoOnboarding";

function OnboardingHarness({ onBack = vi.fn(), onComplete = vi.fn() }) {
  const [displayName, setDisplayName] = useState("");
  return (
    <BakoOnboarding
      displayName={displayName}
      onDisplayNameChange={setDisplayName}
      onBack={onBack}
      onComplete={onComplete}
    />
  );
}

describe("BakoOnboarding", () => {
  it("asks for a name before moving to the personalized greeting", () => {
    render(<OnboardingHarness />);

    const nextButton = screen.getByRole("button", { name: "Next page" });
    expect(screen.getByLabelText("Let’s start with your name.")).toBeInTheDocument();
    expect(nextButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Let’s start with your name."), { target: { value: "Mariam" } });
    expect(nextButton).toBeEnabled();
    fireEvent.click(nextButton);

    expect(screen.getByText("Hi, Mariam.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Your money, on track." })).toBeInTheDocument();
  });

  it("completes after the approved third page", () => {
    const onComplete = vi.fn();
    render(<OnboardingHarness onComplete={onComplete} />);

    fireEvent.change(screen.getByLabelText("Let’s start with your name."), { target: { value: "Haitham" } });
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));

    expect(screen.getByRole("heading", { name: "See it. Plan it. Invest it." })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continue to account setup" }));
    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("returns to login from the first page", () => {
    const onBack = vi.fn();
    render(<OnboardingHarness onBack={onBack} />);

    fireEvent.click(screen.getByRole("button", { name: "Previous page" }));
    expect(onBack).toHaveBeenCalledOnce();
  });
});
