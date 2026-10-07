import { useRef, useState, type PointerEvent } from "react";

import type { Region } from "@/lib/genealogy";

const clamp = (v: number) => Math.min(1, Math.max(0, v));

/**
 * Image with a rectangle drawn by dragging (mouse or touch). Values are fractions of the
 * image size. With `square`, the rectangle is a square in pixels (portrait crops).
 */
export function RegionSelector({
  src,
  value,
  onChange,
  square = false,
  others = [],
  label,
}: {
  src: string;
  value: Region | null;
  onChange: (r: Region) => void;
  square?: boolean;
  others?: { region: Region; label: string }[];
  label: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [start, setStart] = useState<{ x: number; y: number } | null>(null);

  const point = (e: PointerEvent) => {
    const box = ref.current!.getBoundingClientRect();
    return {
      x: clamp((e.clientX - box.left) / box.width),
      y: clamp((e.clientY - box.top) / box.height),
      box,
    };
  };

  const onMove = (e: PointerEvent) => {
    if (!start) return;
    const p = point(e);
    let w = Math.abs(p.x - start.x);
    let h = Math.abs(p.y - start.y);
    if (square) {
      const ratio = p.box.width / p.box.height; // fraction-of-width → fraction-of-height
      const side = Math.max(w * ratio, h);
      h = Math.min(side, start.y < p.y ? 1 - start.y : start.y);
      w = Math.min(h / ratio, start.x < p.x ? 1 - start.x : start.x);
      h = w * ratio;
    }
    const x = p.x < start.x ? start.x - w : start.x;
    const y = p.y < start.y ? start.y - h : start.y;
    if (w > 0.01 && h > 0.01) onChange({ x, y, w, h });
  };

  return (
    <div
      ref={ref}
      role="application"
      aria-label={label}
      className="relative inline-block cursor-crosshair touch-none select-none"
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture(e.pointerId);
        const p = point(e);
        setStart({ x: p.x, y: p.y });
      }}
      onPointerMove={onMove}
      onPointerUp={() => setStart(null)}
    >
      <img src={src} alt="" draggable={false} className="block max-h-[60vh] max-w-full" />
      {others.map((o) => (
        <div
          key={o.label}
          className="pointer-events-none absolute border-2 border-white/70"
          style={{
            left: `${o.region.x * 100}%`,
            top: `${o.region.y * 100}%`,
            width: `${o.region.w * 100}%`,
            height: `${o.region.h * 100}%`,
          }}
        >
          <span className="absolute top-full left-0 bg-black/60 px-1 text-xs text-white">
            {o.label}
          </span>
        </div>
      ))}
      {value && (
        <div
          data-testid="region"
          className="border-leaf-600 bg-leaf-600/10 pointer-events-none absolute border-2 shadow-[0_0_0_9999px_rgba(0,0,0,0.35)]"
          style={{
            left: `${value.x * 100}%`,
            top: `${value.y * 100}%`,
            width: `${value.w * 100}%`,
            height: `${value.h * 100}%`,
          }}
        />
      )}
    </div>
  );
}
