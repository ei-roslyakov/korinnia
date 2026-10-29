import { describe, expect, it } from "vitest";

import { cleanRecipe } from "./recipe";

describe("cleanRecipe", () => {
  it("drops empty rows and trims what is sent", () => {
    expect(
      cleanRecipe({
        servings: 4,
        ingredients: [
          { amount: " 500 г ", item: " борошно " },
          { amount: "", item: "вишні" },
          { amount: "1", item: "  " },
        ],
        steps: [" Замісити тісто. ", "", "Зварити."],
      }),
    ).toEqual({
      servings: 4,
      ingredients: [
        { amount: "500 г", item: "борошно" },
        { amount: null, item: "вишні" },
      ],
      steps: ["Замісити тісто.", "Зварити."],
    });
  });
});
