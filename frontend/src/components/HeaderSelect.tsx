import type { SelectHTMLAttributes } from "react";

/** A compact select for the header, with its own arrow and room on the right of it. */
export function HeaderSelect(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span className="relative inline-flex items-center">
      <select
        {...props}
        className="border-bark-100 bg-surface text-bark-900 hover:border-leaf-600 focus:border-leaf-600 focus:ring-leaf-600 cursor-pointer appearance-none rounded-md border py-1 pr-9 pl-3 text-sm focus:ring-1 focus:outline-none"
      />
      <svg
        viewBox="0 0 12 12"
        aria-hidden="true"
        className="text-bark-700 pointer-events-none absolute right-3 size-3"
      >
        <path
          d="M2.5 4.5 6 8l3.5-3.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}
