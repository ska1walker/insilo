"use client";

import { X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

type ToastVariant = "info" | "success" | "error" | "undo";

type ToastConfig = {
  message: string;
  variant?: ToastVariant;
  /** ms before auto-dismiss. `0` keeps the toast pinned until manual dismiss. */
  duration?: number;
  action?: { label: string; onClick: () => void };
  /** Fires when the toast auto-dismisses (not when user clicks action / closes). */
  onTimeout?: () => void;
};

type ToastEntry = ToastConfig & {
  id: string;
  createdAt: number;
  // Resolved values to remove `undefined` paranoia at render time.
  variant: ToastVariant;
  duration: number;
};

type ToastContextValue = {
  show: (cfg: ToastConfig) => string;
  dismiss: (id: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const DEFAULT_DURATION: Record<ToastVariant, number> = {
  info: 4000,
  success: 4000,
  error: 6000,
  undo: 5000,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = useCallback((cfg: ToastConfig) => {
    const id =
      Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    const variant = cfg.variant ?? "info";
    const duration = cfg.duration ?? DEFAULT_DURATION[variant];
    setToasts((prev) => [
      ...prev,
      {
        ...cfg,
        id,
        variant,
        duration,
        createdAt: Date.now(),
      },
    ]);
    return id;
  }, []);

  return (
    <ToastContext.Provider value={{ show, dismiss }}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within <ToastProvider>");
  }
  return ctx;
}

// ─── Viewport ──────────────────────────────────────────────────────────

function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: ToastEntry[];
  onDismiss: (id: string) => void;
}) {
  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 px-4 pb-6 sm:bottom-4 sm:items-end sm:px-6"
    >
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

// ─── Single toast card ─────────────────────────────────────────────────

function ToastCard({
  toast,
  onDismiss,
}: {
  toast: ToastEntry;
  onDismiss: (id: string) => void;
}) {
  const [leaving, setLeaving] = useState(false);
  const actionFiredRef = useRef(false);

  // Timer for auto-dismiss.
  useEffect(() => {
    if (toast.duration <= 0) return;
    const t = setTimeout(() => {
      if (!actionFiredRef.current) {
        toast.onTimeout?.();
      }
      setLeaving(true);
      // Allow exit transition before unmount.
      setTimeout(() => onDismiss(toast.id), 200);
    }, toast.duration);
    return () => clearTimeout(t);
  }, [toast.duration, toast.id, toast.onTimeout, onDismiss]);

  function handleAction() {
    actionFiredRef.current = true;
    toast.action?.onClick();
    setLeaving(true);
    setTimeout(() => onDismiss(toast.id), 200);
  }

  function handleClose() {
    actionFiredRef.current = true; // Suppress onTimeout for manual close
    setLeaving(true);
    setTimeout(() => onDismiss(toast.id), 200);
  }

  const accentColor =
    toast.variant === "error"
      ? "var(--error)"
      : toast.variant === "success"
        ? "var(--success)"
        : toast.variant === "undo"
          ? "var(--gold-deep)"
          : "var(--text-primary)";

  return (
    <div
      role={toast.variant === "error" ? "alert" : "status"}
      className="pointer-events-auto w-full max-w-[480px] origin-bottom transition-all duration-200 ease-out"
      style={{
        opacity: leaving ? 0 : 1,
        transform: leaving ? "translateY(8px)" : "translateY(0)",
        animation: leaving ? undefined : "toastIn 220ms ease-out",
      }}
    >
      <div
        className="relative overflow-hidden rounded-lg border bg-white"
        style={{
          borderColor: "var(--border-subtle)",
          boxShadow: "0 8px 24px rgba(10, 10, 10, 0.08)",
        }}
      >
        {/* Left accent bar */}
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 w-[3px]"
          style={{ background: accentColor }}
        />

        <div className="flex items-start gap-3 py-3 pl-5 pr-3">
          <p className="flex-1 text-sm leading-snug text-text-primary">
            {toast.message}
          </p>
          {toast.action && (
            <button
              type="button"
              onClick={handleAction}
              className="btn-tertiary -my-1 shrink-0"
              style={{
                color: accentColor,
                fontWeight: 500,
              }}
            >
              {toast.action.label}
            </button>
          )}
          <button
            type="button"
            onClick={handleClose}
            className="-my-1 -mr-1 shrink-0 rounded p-1.5 text-text-meta hover:bg-surface-soft hover:text-text-primary"
            aria-label="Schließen"
          >
            <X className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
        </div>

        {/* Countdown bar at the bottom — only when there's a chance to undo. */}
        {toast.variant === "undo" && toast.duration > 0 && (
          <span
            aria-hidden
            className="absolute inset-x-0 bottom-0 h-[2px]"
            style={{
              background: "var(--gold-deep)",
              transformOrigin: "left",
              animation: `toastCountdown ${toast.duration}ms linear forwards`,
            }}
          />
        )}
      </div>

      <style>{`
        @keyframes toastIn {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes toastCountdown {
          from { transform: scaleX(1); }
          to   { transform: scaleX(0); }
        }
      `}</style>
    </div>
  );
}
