import type { TFunction } from "i18next";

import type { MediaItem } from "@/lib/genealogy";

/** Alt text: the title, else the description, else who is in the photo. */
export function photoAlt(item: MediaItem, t: TFunction): string {
  if (item.title) return item.title;
  if (item.description) return item.description.slice(0, 250);
  if (item.people.length > 0)
    return t("album.photoOf", { names: item.people.map((p) => p.display_name).join(", ") });
  return t("album.photo");
}
