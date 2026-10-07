/** Small set of shared, accessible UI primitives (Tailwind). */
import {
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";
import { useTranslation } from "react-i18next";

import { cx } from "@/lib/cx";
import { useErrorMessage } from "@/lib/hooks";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-leaf-700 text-white hover:bg-leaf-600 disabled:bg-leaf-700/50",
  secondary: "border border-bark-100 bg-white text-bark-900 hover:bg-bark-50",
  danger: "bg-red-700 text-white hover:bg-red-600 disabled:bg-red-700/50",
  ghost: "text-bark-700 hover:bg-bark-100",
};

export function Button({
  variant = "primary",
  className = "",
  busy = false,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean }) {
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      disabled={busy || props.disabled}
      {...props}
    >
      {busy && <Spinner className="size-3.5" />}
      {children}
    </button>
  );
}

export function Spinner({ className = "size-5" }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="loading"
      className={`inline-block animate-spin rounded-full border-2 border-current border-t-transparent ${className}`}
    />
  );
}

interface FieldProps {
  label: string;
  hint?: ReactNode;
  children: (id: string) => ReactNode;
}

export function Field({ label, hint, children }: FieldProps) {
  const id = useId();
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-bark-900 block text-sm font-medium">
        {label}
      </label>
      {children(id)}
      {hint && <p className="text-bark-700 text-xs">{hint}</p>}
    </div>
  );
}

const inputClass =
  "block w-full rounded-md border border-bark-100 bg-white px-3 py-2 text-sm shadow-sm focus:border-leaf-600 focus:ring-1 focus:ring-leaf-600 focus:outline-none";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(inputClass, props.className)} />;
}

export function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx(inputClass, props.className)} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(inputClass, props.className)} />;
}

export function Checkbox({
  label,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" className="border-bark-100 size-4 rounded" {...props} />
      {label}
    </label>
  );
}

export function Alert({
  kind = "error",
  children,
}: {
  kind?: "error" | "success" | "info";
  children: ReactNode;
}) {
  const styles = {
    error: "border-red-200 bg-red-50 text-red-800",
    success: "border-green-200 bg-green-50 text-green-800",
    info: "border-bark-100 bg-bark-100/40 text-bark-900",
  };
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={`rounded-md border px-3 py-2 text-sm ${styles[kind]}`}
    >
      {children}
    </div>
  );
}

export function ErrorAlert({ error }: { error: unknown }) {
  const message = useErrorMessage();
  if (!error) return null;
  return <Alert>{message(error)}</Alert>;
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "green" | "red" | "amber";
}) {
  const tones = {
    neutral: "bg-bark-100 text-bark-700",
    green: "bg-green-100 text-green-800",
    red: "bg-red-100 text-red-800",
    amber: "bg-amber-100 text-amber-800",
  };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function PageHeader({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <h1 className="font-serif text-2xl font-semibold">{title}</h1>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`border-bark-100 rounded-lg border bg-white p-4 shadow-sm ${className}`}>
      {children}
    </section>
  );
}

/** Modal dialog based on the native <dialog> element (focus trap and Esc handling built in). */
export function Dialog({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) {
      // Fallback for environments without the modal API (older browsers, jsdom).
      if (typeof el.showModal === "function") el.showModal();
      else el.setAttribute("open", "");
    }
    if (!open && el.open) el.close?.();
  }, [open]);
  if (!open) return null;
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-label={title}
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-lg p-0 shadow-xl backdrop:bg-black/40"
    >
      <div className="border-bark-100 flex items-center justify-between border-b px-4 py-3">
        <h2 className="font-semibold">{title}</h2>
        <button
          type="button"
          onClick={onClose}
          className="text-bark-700 hover:text-bark-900"
          aria-label="×"
        >
          ×
        </button>
      </div>
      <div className="p-4">{children}</div>
    </dialog>
  );
}

/** Read-only field with a copy button, for invitation / reset links. */
export function CopyField({ value }: { value: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex gap-2">
      <Input
        readOnly
        value={value}
        onFocus={(e) => e.currentTarget.select()}
        aria-label={t("common.link")}
      />
      <Button
        variant="secondary"
        onClick={() => {
          void navigator.clipboard?.writeText(value).then(() => setCopied(true));
        }}
      >
        {copied ? t("common.copied") : t("common.copy")}
      </Button>
    </div>
  );
}
