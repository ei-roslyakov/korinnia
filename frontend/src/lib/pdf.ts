/**
 * A one-page PDF around a JPEG image, without a PDF library: the JPEG bytes go into the file
 * as they are (DCTDecode), so nothing is re-encoded. The page is an A-series sheet in the
 * image's orientation, sized to its resolution, with the image fitted inside a margin.
 */

/** A-series sheets in PDF points (1/72 inch), long side first. */
const SHEETS = [
  { name: "A4", long: 842, short: 595, maxPixels: 2500 },
  { name: "A3", long: 1191, short: 842, maxPixels: 5000 },
  { name: "A2", long: 1684, short: 1191, maxPixels: Infinity },
] as const;
const MARGIN = 28;

export function pageFor(width: number, height: number) {
  const sheet = SHEETS.find((s) => Math.max(width, height) <= s.maxPixels)!;
  return width >= height
    ? { width: sheet.long, height: sheet.short }
    : { width: sheet.short, height: sheet.long };
}

export function jpegToPdf(jpeg: Uint8Array, width: number, height: number): Blob {
  const page = pageFor(width, height);
  const scale = Math.min((page.width - 2 * MARGIN) / width, (page.height - 2 * MARGIN) / height);
  const w = width * scale;
  const h = height * scale;
  const x = (page.width - w) / 2;
  const y = (page.height - h) / 2;
  const draw = `q ${w.toFixed(2)} 0 0 ${h.toFixed(2)} ${x.toFixed(2)} ${y.toFixed(2)} cm /Im0 Do Q`;

  const enc = new TextEncoder();
  const parts: Uint8Array[] = [];
  const offsets: number[] = [];
  let length = 0;
  const push = (chunk: string | Uint8Array) => {
    const bytes = typeof chunk === "string" ? enc.encode(chunk) : chunk;
    parts.push(bytes);
    length += bytes.length;
  };
  const object = (n: number, body: string) => {
    offsets[n] = length;
    push(`${n} 0 obj\n${body}\nendobj\n`);
  };

  push("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n");
  object(1, "<< /Type /Catalog /Pages 2 0 R >>");
  object(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>");
  object(
    3,
    `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${page.width} ${page.height}] ` +
      "/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>",
  );
  offsets[4] = length;
  push(
    `4 0 obj\n<< /Type /XObject /Subtype /Image /Width ${width} /Height ${height} ` +
      `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`,
  );
  push(jpeg);
  push("\nendstream\nendobj\n");
  object(5, `<< /Length ${draw.length} >>\nstream\n${draw}\nendstream`);

  const xref = length;
  push("xref\n0 6\n0000000000 65535 f \n");
  for (let n = 1; n <= 5; n++) push(`${String(offsets[n]).padStart(10, "0")} 00000 n \n`);
  push(`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  return new Blob(parts as BlobPart[], { type: "application/pdf" });
}
