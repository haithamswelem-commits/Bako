import { useEffect, useId, useRef } from "react";
import { ArrowLeft, ArrowRight, X } from "lucide-react";

function Modal({
  isOpen,
  onClose,
  title,
  subtitle = "",
  direction = "ltr",
  variant = "",
  children
}) {
  const isModernPage = variant === "modern-page";
  const BackArrow = direction === "rtl" ? ArrowRight : ArrowLeft;
  const titleId = useId();
  const dialogRef = useRef(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) return undefined;

    const previousActiveElement = document.activeElement;
    const handleKeyDown = (event) => {
      if (event.key === "Escape") onCloseRef.current();
    };

    document.addEventListener("keydown", handleKeyDown);
    dialogRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previousActiveElement?.focus?.();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      className="modal-backdrop pulse-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        className={`modal-panel pulse-modal ${variant ? `modal-panel-${variant}` : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={variant === "headerless" ? undefined : titleId}
        aria-label={variant === "headerless" ? title : undefined}
        tabIndex={-1}
        dir={direction}
      >
        {isModernPage ? (
          <div className="modal-modern-header pulse-modal-header">
            <button
              onClick={onClose}
              className="modal-modern-back"
              aria-label="Go back"
            >
              <BackArrow size={19} />
            </button>
            <div>
              <h2 id={titleId}>{title}</h2>
              {subtitle && <p>{subtitle}</p>}
            </div>
          </div>
        ) : variant === "headerless" ? (
          <button
            onClick={onClose}
            className="modal-close-button modal-floating-close"
            aria-label="Close modal"
          >
            <X size={20} />
          </button>
        ) : (
          <div className="modal-header pulse-modal-header">
            <h2 id={titleId}>{title}</h2>

            <button
              onClick={onClose}
              className="modal-close-button"
              aria-label="Close modal"
            >
              <X size={20} />
            </button>
          </div>
        )}

        <div className="modal-body pulse-modal-body">{children}</div>
      </div>
    </div>
  );
}

export default Modal;
