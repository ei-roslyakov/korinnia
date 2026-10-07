/** "Галина Йосипівна Коваленко (Шевчук)" → "ГК". */
export function initials(name: string): string {
  const parts = name
    .replace(/\(.*\)/, "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0 || name === "?") return "?";
  const first = parts[0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1] ?? "") : "";
  return (first.charAt(0) + last.charAt(0)).toUpperCase();
}
