import { useMemo, useState } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { PulseButton, PulseEmptyState } from "../pulse/PulsePrimitives";

const PAGE_SIZE = 20;

export default function AIConversationHistory({
  exchanges = [],
  selectedId = null,
  onSelect,
  onBack,
  language = "en",
}) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const selected = useMemo(
    () => exchanges.find((exchange) => exchange.id === selectedId),
    [exchanges, selectedId]
  );
  const locale = language === "ar" ? "ar-EG" : "en-US";
  const BackArrow = language === "ar" ? ArrowRight : ArrowLeft;

  if (selected) {
    return (
      <section className="ai-history-detail">
        <PulseButton className="pulse-black-action is-back" variant="secondary" onClick={() => onSelect?.(null)}>
          <BackArrow className="pulse-black-action-arrow" size={17} /> Back to history
        </PulseButton>
        <time>{selected.created_at ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(selected.created_at)) : ""}</time>
        <h3>{selected.question}</h3>
        {selected.headline && <strong>{selected.headline}</strong>}
        <p>{selected.explanation}</p>
        {selected.recommended_action && (
          <aside>
            <span>Saved recommendation</span>
            <p>{selected.recommended_action}</p>
            <small>Read only. Ask Bako again to recalculate using current data.</small>
          </aside>
        )}
      </section>
    );
  }

  return (
    <section className="ai-history-list">
      <header>
        <div><span>Previous questions</span><h3>History</h3></div>
        <PulseButton className="pulse-black-action is-back" variant="secondary" onClick={onBack}>
          <BackArrow className="pulse-black-action-arrow" size={17} /> Back to chat
        </PulseButton>
      </header>
      {exchanges.length === 0 ? (
        <PulseEmptyState title="No previous questions">Your saved Bako conversations will appear here.</PulseEmptyState>
      ) : (
        <>
          <div>
            {exchanges.slice(0, visibleCount).map((exchange) => (
              <button type="button" key={exchange.id} onClick={() => onSelect?.(exchange.id)}>
                <span>{exchange.question}</span>
                <time>{exchange.created_at ? new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(exchange.created_at)) : ""}</time>
              </button>
            ))}
          </div>
          {visibleCount < exchanges.length && (
            <PulseButton variant="secondary" onClick={() => setVisibleCount((count) => count + PAGE_SIZE)}>Load more</PulseButton>
          )}
        </>
      )}
    </section>
  );
}
