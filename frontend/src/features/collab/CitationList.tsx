import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui";
import type { Citation } from "@/lib/genealogy";

import { citationTargetLabel } from "./labels";

const QUALITY_TONE = {
  primary: "green",
  secondary: "neutral",
  family_tradition: "amber",
  unverified: "red",
} as const;

/** Citations grouped by source: "Метрична книга — арк. 34 — supports: Народження". */
export function CitationList({ citations }: { citations: Citation[] }) {
  const { t } = useTranslation();
  const bySource = new Map<string, Citation[]>();
  for (const c of citations) bySource.set(c.source.id, [...(bySource.get(c.source.id) ?? []), c]);
  return (
    <ul className="space-y-3 text-sm">
      {[...bySource.values()].map((group) => (
        <li key={group[0]!.source.id}>
          <div className="font-medium">
            {group[0]!.source.title}{" "}
            <span className="text-bark-700 text-xs">
              ({t(`collab.sourceTypes.${group[0]!.source.type}`)})
            </span>
          </div>
          <ul className="mt-1 space-y-1 pl-3">
            {group.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-2">
                <span>{citationTargetLabel(t, c.target, c.field)}</span>
                {c.page && <span className="text-bark-700">· {c.page}</span>}
                <Badge tone={QUALITY_TONE[c.quality]}>{t(`collab.quality.${c.quality}`)}</Badge>
                {c.notes && <span className="text-bark-700 w-full text-xs">{c.notes}</span>}
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}
