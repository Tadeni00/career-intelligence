import {
  MAX_SAVED_SEARCHES, addSavedSearch, parseSavedSearches, validCriteria,
} from "./savedSearches.ts";

function assert(name: string, test: boolean) {
  if (!test) throw new Error("FAIL: " + name);
  console.log("PASS", name);
}
const criteria = {
  query: "Data Scientist", country: "ng", location: "Lagos",
  remoteOnly: true, maxResults: 20,
};
assert("valid criteria accepted", validCriteria(criteria)?.query === criteria.query);
assert("blank query rejected", validCriteria({ ...criteria, query: "  " }) === null);
assert("non-ISO country rejected", validCriteria({ ...criteria, country: "Nigeria" }) === null);
assert("impossible page size rejected", validCriteria({ ...criteria, maxResults: 999 }) === null);
assert("garbled stored payload harmless", parseSavedSearches("{broken").length === 0);
const added = addSavedSearch([], criteria, "preset-1");
assert("explicit saved search records parameters only", added.length === 1 &&
  added[0].remoteOnly && added[0].location === "Lagos" &&
  !("cv_profile_id" in added[0]));
assert("duplicates not inserted", addSavedSearch(added, criteria, "preset-2").length === 1);
assert("saved payload round trips", parseSavedSearches(JSON.stringify(added))[0].query === "Data Scientist");
assert("invalid stored items filtered", parseSavedSearches(JSON.stringify([
  { ...added[0], id: "ok" }, { ...added[0], id: "bad\nkey" },
  { ...added[0], id: "ok" },
])).length === 1);
let presets = added;
for (let n = 0; n < 12; n++) {
  presets = addSavedSearch(presets, { ...criteria, query: "Role " + n }, "preset-" + (n+2));
}
assert("preset cap enforced", presets.length === MAX_SAVED_SEARCHES);
assert("newest explicit preset first", presets[0].query === "Role 11");
