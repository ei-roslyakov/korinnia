/**
 * Join a component's base classes with caller classes, letting the caller override.
 *
 * Two Tailwind utilities for the same property (`w-full` and `w-auto`) both match, and the
 * winner depends on their order in the generated CSS, not in the class attribute. So base
 * utilities of a group the caller sets (width, height, padding, display) are dropped.
 */
const GROUPS: [string, RegExp][] = [
  ["w", /^w-/],
  ["min-w", /^min-w-/],
  ["max-w", /^max-w-/],
  ["h", /^h-/],
  ["p", /^p-/],
  ["px", /^px-/],
  ["py", /^py-/],
  ["display", /^(block|inline|inline-block|inline-flex|flex|grid|hidden)$/],
];
// Setting all padding also replaces the axis paddings.
const COVERS: Record<string, string[]> = { p: ["p", "px", "py"] };

const groupOf = (cls: string) => GROUPS.find(([, re]) => re.test(cls))?.[0];

export function cx(base: string, extra?: string): string {
  const extras = (extra ?? "").split(/\s+/).filter(Boolean);
  const overridden = new Set(
    extras.flatMap((c) => {
      const g = groupOf(c);
      return g ? (COVERS[g] ?? [g]) : [];
    }),
  );
  const kept = base.split(/\s+/).filter((c) => c && !overridden.has(groupOf(c) ?? ""));
  return [...kept, ...extras].join(" ");
}
