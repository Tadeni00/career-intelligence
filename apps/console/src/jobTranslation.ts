/** Explicit, user-initiated translation of publicly listed job text.
 * Never sends CV/profile content, never modifies stored job evidence.
 */
export const TRANSLATION_TEXT_LIMIT = 3500;

export function jobEnglishTranslation(text: string): { url: string; partial: boolean } | null {
  const source = text.trim();
  if (!source) return null;
  const excerpt = source.slice(0, TRANSLATION_TEXT_LIMIT);
  const params = new URLSearchParams({
    sl: "auto",
    tl: "en",
    text: excerpt,
    op: "translate",
  });
  return {
    url: `https://translate.google.com/?${params.toString()}`,
    partial: source.length > excerpt.length,
  };
}
