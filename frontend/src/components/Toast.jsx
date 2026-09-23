import { CircleAlert, CircleCheck, Info, TriangleAlert } from "lucide-react";

const TOAST_ICONS = {
  success: CircleCheck,
  error: CircleAlert,
  warning: TriangleAlert,
  info: Info,
};

function Toast({
  message,
  type = "success"
}) {
  const toastType = TOAST_ICONS[type] ? type : "info";
  const ToastIcon = TOAST_ICONS[toastType];

  return (
    <div
      className={`toast pulse-toast toast-${toastType}`}
      role={toastType === "error" ? "alert" : "status"}
      aria-live={toastType === "error" ? "assertive" : "polite"}
    >
      <span className="pulse-toast-icon" aria-hidden="true">
        <ToastIcon size={15} strokeWidth={2.4} />
      </span>
      <span className="pulse-toast-message">{message}</span>
    </div>
  );
}

export default Toast;
