/** A tree name from a file name: "kovalenko_family-2024.ged" → "Kovalenko family 2024". */
export function treeNameFromFile(filename: string): string {
  const base = filename
    .replace(/\.[^.]+$/, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 200);
  return base ? base.charAt(0).toLocaleUpperCase() + base.slice(1) : "GEDCOM";
}
