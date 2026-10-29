import { useTranslation } from "react-i18next";

import type { Recipe } from "@/lib/genealogy";

/** Servings, times, ingredients and numbered steps. Used on the recipe's page, as the live
 * preview in the editor, and for printing (one page, see `.recipe-print` in index.css). */
export function RecipeView({ recipe, occasion }: { recipe: Recipe; occasion?: string | null }) {
  const { t } = useTranslation();
  const facts = [
    occasion && t("recipes.occasionValue", { occasion }),
    recipe.servings && t("recipes.servingsValue", { count: recipe.servings }),
    recipe.prep_minutes != null && t("recipes.prepValue", { minutes: recipe.prep_minutes }),
    recipe.cook_minutes != null && t("recipes.cookValue", { minutes: recipe.cook_minutes }),
  ].filter(Boolean);
  const ingredients = recipe.ingredients.filter((i) => i.item.trim());
  const steps = recipe.steps.filter((s) => s.trim());

  return (
    <section className="recipe-print space-y-4" data-testid="recipe">
      {facts.length > 0 && (
        <p className="text-bark-700 flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {facts.map((f) => (
            <span key={String(f)}>{f}</span>
          ))}
        </p>
      )}
      <div className="grid gap-6 sm:grid-cols-[minmax(12rem,1fr)_2fr] print:grid-cols-[1fr_2fr]">
        <div>
          <h2 className="mb-2 font-serif text-lg font-semibold">{t("recipes.ingredients")}</h2>
          {ingredients.length === 0 ? (
            <p className="text-bark-700 text-sm">—</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {ingredients.map((i, n) => (
                <li key={n} className="flex gap-2">
                  {i.amount && <span className="font-medium whitespace-nowrap">{i.amount}</span>}
                  <span>{i.item}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h2 className="mb-2 font-serif text-lg font-semibold">{t("recipes.steps")}</h2>
          {steps.length === 0 ? (
            <p className="text-bark-700 text-sm">—</p>
          ) : (
            <ol className="list-decimal space-y-2 pl-5 text-sm">
              {steps.map((s, n) => (
                <li key={n} className="whitespace-pre-line">
                  {s}
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </section>
  );
}
