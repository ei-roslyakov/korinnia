import { useTranslation } from "react-i18next";

import { Button, Field, Input, TextArea } from "@/components/ui";
import type { Recipe } from "@/lib/genealogy";

const number = (v: string) => (v === "" ? null : Math.max(0, Math.round(Number(v))));

/** The structured part of a recipe: servings, times, ingredient rows and step rows. */
export function RecipeFields({
  value,
  onChange,
}: {
  value: Recipe;
  onChange: (r: Recipe) => void;
}) {
  const { t } = useTranslation();
  const set = (patch: Partial<Recipe>) => onChange({ ...value, ...patch });

  return (
    <fieldset className="border-bark-100 space-y-4 rounded-lg border p-4">
      <legend className="px-1 text-sm font-semibold">{t("recipes.title")}</legend>
      <div className="grid grid-cols-3 gap-3">
        <Field label={t("recipes.servings")}>
          {(id) => (
            <Input
              id={id}
              type="number"
              min={1}
              value={value.servings ?? ""}
              onChange={(e) => set({ servings: number(e.target.value) || null })}
            />
          )}
        </Field>
        <Field label={t("recipes.prep")}>
          {(id) => (
            <Input
              id={id}
              type="number"
              min={0}
              value={value.prep_minutes ?? ""}
              onChange={(e) => set({ prep_minutes: number(e.target.value) })}
            />
          )}
        </Field>
        <Field label={t("recipes.cook")}>
          {(id) => (
            <Input
              id={id}
              type="number"
              min={0}
              value={value.cook_minutes ?? ""}
              onChange={(e) => set({ cook_minutes: number(e.target.value) })}
            />
          )}
        </Field>
      </div>

      <div className="space-y-2">
        <span className="block text-sm font-medium">{t("recipes.ingredients")}</span>
        {value.ingredients.map((ing, i) => (
          <div key={i} className="flex gap-2" data-testid="ingredient-row">
            <Input
              aria-label={t("recipes.amount", { n: i + 1 })}
              placeholder={t("recipes.amountPlaceholder")}
              className="w-32"
              value={ing.amount ?? ""}
              onChange={(e) =>
                set({
                  ingredients: value.ingredients.map((x, j) =>
                    j === i ? { ...x, amount: e.target.value } : x,
                  ),
                })
              }
            />
            <Input
              aria-label={t("recipes.item", { n: i + 1 })}
              placeholder={t("recipes.itemPlaceholder")}
              value={ing.item}
              onChange={(e) =>
                set({
                  ingredients: value.ingredients.map((x, j) =>
                    j === i ? { ...x, item: e.target.value } : x,
                  ),
                })
              }
            />
            <Button
              variant="ghost"
              aria-label={t("recipes.removeIngredient", { n: i + 1 })}
              onClick={() => set({ ingredients: value.ingredients.filter((_, j) => j !== i) })}
            >
              ✕
            </Button>
          </div>
        ))}
        <Button
          variant="secondary"
          onClick={() => set({ ingredients: [...value.ingredients, { amount: "", item: "" }] })}
        >
          + {t("recipes.addIngredient")}
        </Button>
      </div>

      <div className="space-y-2">
        <span className="block text-sm font-medium">{t("recipes.steps")}</span>
        {value.steps.map((step, i) => (
          <div key={i} className="flex items-start gap-2" data-testid="step-row">
            <span className="text-bark-700 mt-2 w-5 text-right text-sm tabular-nums">{i + 1}.</span>
            <TextArea
              aria-label={t("recipes.step", { n: i + 1 })}
              rows={2}
              value={step}
              onChange={(e) =>
                set({ steps: value.steps.map((x, j) => (j === i ? e.target.value : x)) })
              }
            />
            <Button
              variant="ghost"
              aria-label={t("recipes.removeStep", { n: i + 1 })}
              onClick={() => set({ steps: value.steps.filter((_, j) => j !== i) })}
            >
              ✕
            </Button>
          </div>
        ))}
        <Button variant="secondary" onClick={() => set({ steps: [...value.steps, ""] })}>
          + {t("recipes.addStep")}
        </Button>
      </div>
    </fieldset>
  );
}
