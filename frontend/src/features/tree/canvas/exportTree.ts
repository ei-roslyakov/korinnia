import type { Rect } from "@xyflow/react";
import { toCanvas } from "html-to-image";

import { jpegToPdf } from "@/lib/pdf";

export type ExportFormat = "png" | "pdf";

/** Space around the tree and the height of the title strip, in tree units. */
const PADDING = 40;
const HEADER = 72;
/** Browsers refuse bigger canvases; very large trees are exported at a lower resolution. */
const MAX_SIDE = 14000;
const MAX_AREA = 100_000_000;

/** Pixels per tree unit: sharp (3×) for small trees, as much as the canvas limits allow otherwise. */
export function exportRatio(width: number, height: number): number {
  return Math.min(3, MAX_SIDE / width, MAX_SIDE / height, Math.sqrt(MAX_AREA / (width * height)));
}

const cssVar = (el: Element, name: string) => getComputedStyle(el).getPropertyValue(name).trim();

/**
 * Draws the whole tree (every card, not only the visible ones) into an image with the tree's
 * name on top, then downloads it as PNG or as a one-page PDF.
 */
export async function exportTree({
  root,
  bounds,
  format,
  title,
  subtitle,
  fileName,
}: {
  /** The React Flow root element. */
  root: HTMLElement;
  /** Bounds of all nodes, in tree coordinates. */
  bounds: Rect;
  format: ExportFormat;
  title: string;
  subtitle: string;
  fileName: string;
}): Promise<void> {
  const viewport = root.querySelector<HTMLElement>(".react-flow__viewport");
  if (!viewport) throw new Error("tree viewport not found");
  const width = Math.ceil(bounds.width + 2 * PADDING);
  const height = Math.ceil(bounds.height + 2 * PADDING);
  const ratio = exportRatio(width, height + HEADER);

  const tree = await toCanvas(viewport, {
    width,
    height,
    pixelRatio: ratio,
    // Transparent: the theme's sky-to-meadow gradient is painted underneath below.
    style: {
      width: `${width}px`,
      height: `${height}px`,
      transform: `translate(${PADDING - bounds.x}px, ${PADDING - bounds.y}px) scale(1)`,
    },
    // No "+" buttons or other controls in the picture.
    filter: (node) => !(node instanceof HTMLButtonElement),
  });

  const out = document.createElement("canvas");
  out.width = tree.width;
  out.height = Math.round((height + HEADER) * ratio);
  const ctx = out.getContext("2d")!;
  ctx.fillStyle = cssVar(root, "--k-surface") || "#ffffff";
  ctx.fillRect(0, 0, out.width, out.height);
  ctx.scale(ratio, ratio);
  ctx.fillStyle = cssVar(root, "--k-bark-900") || "#2a251c";
  ctx.font = `600 28px "Lora Variable", Georgia, serif`;
  ctx.fillText(title, PADDING, 40);
  ctx.fillStyle = cssVar(root, "--k-bark-700") || "#4a4335";
  ctx.font = `13px "Inter Variable", system-ui, sans-serif`;
  ctx.fillText(subtitle, PADDING, 60);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const top = Math.round(HEADER * ratio);
  const stops = gradientStops(cssVar(root, "--k-canvas"));
  if (stops.length) {
    const sky = ctx.createLinearGradient(0, top, 0, out.height);
    for (const [color, at] of stops) sky.addColorStop(at, color);
    ctx.fillStyle = sky;
    ctx.fillRect(0, top, out.width, out.height - top);
  }
  ctx.drawImage(tree, 0, top);

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

/** Colour stops of a CSS `linear-gradient(to bottom, #a 0%, #b 70%, …)`, as [colour, 0–1]. */
export function gradientStops(css: string): [string, number][] {
  const stops: [string, number][] = [];
  for (const m of css.matchAll(/(#[0-9a-f]{3,8}|rgba?\([^)]*\))\s+([\d.]+)%/gi)) {
    stops.push([m[1]!, Math.min(1, Number(m[2]) / 100)]);
  }
  return stops;
}

function toBlob(canvas: HTMLCanvasElement, type: string, quality?: number): Promise<Blob> {
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("export failed"))), type, quality),
  );
}

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** A file name from the tree's name and today's date ("Родина-Коваленків-2026-10-08"). */
export function exportFileName(name: string, today = new Date()): string {
  const base = name
    .normalize("NFKC")
    .replace(/[\\/:*?"<>|]+/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .slice(0, 80);
  return `${base || "tree"}-${today.toISOString().slice(0, 10)}`;
}
