import { useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui";

const MIN = 0.3;
const MAX = 4;
const clamp = (k: number) => Math.min(MAX, Math.max(MIN, k));

/** Pan by dragging, zoom with the wheel or a pinch, like the tree canvas; buttons for
 * keyboard and mouse users. The chart inside keeps its own size (exports use that). */
export function PanZoom({ children, label }: { children: ReactNode; label: string }) {
  const { t } = useTranslation();
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinch = useRef<number | null>(null);
  const moved = useRef(false);

  const zoomAt = (factor: number, cx: number, cy: number) =>
    setView((v) => {
      const k = clamp(v.k * factor);
      const f = k / v.k;
      return { k, x: cx - (cx - v.x) * f, y: cy - (cy - v.y) * f };
    });

  return (
    <div className="relative">
      <div
        role="region"
        aria-label={label}
        className="border-bark-100 bg-surface relative h-[70vh] min-h-96 touch-none overflow-hidden rounded-lg border select-none"
        onWheel={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          zoomAt(e.deltaY < 0 ? 1.1 : 1 / 1.1, e.clientX - r.left, e.clientY - r.top);
        }}
        onPointerDown={(e) => {
          pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
          moved.current = false;
        }}
        onPointerMove={(e) => {
          const last = pointers.current.get(e.pointerId);
          if (!last) return;
          const now = { x: e.clientX, y: e.clientY };
          pointers.current.set(e.pointerId, now);
          if (pointers.current.size === 2) {
            const [a, b] = [...pointers.current.values()] as [typeof now, typeof now];
            const dist = Math.hypot(a.x - b.x, a.y - b.y);
            if (pinch.current) {
              const r = e.currentTarget.getBoundingClientRect();
              zoomAt(dist / pinch.current, (a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top);
            }
            pinch.current = dist;
            return;
          }
          const dx = now.x - last.x;
          const dy = now.y - last.y;
          if (Math.abs(dx) + Math.abs(dy) > 2) {
            moved.current = true;
            e.currentTarget.setPointerCapture?.(e.pointerId);
          }
          if (moved.current) setView((v) => ({ ...v, x: v.x + dx, y: v.y + dy }));
        }}
        onPointerUp={(e) => {
          pointers.current.delete(e.pointerId);
          pinch.current = null;
        }}
        onPointerCancel={(e) => {
          pointers.current.delete(e.pointerId);
          pinch.current = null;
        }}
        // A drag must not click the sector it ends on.
        onClickCapture={(e) => {
          if (moved.current) {
            e.stopPropagation();
            moved.current = false;
          }
        }}
      >
        <div
          style={{
            transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})`,
            transformOrigin: "0 0",
          }}
          className="flex min-h-full min-w-full items-start justify-center p-4"
        >
          {children}
        </div>
      </div>
      <div className="absolute right-2 bottom-2 flex gap-1 print:hidden">
        <Button
          variant="secondary"
          aria-label={t("charts.zoomIn")}
          onClick={() => zoomAt(1.25, 0, 0)}
        >
          +
        </Button>
        <Button
          variant="secondary"
          aria-label={t("charts.zoomOut")}
          onClick={() => zoomAt(0.8, 0, 0)}
        >
          −
        </Button>
        <Button variant="secondary" onClick={() => setView({ x: 0, y: 0, k: 1 })}>
          {t("charts.resetView")}
        </Button>
      </div>
    </div>
  );
}
