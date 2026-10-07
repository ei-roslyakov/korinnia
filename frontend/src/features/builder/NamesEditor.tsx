import { useTranslation } from "react-i18next";

import { Button, Input, Select } from "@/components/ui";
import { NAME_TYPES, SCRIPTS } from "@/lib/genealogy";

import type { NameInput } from "./api";
import { emptyName } from "./helpers";

const PARTS = ["first_name", "patronymic", "last_name", "maiden_name", "middle_name"] as const;

export function NamesEditor({
  names,
  onChange,
}: {
  names: NameInput[];
  onChange: (names: NameInput[]) => void;
}) {
  const { t } = useTranslation();
  const update = (i: number, patch: Partial<NameInput>) =>
    onChange(
      names.map((n, j) => {
        if (patch.is_primary) return j === i ? { ...n, ...patch } : { ...n, is_primary: false };
        return j === i ? { ...n, ...patch } : n;
      }),
    );

  return (
    <div className="space-y-3">
      {names.map((n, i) => (
        <fieldset key={i} className="border-bark-100 space-y-2 rounded-md border p-3">
          <legend className="px-1 text-sm font-medium">
            {t("builder.names.name", { n: i + 1 })}
          </legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {PARTS.map((part) => (
              <Input
                key={part}
                aria-label={`${t(`builder.names.${part}`)} ${i + 1}`}
                placeholder={t(`builder.names.${part}`)}
                value={n[part] ?? ""}
                onChange={(e) => update(i, { [part]: e.target.value })}
              />
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <Select
              aria-label={`${t("builder.names.type")} ${i + 1}`}
              className="w-auto"
              value={n.type}
              onChange={(e) => update(i, { type: e.target.value })}
            >
              {NAME_TYPES.map((x) => (
                <option key={x} value={x}>
                  {t(`nameTypes.${x}`)}
                </option>
              ))}
            </Select>
            <Select
              aria-label={`${t("builder.names.script")} ${i + 1}`}
              className="w-auto"
              value={n.script}
              onChange={(e) => update(i, { script: e.target.value })}
            >
              {SCRIPTS.map((x) => (
                <option key={x} value={x}>
                  {t(`scripts.${x}`)}
                </option>
              ))}
            </Select>
            <label className="flex items-center gap-1">
              <input
                type="radio"
                name="primary-name"
                checked={n.is_primary}
                onChange={() => update(i, { is_primary: true })}
              />
              {t("builder.names.primary")}
            </label>
            <Button
              variant="ghost"
              className="ml-auto text-red-700"
              onClick={() => onChange(names.filter((_, j) => j !== i))}
            >
              {t("common.remove")}
            </Button>
          </div>
        </fieldset>
      ))}
      <Button
        variant="secondary"
        onClick={() => onChange([...names, emptyName(names.length === 0)])}
      >
        + {t("builder.names.add")}
      </Button>
    </div>
  );
}
