import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import { CoupleNode, type CoupleNodeData } from "./nodes";

const draw = (data: Partial<CoupleNodeData>) => {
  const full: CoupleNodeData = {
    width: 56,
    married: true,
    broken: false,
    year: "1946",
    label: "Шлюб · 22 червня 1946 · Львів",
    dim: false,
    ...data,
  };
  const props = { data: full } as unknown as ComponentProps<typeof CoupleNode>;
  return render(<CoupleNode {...props} />);
};

describe("couple link", () => {
  it("shows rings, the wedding year and the details on hover", () => {
    const { container } = draw({});
    expect(screen.getByRole("img", { name: "Шлюб · 22 червня 1946 · Львів" })).toHaveAttribute(
      "title",
      "Шлюб · 22 червня 1946 · Львів",
    );
    expect(screen.getByText("1946")).toBeInTheDocument();
    expect(container.querySelectorAll("circle")).toHaveLength(2);
    expect(container.querySelector("line[stroke-dasharray]")).toBeNull();
  });

  it("is dashed with a heart for partners, struck through after a divorce", () => {
    const partners = draw({ married: false, year: null });
    expect(partners.container.querySelectorAll("circle")).toHaveLength(0);
    expect(partners.container.querySelector("path")).not.toBeNull();
    expect(partners.container.querySelectorAll("line[stroke-dasharray]")).toHaveLength(2);
    partners.unmount();
    const divorced = draw({ broken: true });
    expect(divorced.container.querySelectorAll("line")).toHaveLength(3);
  });
});
