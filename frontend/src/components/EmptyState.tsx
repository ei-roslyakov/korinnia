import type { ReactNode } from "react";

import { Logo } from "./Logo";

/** A friendly "nothing here yet": the tree mark, a short message and an optional action. */
export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="border-bark-100 bg-surface flex flex-col items-center gap-2 rounded-lg border border-dashed px-6 py-10 text-center">
      <Logo className="size-16 opacity-60 grayscale-[35%]" />
      <p className="font-serif text-lg font-semibold">{title}</p>
      {hint && <p className="text-bark-700 max-w-md text-sm">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
