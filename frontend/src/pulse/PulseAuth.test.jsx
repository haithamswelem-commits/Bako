import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { VERIFIED_QURAN_VERSE } from "../data/verifiedQuranVerse";
import { BakoAuthPage, QuranStartupPage } from "./PulseAuth";

const baseAuthProps = {
  mode: "login",
  email: "",
  password: "",
  displayName: "",
  passwordVisible: false,
  loading: false,
  fieldErrors: {},
  statusMessage: "",
  statusTone: "error",
  generatedToken: "",
  resetToken: "",
  newPassword: "",
  onEmailChange: vi.fn(),
  onPasswordChange: vi.fn(),
  onDisplayNameChange: vi.fn(),
  onTogglePassword: vi.fn(),
  onLogin: vi.fn(),
  onRegister: vi.fn(),
  onOpenRegister: vi.fn(),
  onOpenRecovery: vi.fn(),
  onBackToLogin: vi.fn(),
  onRequestReset: vi.fn(),
  onResetTokenChange: vi.fn(),
  onNewPasswordChange: vi.fn(),
  onResetPassword: vi.fn(),
};

describe("BakoAuthPage", () => {
  it("renders the approved login copy and navigation actions", () => {
    const onOpenRegister = vi.fn();
    const onOpenRecovery = vi.fn();
    render(<BakoAuthPage {...baseAuthProps} onOpenRegister={onOpenRegister} onOpenRecovery={onOpenRecovery} />);

    expect(screen.getByRole("heading", { name: "READY WHEN YOU ARE" })).toBeInTheDocument();
    expect(screen.getByLabelText("EMAIL")).toBeInTheDocument();
    expect(screen.getByLabelText("PASSWORD")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "YOUR MONEY. ONE PLACE." })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "START HERE →" }));
    fireEvent.click(screen.getByRole("button", { name: "CAN'T SIGN IN?" }));
    expect(onOpenRegister).toHaveBeenCalledOnce();
    expect(onOpenRecovery).toHaveBeenCalledOnce();
  });

  it("associates errors and exposes an accessible password toggle", () => {
    const onTogglePassword = vi.fn();
    render(
      <BakoAuthPage
        {...baseAuthProps}
        fieldErrors={{ email: "Enter a valid email address." }}
        onTogglePassword={onTogglePassword}
      />
    );

    expect(screen.getByLabelText("EMAIL")).toHaveAttribute("aria-invalid", "true");
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(onTogglePassword).toHaveBeenCalledOnce();
  });
});

describe("QuranStartupPage", () => {
  const verse = VERIFIED_QURAN_VERSE.arabic;
  const translation = VERIFIED_QURAN_VERSE.translation;
  const citation = VERIFIED_QURAN_VERSE.citation;

  it("shows verified content without a continue action", () => {
    render(
      <QuranStartupPage arabicVerse={verse} translation={translation} citation={citation} onComplete={vi.fn()} />
    );

    expect(screen.getByText(verse)).toHaveAttribute("dir", "rtl");
    expect(screen.getByText(translation)).toBeInTheDocument();
    expect(screen.getByText(citation)).toBeInTheDocument();
    expect(screen.getByText("OPENING BAKO")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("completes once after five seconds and clears its timer on unmount", () => {
    vi.useFakeTimers();
    const onComplete = vi.fn();
    const { unmount } = render(
      <QuranStartupPage arabicVerse={verse} translation={translation} citation={citation} onComplete={onComplete} />
    );

    act(() => vi.advanceTimersByTime(4999));
    expect(onComplete).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(onComplete).toHaveBeenCalledOnce();

    unmount();
    act(() => vi.runOnlyPendingTimers());
    expect(onComplete).toHaveBeenCalledOnce();
    vi.useRealTimers();
  });
});
