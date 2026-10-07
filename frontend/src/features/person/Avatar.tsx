import type { Gender } from "@/lib/genealogy";
import { initials } from "@/lib/names";

const TONES: Record<Gender, string> = {
  male: "bg-sky-100 text-sky-800",
  female: "bg-rose-100 text-rose-800",
  other: "bg-violet-100 text-violet-800",
  unknown: "bg-bark-100 text-bark-700",
};

/** Placeholder portrait (photos arrive with media support). */
export function Avatar({
  name,
  gender,
  size = "md",
}: {
  name: string;
  gender: Gender;
  size?: "sm" | "md" | "lg";
}) {
  const sizes = { sm: "size-10 text-sm", md: "size-12 text-base", lg: "size-20 text-2xl" };
  return (
    <div
      aria-hidden
      className={`flex shrink-0 items-center justify-center rounded-full font-serif font-semibold ${sizes[size]} ${TONES[gender]}`}
    >
      {initials(name)}
    </div>
  );
}
