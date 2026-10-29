import type { ReactNode } from "react";
import { Link } from "react-router";

import type { PlaceSummary } from "@/lib/genealogy";

/** A place's name as a link to its page (D116). */
export function PlaceLink({
  treeId,
  place,
  children,
}: {
  treeId: string;
  place: Pick<PlaceSummary, "id" | "name">;
  children?: ReactNode;
}) {
  return (
    <Link to={`/trees/${treeId}/places/${place.id}`} className="text-leaf-700 hover:underline">
      {children ?? place.name}
    </Link>
  );
}
