import { toCanvas } from "html-to-image";

import { download, toBlob, type ExportFormat } from "@/features/tree/canvas/exportTree";
import { jpegToPdf } from "@/lib/pdf";

const PADDING = 32;
const HEADER = 64;
const RATIO = 2;

const cssVar = (el: Element, name: string) => getComputedStyle(el).getPropertyValue(name).trim();

/** A chart (the SVG or the outline) as PNG or a one-page PDF, with a title strip on top —
 * the same mechanism as the tree export (D88). The element is drawn at its own size, not
 * at the current zoom. */
export async function exportChart({
  element,
  format,
  title,
  subtitle,
  fileName,
}: {
  element: HTMLElement | SVGSVGElement;
  format: ExportFormat;
  title: string;
  subtitle: string;
  fileName: string;
}): Promise<void> {
  const width = Math.ceil(element.scrollWidth || element.getBoundingClientRect().width);
  const height = Math.ceil(element.scrollHeight || element.getBoundingClientRect().height);
  const chart = await toCanvas(element as HTMLElement, {
    width,
    height,
    pixelRatio: RATIO,
    style: { transform: "none", margin: "0" },
    filter: (node) => !(node instanceof HTMLButtonElement),
  });
  const out = document.createElement("canvas");
  out.width = Math.round((width + 2 * PADDING) * RATIO);
  out.height = Math.round((height + HEADER + PADDING) * RATIO);
  const ctx = out.getContext("2d")!;
  const root = document.documentElement;
  ctx.fillStyle = cssVar(root, "--k-surface-solid") || cssVar(root, "--k-surface") || "#ffffff";
  ctx.fillRect(0, 0, out.width, out.height);
  ctx.scale(RATIO, RATIO);
  ctx.fillStyle = cssVar(root, "--k-bark-900") || "#2a251c";
  ctx.font = `600 24px "Lora Variable", Georgia, serif`;
  ctx.fillText(title, PADDING, 36);
  ctx.fillStyle = cssVar(root, "--k-bark-700") || "#4a4335";
  ctx.font = `13px "Inter Variable", system-ui, sans-serif`;
  ctx.fillText(subtitle, PADDING, 54);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.drawImage(chart, PADDING * RATIO, HEADER * RATIO);
  const blob =
    format === "png"
      ? await toBlob(out, "image/png")
      : jpegToPdf(
          new Uint8Array(await (await toBlob(out, "image/jpeg", 0.92)).arrayBuffer()),
          out.width,
          out.height,
        );
  download(blob, `${fileName}.${format}`);
}
