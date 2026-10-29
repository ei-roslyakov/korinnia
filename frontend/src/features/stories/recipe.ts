import type { Recipe } from "@/lib/genealogy";

export const EMPTY_RECIPE: Recipe = {
  servings: null,
  prep_minutes: null,
  cook_minutes: null,
  ingredients: [{ amount: "", item: "" }],
  steps: [""],
};

/** What is sent: rows without an ingredient or a step are left out. */
export function cleanRecipe(r: Recipe): Recipe {
  return {
    ...r,
    ingredients: r.ingredients
      .filter((i) => i.item.trim())
      .map((i) => ({ amount: i.amount?.trim() || null, item: i.item.trim() })),
    steps: r.steps.map((s) => s.trim()).filter(Boolean),
  };
}
