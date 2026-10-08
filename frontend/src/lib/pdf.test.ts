import { describe, expect, it } from "vitest";

import { jpegToPdf, pageFor } from "./pdf";

const bytesOf = async (blob: Blob) => new Uint8Array(await blob.arrayBuffer());
const latin1 = (bytes: Uint8Array) => Array.from(bytes, (b) => String.fromCharCode(b)).join("");

describe("jpegToPdf", () => {
  it("wraps the JPEG bytes unchanged with a valid cross-reference table", async () => {
    const jpeg = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 1, 2, 3, 0xff, 0xd9]);
    const pdf = jpegToPdf(jpeg, 1200, 800);
    expect(pdf.type).toBe("application/pdf");
    const text = latin1(await bytesOf(pdf));

    expect(text.startsWith("%PDF-1.4")).toBe(true);
    expect(text.trimEnd().endsWith("%%EOF")).toBe(true);
    expect(text).toContain(latin1(jpeg));
    expect(text).toContain("/Width 1200 /Height 800");
    expect(text).toContain("/MediaBox [0 0 842 595]"); // A4 landscape

    // Every xref entry points at its "n 0 obj" line, and startxref at the table.
    const xref = text.lastIndexOf("\nxref\n") + 1;
    expect(Number(text.slice(text.lastIndexOf("startxref\n") + 10).split("\n")[0])).toBe(xref);
    const entries = text.slice(xref).split("\n").slice(3, 8);
    entries.forEach((line, i) => {
      const offset = Number(line.slice(0, 10));
      expect(text.slice(offset, offset + 8)).toBe(`${i + 1} 0 obj\n`.slice(0, 8));
    });
  });

  it("picks a bigger sheet for bigger images, in their orientation", () => {
    expect(pageFor(1000, 2000)).toEqual({ width: 595, height: 842 });
    expect(pageFor(4000, 2000)).toEqual({ width: 1191, height: 842 });
    expect(pageFor(9000, 3000)).toEqual({ width: 1684, height: 1191 });
  });
});
