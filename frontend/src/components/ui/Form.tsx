import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { cn } from "@/lib/cn";

const control =
  "w-full rounded-md border bg-bg px-3 text-sm text-ink shadow-xs placeholder:text-ink-muted " +
  "transition-[border-color,box-shadow] duration-150 " +
  "focus:outline-none focus:ring-[3px] focus:ring-offset-0 " +
  "disabled:cursor-not-allowed disabled:bg-surface disabled:text-ink-secondary";

function borderFor(invalid?: boolean) {
  return invalid
    ? "border-status-red focus:border-status-red focus:ring-status-red/20"
    : "border-border hover:border-border-strong focus:border-accent focus:ring-accent/20";
}

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }
>(function Input({ className, invalid, ...props }, ref) {
  return (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(control, "h-9", borderFor(invalid), className)}
      {...props}
    />
  );
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }
>(function Textarea({ className, invalid, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(control, "py-2 leading-5", borderFor(invalid), className)}
      {...props}
    />
  );
});

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }
>(function Select({ className, invalid, children, ...props }, ref) {
  return (
    <select
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(control, "h-9 cursor-pointer pr-8", borderFor(invalid), className)}
      {...props}
    >
      {children}
    </select>
  );
});

export const Checkbox = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & { label?: ReactNode }
>(function Checkbox({ label, className, ...props }, ref) {
  const box = (
    <input
      ref={ref}
      type="checkbox"
      className={cn(
        "h-4 w-4 cursor-pointer rounded border-border accent-[rgb(var(--accent))]",
        !label && className,
      )}
      {...props}
    />
  );
  if (!label) return box;
  return (
    <label className={cn("inline-flex items-center gap-2 text-sm", className)}>
      {box}
      {label}
    </label>
  );
});

interface FieldProps {
  label: string;
  error?: string;
  hint?: string;
  children: (ids: { id: string; describedBy?: string; invalid: boolean }) => ReactNode;
  className?: string;
  optional?: boolean;
}

/** Label above the control, inline red error text below it. */
export function Field({ label, error, hint, children, className, optional }: FieldProps) {
  const id = useId();
  const errId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy =
    [error ? errId : null, hint ? hintId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink">
        {label}
        {optional && <span className="ml-1 font-normal text-ink-secondary">(optional)</span>}
      </label>
      {children({ id, describedBy, invalid: !!error })}
      {hint && !error && (
        <p id={hintId} className="mt-1 text-xs text-ink-secondary">
          {hint}
        </p>
      )}
      {error && (
        <p id={errId} role="alert" className="mt-1 text-xs text-status-red">
          {error}
        </p>
      )}
    </div>
  );
}

/** Bordered red banner for API errors at the top of a form. */
export function ErrorBanner({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="mb-4 rounded-md border border-status-red/30 bg-status-red-bg px-3 py-2.5 text-sm text-status-red"
    >
      {message}
    </div>
  );
}
