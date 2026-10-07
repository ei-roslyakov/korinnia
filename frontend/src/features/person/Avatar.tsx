import type { Gender } from "@/lib/genealogy";
import { initials } from "@/lib/names";

const TONES: Record<Gender, string> = {
  male: "bg-sky-100 text-sky-800",
  female: "bg-rose-100 text-rose-800",
  other: "bg-violet-100 text-violet-800",
  unknown: "bg-bark-100 text-bark-700",
};

/** Portrait (cropped primary photo) or initials when there is no photo yet. */
export function Avatar({
  name,
  gender,
  url,
  size = "md",
}: {
  name: string;
  gender: Gender;
  url?: string | null;
  size?: "sm" | "md" | "lg";
}) {
  const sizes = { sm: "size-10 text-sm", md: "size-12 text-base", lg: "size-20 text-2xl" };
  if (url) {
    return (
      <img
        src={url}
        alt=""
        loading="lazy"
        draggable={false}
        className={`shrink-0 rounded-full object-cover ${sizes[size]}`}
      />
    );
  }
  return (
    <div
      aria-hidden
      className={`flex shrink-0 items-center justify-center rounded-full font-serif font-semibold ${sizes[size]} ${TONES[gender]}`}
    >
      {initials(name)}
    </div>
  );
}
