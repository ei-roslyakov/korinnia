import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { Input } from "@/components/ui";
import { lifeYears } from "@/lib/dates";
import type { PersonSummary } from "@/lib/genealogy";

import { usePersonSearch } from "./api";

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

/** Accessible combobox searching people by name variant (Cyrillic/Latin), place or year. */
export function PersonCombobox({
  treeId,
  onSelect,
  label,
  excludeIds = [],
}: {
  treeId: string;
  onSelect: (person: PersonSummary) => void;
  label: string;
  excludeIds?: string[];
}) {
  const { t } = useTranslation();
  const listId = useId();
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const query = useDebounced(text.trim(), 250);
  const search = usePersonSearch(treeId, query);
  const results =
    query.length >= 2 ? (search.data?.items ?? []).filter((p) => !excludeIds.includes(p.id)) : [];
  const showList = open && query.length >= 2;

  const choose = (person: PersonSummary) => {
    onSelect(person);
    setOpen(false);
    setText("");
  };

  return (
    <div className="relative w-full max-w-sm">
      <Input
        type="search"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showList && results[active] ? `${listId}-${active}` : undefined}
        aria-label={label}
        placeholder={label}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((i) => Math.min(i + 1, results.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (e.key === "Enter" && results[active]) {
            e.preventDefault();
            choose(results[active]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {showList && (
        <ul
          id={listId}
          role="listbox"
          className="border-bark-100 absolute z-30 mt-1 max-h-80 w-full overflow-y-auto rounded-md border bg-white py-1 shadow-lg"
        >
          {search.isFetching && results.length === 0 && (
            <li className="text-bark-700 px-3 py-2 text-sm">{t("canvas.searching")}</li>
          )}
          {!search.isFetching && results.length === 0 && (
            <li className="text-bark-700 px-3 py-2 text-sm">{t("canvas.noResults")}</li>
          )}
          {results.map((p, i) => (
            <li
              key={p.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              className={`cursor-pointer px-3 py-2 text-sm ${i === active ? "bg-bark-100" : ""}`}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(p);
              }}
            >
              <div className="font-medium">{p.display_name}</div>
              <div className="text-bark-700 text-xs">
                {[lifeYears(p.birth, p.death, p.is_living), p.birth_place]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
