import React, { useEffect } from "react";

export type ToastItem = {
  id: string;
  title: string;
  message: string;
};

export function ToastHost({
  toasts,
  onDismiss
}: {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}) {
  useEffect(() => {
    if (!toasts.length) return;
    const timers = toasts.map((t) =>
      window.setTimeout(() => {
        onDismiss(t.id);
      }, 5500)
    );
    return () => {
      timers.forEach((id) => window.clearTimeout(id));
    };
  }, [toasts, onDismiss]);

  if (!toasts.length) return null;

  return (
    <div className="toastWrap" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className="toast">
          <p className="toastTitle">{t.title}</p>
          <p className="toastBody">{t.message}</p>
        </div>
      ))}
    </div>
  );
}

