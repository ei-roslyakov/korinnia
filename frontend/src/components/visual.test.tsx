import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LifeBar } from "@/features/person/LifeBar";
import i18n from "@/i18n";
import { useToast } from "@/lib/toast";
import { halyna } from "@/test/fixtures";

import { EmptyState } from "./EmptyState";
import { ToastProvider } from "./Toast";

beforeEach(async () => {
  await i18n.changeLanguage("uk");
});

function SaveButton() {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast("Збережено.")}>
      save
    </button>
  );
}

describe("visual helpers", () => {
  it("shows a toast and removes it after a few seconds", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <SaveButton />
      </ToastProvider>,
    );
    act(() => screen.getByRole("button", { name: "save" }).click());
    expect(screen.getByRole("status")).toHaveTextContent("Збережено.");
    act(() => vi.advanceTimersByTime(4100));
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
    vi.useRealTimers();
  });

  it("renders an empty state with its action", () => {
    render(<EmptyState title="Порожньо" hint="Додайте щось" action={<button>Додати</button>} />);
    expect(screen.getByText("Порожньо")).toBeInTheDocument();
    expect(screen.getByText("Додайте щось")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Додати" })).toBeInTheDocument();
  });

  it("draws a life bar from birth to death with a dot per dated event", () => {
    render(<LifeBar person={halyna} />);
    const bar = screen.getByRole("figure");
    expect(bar).toHaveAccessibleName(/Життя з 1923 до 2010/);
    expect(bar).toHaveTextContent("1923");
    expect(bar).toHaveTextContent("2010 · 87 років");
    const dated = halyna.events.filter((e) => e.date?.year);
    expect(bar.querySelectorAll("span[title]")).toHaveLength(dated.length);
  });

  it("skips the life bar without a birth year", () => {
    const { container } = render(<LifeBar person={{ ...halyna, birth: null }} />);
    expect(container).toBeEmptyDOMElement();
  });
});
