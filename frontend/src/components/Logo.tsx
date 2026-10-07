/**
 * The Korinnia ("roots") mark: a tree with its roots. Colours come from the theme's CSS
 * variables, so it fits the light, dark and archive themes.
 */
export function Logo({ className = "size-8" }: { className?: string }) {
  const leaf = { fill: "var(--k-logo-leaf)" };
  const leafLight = { fill: "var(--k-logo-leaf-light)" };
  const wood = { stroke: "var(--k-logo-trunk)" };
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true" focusable="false">
      {/* Roots under the ground line */}
      <g fill="none" strokeLinecap="round" style={wood}>
        <path d="M24 35c-1 4-5 6-10 8" strokeWidth="2" />
        <path d="M24 35c1 4 5 6 10 8" strokeWidth="2" />
        <path d="M24 35c0 4-1 7 0 10" strokeWidth="2" />
        <path d="M20 39c-2 1-4 3-5 5" strokeWidth="1.3" />
        <path d="M28 39c2 1 4 3 5 5" strokeWidth="1.3" />
      </g>
      <path
        d="M9 35.5h30"
        strokeWidth="1.2"
        strokeLinecap="round"
        style={{ stroke: "var(--k-logo-ground)" }}
      />
      {/* Trunk and branches */}
      <path
        d="M22.6 36c.6-4 .7-8 .4-12l-4-4.5M23 24.5l5.5-5M25.4 36c-.5-4-.4-8 0-12"
        fill="none"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={wood}
      />
      {/* Canopy */}
      <circle cx="24" cy="14" r="9" style={leaf} />
      <circle cx="15" cy="18" r="7" style={leaf} />
      <circle cx="33" cy="18" r="7" style={leaf} />
      <circle cx="18.5" cy="10" r="6" style={leaf} />
      <circle cx="29.5" cy="10" r="6" style={leaf} />
      <circle cx="20" cy="9" r="2.6" style={leafLight} />
      <circle cx="13.5" cy="16.5" r="2" style={leafLight} />
      <circle cx="28" cy="12" r="2.2" style={leafLight} />
    </svg>
  );
}
