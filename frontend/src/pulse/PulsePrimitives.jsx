export function PulsePage({ children, className = "", direction = "ltr" }) {
  return (
    <main className={`pulse-page ${className}`.trim()} dir={direction}>
      {children}
    </main>
  );
}

export function PulseCard({ children, className = "", as: Component = "section" }) {
  return (
    <Component className={`pulse-card ${className}`.trim()}>
      {children}
    </Component>
  );
}

export function PulseButton({
  children,
  className = "",
  variant = "primary",
  type = "button",
  ...props
}) {
  return (
    <button
      className={`pulse-button pulse-button-${variant} ${className}`.trim()}
      type={type}
      {...props}
    >
      {children}
    </button>
  );
}

export function PulseField({ label, error = "", hint = "", children, className = "" }) {
  return (
    <label className={`pulse-field ${error ? "is-invalid" : ""} ${className}`.trim()}>
      <span>{label}</span>
      {children}
      {error ? <small role="alert">{error}</small> : hint ? <small>{hint}</small> : null}
    </label>
  );
}

export function PulseFinancialValue({
  amount,
  currency = "EGP",
  className = "",
}) {
  return (
    <span className={`pulse-financial-value ${className}`.trim()}>
      <span className="pulse-financial-amount">{amount}</span>
      <small className="pulse-financial-currency">{currency}</small>
    </span>
  );
}

export function PulseEmptyState({ title, children, action = null }) {
  return (
    <section className="pulse-empty-state">
      <strong>{title}</strong>
      {children && <p>{children}</p>}
      {action}
    </section>
  );
}

export function PulseLoadingState({ children = "Loading..." }) {
  return (
    <div className="pulse-loading-state" role="status" aria-live="polite">
      <i aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}

export function PulseErrorState({ title, children, action = null }) {
  return (
    <section className="pulse-error-state" role="alert">
      <span aria-hidden="true">!</span>
      <strong>{title}</strong>
      {children && <p>{children}</p>}
      {action}
    </section>
  );
}

export function PulseStatus({ children, tone = "neutral" }) {
  return (
    <span className={`pulse-status pulse-status-${tone}`}>
      <i aria-hidden="true" />
      {children}
    </span>
  );
}

export function PulseConfirmDialog({ request, onResolve }) {
  if (!request) return null;

  return (
    <div
      className="pulse-confirm-backdrop"
      role="presentation"
      onKeyDown={(event) => {
        if (event.key === "Escape") onResolve(false);
      }}
    >
      <section
        className="pulse-confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="pulse-confirm-title"
        aria-describedby="pulse-confirm-message"
      >
        <span className="pulse-confirm-kicker">Please confirm</span>
        <h2 id="pulse-confirm-title">{request.title || "Are you sure?"}</h2>
        <p id="pulse-confirm-message">{request.message}</p>
        <div className="pulse-confirm-actions">
          <button type="button" autoFocus onClick={() => onResolve(false)}>Keep it</button>
          <button type="button" className="is-danger" onClick={() => onResolve(true)}>
            {request.confirmLabel || "Delete"}
          </button>
        </div>
      </section>
    </div>
  );
}
