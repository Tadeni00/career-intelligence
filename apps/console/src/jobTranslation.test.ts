import { jobEnglishTranslation, TRANSLATION_TEXT_LIMIT } from "./jobTranslation.ts";

const assert = (condition: unknown, message: string) => {
  if (!condition) throw new Error(message);
};

assert(jobEnglishTranslation("") === null, "Empty text should not generate a link");
assert(jobEnglishTranslation("   ") === null, "Whitespace should not generate a link");
const french = "Nous recrutons un analyste de données à Cotonou. Salaire: 500 000 FCFA.";
const result = jobEnglishTranslation(french);
assert(result !== null, "French posting should produce a link");
if (result) {
  const url = new URL(result.url);
  assert(url.protocol === "https:" && url.hostname === "translate.google.com", "Fixed translation host");
  assert(url.searchParams.get("tl") === "en", "English must be target language");
  assert(url.searchParams.get("sl") === "auto", "Source language should be detected");
  assert(url.searchParams.get("text") === french, "French text should be unchanged");
  assert(!result.partial, "Short advert should be complete");
}
const long = jobEnglishTranslation("x".repeat(TRANSLATION_TEXT_LIMIT + 20));
assert(long?.partial === true, "Long advert should be identified as partial");
assert(new URL(long!.url).searchParams.get("text")?.length === TRANSLATION_TEXT_LIMIT, "Bound text length");
console.log("PASS on-demand English job-description translation links");
