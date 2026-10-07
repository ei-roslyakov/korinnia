import { useCallback, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { ToastContext, type ToastKind } from "@/lib/toast";

const DURATION_MS = 4000;
const STYLE: Record<ToastKind, string> = {
  success: "border-green-200 bg-green-50 text-green-800",
  info: "border-bark-100 bg-surface text-bark-900",
  error: "border-red-200 bg-red-50 text-red-800",
};
const ICON: Record<ToastKind, string> = { success: "✓", info: "ℹ", error: "!" };

interface Item {
  id: number;
  message: string;
  kind: ToastKind;
}

let nextId = 1;

/** Toasts for the whole app: announced politely to screen readers, gone after 4 s. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const show = useCallback((message: string, kind: ToastKind = "success") => {
    const id = nextId++;
    setItems((list) => [...list.slice(-2), { id, message, kind }]);
    setTimeout(() => setItems((list) => list.filter((i) => i.id !== id)), DURATION_MS);
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      {createPortal(
        <div
          role="status"
          aria-live="polite"
          className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4"
        >
          {items.map((i) => (
            <div
              key={i.id}
              className={`pointer-events-auto flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium shadow-lg motion-safe:animate-[toast-in_200ms_ease-out] ${STYLE[i.kind]}`}
            >
              <span aria-hidden="true">{ICON[i.kind]}</span>
              {i.message}
            </div>
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}
