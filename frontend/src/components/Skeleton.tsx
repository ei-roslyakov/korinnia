/** Placeholder shapes shown while content loads (instead of a lone spinner). */
export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div aria-hidden="true" className={`bg-bark-100 animate-pulse rounded ${className}`} />;
}

/** A grid of card-shaped placeholders. */
export function CardsSkeleton({ count = 3, label }: { count?: number; label: string }) {
  return (
    <div role="status" aria-label={label} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="border-bark-100 bg-surface space-y-3 rounded-lg border p-4">
          <div className="flex -space-x-3">
            {[0, 1, 2].map((k) => (
              <Skeleton key={k} className="border-surface size-10 rounded-full border-2" />
            ))}
          </div>
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      ))}
    </div>
  );
}

/** Lines of text-shaped placeholders. */
export function TextSkeleton({ lines = 4, label }: { lines?: number; label: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-3">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={`h-4 ${i % 3 === 2 ? "w-2/3" : "w-full"}`} />
      ))}
    </div>
  );
}
