import { Check, X } from "lucide-react";
import { useToast } from "@/stores/toast";
import { icon } from "./icon";

export function Toaster() {
  const { toasts, dismiss } = useToast();
  return (
    <div
      aria-live="polite"
      className="fixed bottom-16 right-4 z-50 flex flex-col gap-2 md:bottom-4"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          className="flex items-center gap-2 rounded border border-border bg-ink px-3 py-2 text-sm text-white shadow-overlay"
        >
          <Check {...icon} className="text-[#5EEAD4]" />
          <span>{t.message}</span>
          <button
            aria-label="Dismiss"
            onClick={() => dismiss(t.id)}
            className="ml-2 text-white/70 hover:text-white"
          >
            <X {...icon} size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
