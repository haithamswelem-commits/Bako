function Button({ children, onClick, disabled = false, type = "button", variant = "accent" }) {
  return (
    <button
      type={type}
      className={`primary-button pulse-button pulse-button-${variant}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

export default Button;
