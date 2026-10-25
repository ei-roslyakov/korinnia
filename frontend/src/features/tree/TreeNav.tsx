import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { atLeast, type Role } from "@/lib/types";

/** Links to the tree's other views; one scrollable row so it never wraps on phones. */
export function TreeNav({
  treeId,
  role,
  pending = 0,
}: {
  treeId: string;
  role: Role;
  pending?: number;
}) {
  const { t } = useTranslation();
  const moderation = (
    <>
      {t("collab.moderation.title")}
      {pending > 0 && (
        <span
          className="ml-1 rounded-full bg-amber-500 px-1.5 text-xs text-white"
          aria-label={t("collab.moderation.pending", { count: pending })}
        >
          {pending}
        </span>
      )}
    </>
  );
  const links: [string, ReactNode, boolean][] = [
    ["album", t("insights.nav.album"), true],
    ["timeline", t("insights.nav.timeline"), true],
    ["map", t("insights.nav.map"), true],
    ["on-this-day", t("insights.nav.onThisDay"), true],
    ["relationship", t("insights.nav.relationship"), true],
    ["stats", t("insights.nav.stats"), true],
    ["stories", t("collab.stories"), true],
    ["sources", t("collab.sources"), true],
    ["quality", t("collab.quality.title"), atLeast(role, "contributor")],
    ["moderation", moderation, atLeast(role, "editor")],
    ["members", t("members.title"), atLeast(role, "admin")],
    ["audit", t("canvas.history"), atLeast(role, "admin")],
  ];
  return (
    <nav
      aria-label={t("insights.nav.label")}
      className="flex w-full gap-4 overflow-x-auto text-sm whitespace-nowrap"
    >
      {links
        .filter(([, , show]) => show)
        .map(([path, label]) => (
          <Link
            key={path}
            to={`/trees/${treeId}/${path}`}
            className="text-leaf-700 hover:underline"
          >
            {label}
          </Link>
        ))}
    </nav>
  );
}
