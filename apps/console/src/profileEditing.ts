import type { ProfileSummary } from "./types";

export type ProfileDraft = {
  name: string;
  professional_title: string;
  location: string;
  summary: string;
  years_of_experience: string;
  minimum_salary: string;
  preferred_roles: string;
  preferred_locations: string;
  remote_preference: string;
};

export function profileToDraft(profile: ProfileSummary): ProfileDraft {
  return {
    name: profile.name ?? "",
    professional_title: profile.professional_title ?? "",
    location: profile.location ?? "",
    summary: profile.summary ?? "",
    years_of_experience: profile.years_of_experience == null ? "" : String(profile.years_of_experience),
    minimum_salary: profile.minimum_salary == null ? "" : String(profile.minimum_salary),
    preferred_roles: profile.preferred_roles.join(", "),
    preferred_locations: profile.preferred_locations.join(", "),
    remote_preference: profile.remote_preference ?? "",
  };
}

export function commaSeparatedValues(raw: string): string[] {
  return [...new Set(raw.split(",").map((value) => value.trim()).filter(Boolean))];
}

export function validateProfileDraft(draft: ProfileDraft): string | null {
  if (!draft.name.trim()) return "Name cannot be empty.";
  if (draft.years_of_experience.trim()) {
    const years = Number(draft.years_of_experience);
    if (!Number.isFinite(years) || years < 0 || years > 100) {
      return "Years of experience must be between 0 and 100.";
    }
  }
  if (draft.minimum_salary.trim()) {
    const salary = Number(draft.minimum_salary);
    if (!Number.isFinite(salary) || salary < 0) {
      return "Minimum salary must be a non-negative number.";
    }
  }
  if (!["", "REMOTE", "HYBRID", "ONSITE", "ANY"].includes(draft.remote_preference)) {
    return "Choose a supported work arrangement.";
  }
  if (draft.preferred_roles.length > 2000 || draft.preferred_locations.length > 2000) {
    return "Preferred roles and locations are too long.";
  }
  return null;
}

/** Submit only editable fields, not profile relations, IDs, or stale CV data. */
export function profileUpdatePayload(draft: ProfileDraft) {
  return {
    name: draft.name.trim(),
    professional_title: draft.professional_title.trim() || null,
    location: draft.location.trim() || null,
    summary: draft.summary.trim() || null,
    years_of_experience: draft.years_of_experience.trim() ? Number(draft.years_of_experience) : null,
    minimum_salary: draft.minimum_salary.trim() ? Number(draft.minimum_salary) : null,
    preferred_roles: commaSeparatedValues(draft.preferred_roles),
    preferred_locations: commaSeparatedValues(draft.preferred_locations),
    remote_preference: draft.remote_preference || null,
  };
}

/** Only REMOTE can be faithfully expressed by the discovery provider's boolean flag. */
export function profileRemoteOnly(preference: string | null | undefined): boolean {
  return preference === "REMOTE";
}
