/** "Signing in and your profile" → "signing-in-and-your-profile" (any script). */
export function slug(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-|-$/g, "");
}
