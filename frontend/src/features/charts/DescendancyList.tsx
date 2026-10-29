import { forwardRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { lifeYears } from "@/lib/dates";
import type { PersonSummary } from "@/lib/genealogy";

import type { DescendantNode } from "./lineage";

/** Descendants as an indented outline numbered 1, 1.1, 1.2, 1.2.1 … (d'Aboville), partners
 * inline with the year of marriage; every generation can be folded. */
export const DescendancyList = forwardRef<
  HTMLDivElement,
  {
    root: DescendantNode;
    personLink: (id: string) => string;
    /** Living people as names only (no years). */
    namesOnly: boolean;
  }
>(function DescendancyList({ root, personLink, namesOnly }, ref) {
  return (
    <div ref={ref} className="bg-surface p-2 text-sm" data-testid="descendancy">
      <ul>
        <Node node={root} personLink={personLink} namesOnly={namesOnly} />
      </ul>
    </div>
  );
});

function Node({
  node,
  personLink,
  namesOnly,
}: {
  node: DescendantNode;
  personLink: (id: string) => string;
  namesOnly: boolean;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(true);
  const years = (p: PersonSummary) =>
    namesOnly && p.is_living ? "" : lifeYears(p.birth, p.death, p.is_living);
  const who = (p: PersonSummary) => (
    <>
      <Link to={personLink(p.id)} className="text-leaf-700 font-medium hover:underline">
        {p.display_name}
      </Link>
      {years(p) && <span className="text-bark-700"> ({years(p)})</span>}
    </>
  );
  return (
    <li className="py-0.5" data-testid="descendant" data-number={node.number}>
      <div className="flex items-baseline gap-2">
        {node.children.length > 0 ? (
          <button
            type="button"
            aria-expanded={open}
            aria-label={t(open ? "charts.descendants.fold" : "charts.descendants.unfold", {
              name: node.person.display_name,
            })}
            className="text-bark-700 w-4 shrink-0 text-xs print:hidden"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? "▾" : "▸"}
          </button>
        ) : (
          <span className="w-4 shrink-0" />
        )}
        <span className="text-bark-700 shrink-0 font-mono text-xs tabular-nums">{node.number}</span>
        <span>
          {who(node.person)}
          {node.partners.map(({ person, year }) => (
            <span key={person.id} className="text-bark-700">
              {" "}
              ⚭{year ? ` ${year}` : ""} {who(person)}
            </span>
          ))}
        </span>
      </div>
      {open && node.children.length > 0 && (
        <ul className="border-bark-100 ml-2 border-l pl-4">
          {node.children.map((c) => (
            <Node key={c.person.id} node={c} personLink={personLink} namesOnly={namesOnly} />
          ))}
        </ul>
      )}
    </li>
  );
}
