import {
  commaSeparatedValues, profileRemoteOnly, profileToDraft,
  profileUpdatePayload, validateProfileDraft,
} from "./profileEditing.ts";
import type { ProfileSummary } from "./types.ts";

function check(label: string, condition: boolean) {
  if (!condition) throw new Error("FAIL: " + label);
  console.log("PASS", label);
}
const summary = {
  id: 1, name: "Sample Candidate", professional_title: "Data Scientist",
  location: "Lagos", summary: "Research and production modelling",
  years_of_experience: 5, minimum_salary: 0,
  preferred_roles: ["Data Scientist", "ML Engineer"],
  preferred_locations: ["Lagos", "Remote"], remote_preference: "REMOTE",
  skills: [{ id: 8, name: "Python" }], experience: [], education: [], projects: [],
} as ProfileSummary;
const draft = profileToDraft(summary);
check("all preferred roles editable before save", draft.preferred_roles === "Data Scientist, ML Engineer");
check("zero salary preserved", draft.minimum_salary === "0");
check("comma values cleaned and deduplicated",
  JSON.stringify(commaSeparatedValues("Data Scientist, , ML Engineer, Data Scientist")) ===
  JSON.stringify(["Data Scientist", "ML Engineer"]));
const payload = profileUpdatePayload(draft);
check("payload contains no relations or identity", !("skills" in payload) && !("id" in payload));
check("payload correctly preserves preferences", payload.preferred_roles.length === 2 &&
  payload.preferred_locations[1] === "Remote" && payload.minimum_salary === 0);
check("blank numeric fields clear values",
  profileUpdatePayload({ ...draft, years_of_experience: "", minimum_salary: "" }).minimum_salary === null);
check("invalid salary blocked", validateProfileDraft({ ...draft, minimum_salary: "USD 100" }) !== null);
check("negative experience blocked", validateProfileDraft({ ...draft, years_of_experience: "-3" }) !== null);
check("blank name blocked", validateProfileDraft({ ...draft, name: " " }) !== null);
check("valid profile accepted", validateProfileDraft(draft) === null);
check("only remote-only maps to provider filter",
  profileRemoteOnly("REMOTE") && !profileRemoteOnly("HYBRID") &&
  !profileRemoteOnly("ONSITE") && !profileRemoteOnly(null));
