import { Check, X } from "lucide-react";
import { useToast } from "@/stores/toast";
import { icon } from "./icon";

export function Toaster() {
  const { toasts, dismiss } = useToast();
  return (
    <div
      aria-live="polite"
      className="fixed bottom-20 right-4 z-[60] flex flex-col gap-2 md:bottom-5 md:right-5"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          className="flex min-w-[260px] max-w-sm animate-slide-in-right items-center gap-3 rounded-lg border border-border bg-bg py-2.5 pl-3 pr-2 text-sm text-ink shadow-overlay"
        >
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-status-green-bg text-status-green">
            <Check {...icon} size={14} />
          </span>
          <span className="flex-1 font-medium">{t.message}</span>
          <button
            aria-label="Dismiss"
            onClick={() => dismiss(t.id)}
            className="flex h-7 w-7 items-center justify-center rounded-md text-ink-secondary transition-colors hover:bg-surface hover:text-ink"
          >
            <X {...icon} size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
