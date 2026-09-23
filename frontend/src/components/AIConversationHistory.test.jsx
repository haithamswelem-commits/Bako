import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import AIConversationHistory from "./AIConversationHistory";

const exchange = {
  id: 7,
  question: "How is my budget pace?",
  headline: "Your pace is safe",
  explanation: "You are within your verified daily allowance.",
  recommended_action: "Keep daily spending within the current allowance.",
  created_at: "2026-08-27T10:00:00Z",
};

describe("AIConversationHistory", () => {
  it("opens a stored answer without invoking a model callback", () => {
    const onSelect = vi.fn();
    const onAsk = vi.fn();
    const { rerender } = render(
      <AIConversationHistory exchanges={[exchange]} onSelect={onSelect} onBack={vi.fn()} onAsk={onAsk} />
    );

    fireEvent.click(screen.getByRole("button", { name: /How is my budget pace/i }));
    expect(onSelect).toHaveBeenCalledWith(7);
    expect(onAsk).not.toHaveBeenCalled();

    rerender(<AIConversationHistory exchanges={[exchange]} selectedId={7} onSelect={onSelect} onBack={vi.fn()} onAsk={onAsk} />);
    expect(screen.getByText("You are within your verified daily allowance.")).toBeInTheDocument();
    expect(screen.getByText(/Read only/i)).toBeInTheDocument();
    expect(onAsk).not.toHaveBeenCalled();
  });
});
