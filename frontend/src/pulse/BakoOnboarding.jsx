import { useEffect, useRef, useState } from "react";

import { PulsePage } from "./PulsePrimitives";

const LAST_PAGE_INDEX = 2;

export function BakoOnboarding({ displayName, onDisplayNameChange, onBack, onComplete }) {
  const [pageIndex, setPageIndex] = useState(0);
  const [direction, setDirection] = useState("next");
  const touchStartX = useRef(null);
  const cleanName = displayName.trim();
  const greetingName = cleanName || "there";

  const showPage = (nextPage) => {
    const boundedPage = Math.max(0, Math.min(LAST_PAGE_INDEX, nextPage));
    if (boundedPage === pageIndex) return;
    setDirection(boundedPage > pageIndex ? "next" : "back");
    setPageIndex(boundedPage);
  };

  const handleNext = () => {
    if (pageIndex === 0 && !cleanName) return;
    if (pageIndex === LAST_PAGE_INDEX) {
      onComplete();
      return;
    }
    showPage(pageIndex + 1);
  };

  const handleBack = () => {
    if (pageIndex === 0) {
      onBack();
      return;
    }
    showPage(pageIndex - 1);
  };

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "ArrowLeft") handleBack();
      if (event.key === "ArrowRight") handleNext();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  const handleTouchStart = (event) => {
    touchStartX.current = event.changedTouches[0]?.clientX ?? null;
  };

  const handleTouchEnd = (event) => {
    if (touchStartX.current === null) return;
    const distance = (event.changedTouches[0]?.clientX ?? touchStartX.current) - touchStartX.current;
    touchStartX.current = null;
    if (Math.abs(distance) < 48) return;
    if (distance < 0) handleNext();
    else handleBack();
  };

  return (
    <PulsePage className="bako-onboarding-page">
      <section
        className={`bako-onboarding-shell is-${direction}`}
        aria-label="Welcome to Bako"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        <header className="bako-onboarding-header">
          <span>BAKO</span>
          <span aria-live="polite">0{pageIndex + 1} / 03</span>
        </header>

        <div className="bako-onboarding-stage" key={pageIndex}>
          {pageIndex === 0 && (
            <section className="bako-onboarding-panel bako-onboarding-panel-one" aria-labelledby="bako-onboarding-title-one">
              <picture className="bako-onboarding-ctrl-art">
                <img src="/bako-onboarding-ctrl.png" alt="A black CTRL keyboard key with a pulse-green label" />
              </picture>
              <h1 id="bako-onboarding-title-one">Money<br /><span>under</span></h1>
              <p className="bako-onboarding-topics">
                <small>Your</small>
                <strong>Spending.</strong>
                <strong>Goals.</strong>
                <strong>Daily guide.</strong>
                <em>Made clear.</em>
              </p>
              <label className="bako-onboarding-name" htmlFor="bako-onboarding-name">
                <span>Let’s start with your name.</span>
                <input
                  id="bako-onboarding-name"
                  type="text"
                  value={displayName}
                  maxLength={100}
                  autoComplete="name"
                  autoFocus
                  onChange={(event) => onDisplayNameChange(event.target.value)}
                />
              </label>
            </section>
          )}

          {pageIndex === 1 && (
            <section className="bako-onboarding-panel bako-onboarding-panel-two" aria-labelledby="bako-onboarding-title-two">
              <p className="bako-onboarding-greeting">Hi, {greetingName}.</p>
              <h1 id="bako-onboarding-title-two">Your money,<br /><em>on track.</em></h1>
              <picture className="bako-onboarding-maze-art">
                <img src="/bako-onboarding-maze.png" alt="A black maze with one clear pulse-green path" />
              </picture>
              <p className="bako-onboarding-guide">
                Bako turns what you spend into a simple daily guide with
                <strong>less noise</strong>
              </p>
            </section>
          )}

          {pageIndex === 2 && (
            <section className="bako-onboarding-panel bako-onboarding-panel-three" aria-labelledby="bako-onboarding-title-three">
              <h1 id="bako-onboarding-title-three">See it.<br />Plan it.<br /><em>Invest it.</em></h1>
              <picture className="bako-onboarding-brain-art">
                <img src="/bako-onboarding-brain.png" alt="A black brain with pulse-green thinking points" />
              </picture>
              <div className="bako-onboarding-feature is-left">
                <i aria-hidden="true" />
                <strong>Ask Bako</strong>
                <span>Clear answers<br />from<br />your<br />money.</span>
              </div>
              <div className="bako-onboarding-feature is-right">
                <i aria-hidden="true" />
                <strong>Your list</strong>
                <span>Your names.<br />Your way.</span>
              </div>
              <p className="bako-onboarding-decision"><small>Bako explains</small><strong>You decide.</strong></p>
            </section>
          )}
        </div>

        <footer className="bako-onboarding-footer">
          <button type="button" className="bako-onboarding-back" aria-label="Previous page" onClick={handleBack}>←</button>
          <span className="bako-onboarding-dots" aria-hidden="true">
            {[0, 1, 2].map((dotIndex) => <i className={dotIndex === pageIndex ? "is-active" : ""} key={dotIndex} />)}
          </span>
          <button
            type="button"
            className="bako-onboarding-next"
            aria-label={pageIndex === LAST_PAGE_INDEX ? "Continue to account setup" : "Next page"}
            disabled={pageIndex === 0 && !cleanName}
            onClick={handleNext}
          >
            {pageIndex === LAST_PAGE_INDEX && <span>LET’S START</span>}
            <b aria-hidden="true">→</b>
          </button>
        </footer>
      </section>
    </PulsePage>
  );
}
