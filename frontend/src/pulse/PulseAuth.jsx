import { useEffect, useRef } from "react";
import { Eye, EyeOff } from "lucide-react";

import { PulsePage } from "./PulsePrimitives";

export function BakoBrandLockup() {
  return (
    <div className="bako-brand-lockup">
      <img
        src="/bako-lockup-slogan.png"
        alt="Bako - Keep your money together"
        loading="eager"
        decoding="async"
      />
    </div>
  );
}

export function PulseInput({ id, label, error = "", trailingAction = null, ...inputProps }) {
  const errorId = `${id}-error`;
  return (
    <div className={`pulse-auth-field${error ? " is-invalid" : ""}`}>
      <label htmlFor={id}>{label}</label>
      <div className="pulse-auth-input-wrap">
        <input id={id} aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined} {...inputProps} />
        {trailingAction}
      </div>
      {error && <p className="pulse-auth-field-error" id={errorId} role="alert">{error}</p>}
    </div>
  );
}

export function PulseButton({ children, loading = false, ...buttonProps }) {
  return (
    <button className="pulse-auth-primary" {...buttonProps}>
      <span>{loading ? "PLEASE WAIT" : children}</span>
      <span className="pulse-auth-button-arrow" aria-hidden="true">→</span>
    </button>
  );
}

export function BakoAuthPage({
  mode, email, password, displayName, passwordVisible, loading, fieldErrors,
  statusMessage, statusTone, generatedToken, resetToken, newPassword,
  onEmailChange, onPasswordChange, onDisplayNameChange, onTogglePassword,
  onLogin, onRegister, onOpenRegister, onOpenRecovery, onBackToLogin,
  onRequestReset, onResetTokenChange, onNewPasswordChange, onResetPassword,
}) {
  const isRegister = mode === "register";
  const isRecovery = mode === "recovery";
  const formTitle = isRecovery ? "CAN'T SIGN IN?" : isRegister ? "CREATE YOUR BAKO" : "READY WHEN YOU ARE";
  const handleSubmit = (event) => {
    event.preventDefault();
    if (isRecovery) {
      if (generatedToken) onResetPassword();
      else onRequestReset();
    } else if (isRegister) onRegister();
    else onLogin();
  };

  return (
    <PulsePage className="bako-auth-page">
      <section className="bako-auth-content" aria-labelledby="bako-auth-title">
        <BakoBrandLockup />
        <form className="bako-auth-form" noValidate onSubmit={handleSubmit}>
          <h1 id="bako-auth-title">{formTitle}</h1>
          {isRecovery && <p className="bako-auth-intro">Enter your email to create a password reset token.</p>}
          {isRegister && (
            <PulseInput id="auth-name" label="NAME" type="text" autoComplete="name" value={displayName}
              maxLength={100} error={fieldErrors.displayName} onChange={onDisplayNameChange} />
          )}
          <PulseInput id="auth-email" label="EMAIL" type="email" inputMode="email" autoComplete="email"
            value={email} error={fieldErrors.email} onChange={onEmailChange} />
          {!isRecovery && (
            <PulseInput id="auth-password" label="PASSWORD" type={passwordVisible ? "text" : "password"}
              autoComplete={isRegister ? "new-password" : "current-password"} value={password}
              error={fieldErrors.password} onChange={onPasswordChange}
              trailingAction={(
                <button className="pulse-password-toggle" type="button"
                  aria-label={passwordVisible ? "Hide password" : "Show password"}
                  aria-pressed={passwordVisible} onClick={onTogglePassword}>
                  {passwordVisible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
                </button>
              )} />
          )}
          {isRecovery && generatedToken && (
            <>
              <PulseInput id="auth-reset-token" label="RESET TOKEN" type="text" autoComplete="one-time-code"
                value={resetToken} error={fieldErrors.resetToken} onChange={onResetTokenChange} />
              <PulseInput id="auth-new-password" label="NEW PASSWORD" type="password" autoComplete="new-password"
                value={newPassword} error={fieldErrors.newPassword} onChange={onNewPasswordChange} />
              <p className="pulse-development-token">Development token: <strong>{generatedToken}</strong></p>
            </>
          )}
          {statusMessage && (
            <p className={`pulse-auth-status is-${statusTone || "error"}`}
              role={statusTone === "success" ? "status" : "alert"}>{statusMessage}</p>
          )}
          <PulseButton type="submit" disabled={loading} loading={loading}>
            {isRecovery ? generatedToken ? "RESET PASSWORD" : "SEND RESET TOKEN" : isRegister ? "CREATE ACCOUNT" : "LOG IN"}
          </PulseButton>
        </form>
        {!isRecovery && !isRegister && (
          <section className="bako-new-user" aria-labelledby="bako-new-user-title">
            <span>NO BAKO YET?</span>
            <h2 id="bako-new-user-title">YOUR MONEY.<br />ONE PLACE.</h2>
            <button type="button" onClick={onOpenRegister}>START HERE →</button>
          </section>
        )}
        <nav className="bako-auth-navigation" aria-label="Authentication options">
          {isRecovery || isRegister
            ? <button type="button" onClick={onBackToLogin}>← BACK TO LOG IN</button>
            : <button type="button" onClick={onOpenRecovery}>CAN'T SIGN IN?</button>}
        </nav>
      </section>
    </PulsePage>
  );
}

export function PulseLoadingBar() {
  return <div className="pulse-opening-track" aria-hidden="true"><span /></div>;
}

export function QuranVersePanel({ arabicVerse, translation, citation }) {
  return (
    <section className="quran-verse-panel">
      <p className="quran-verse-arabic" lang="ar" dir="rtl">{arabicVerse}</p>
      <span className="quran-verse-divider" aria-hidden="true" />
      <blockquote className="quran-verse-translation">{translation}</blockquote>
      <cite>{citation}</cite>
    </section>
  );
}

export function QuranStartupPage({ arabicVerse, translation, citation, durationMs = 5000, onComplete }) {
  const onCompleteRef = useRef(onComplete);
  useEffect(() => { onCompleteRef.current = onComplete; }, [onComplete]);
  useEffect(() => {
    let completed = false;
    const timerId = window.setTimeout(() => {
      if (completed) return;
      completed = true;
      onCompleteRef.current?.();
    }, durationMs);
    return () => {
      completed = true;
      window.clearTimeout(timerId);
    };
  }, [durationMs]);

  return (
    <PulsePage className="quran-startup-page">
      <section className="quran-startup-content" aria-labelledby="quran-startup-title">
        <header className="quran-startup-header">
          <div className="quran-startup-icon" aria-hidden="true">
            <img src="/bako-icon.png" alt="" />
          </div>
          <h1 id="quran-startup-title">A MOMENT TO BEGIN</h1>
        </header>
        <QuranVersePanel arabicVerse={arabicVerse} translation={translation} citation={citation} />
        <footer className="quran-startup-footer">
          <p role="status" aria-live="polite">OPENING BAKO</p>
          <PulseLoadingBar />
        </footer>
      </section>
    </PulsePage>
  );
}
