export interface ProfileSummary {
  id: number;
  name: string;
  professional_title: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  summary: string | null;
  years_of_experience: number | null;
  preferred_roles: string[];
  preferred_locations: string[];
  remote_preference: string | null;
  minimum_salary: number | null;
  skills: CandidateSkill[];
  experience: Experience[];
  education: Education[];
  projects: Project[];
}

export interface CandidateSkill {
  id: number;
  name: string;
  category: string | null;
  proficiency: string | null;
  years_experience: number | null;
  notes: string | null;
}

export interface Experience {
  id: number;
  company: string;
  title: string;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
  is_current: boolean;
}

export interface Education {
  id: number;
  institution: string;
  degree: string | null;
  field: string | null;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
}

export interface Project {
  id: number;
  name: string;
  description: string | null;
  technologies: string[];
  url: string | null;
}

export interface CVDocument {
  id: number;
  candidate_id: number;
  filename: string;
  file_type: string;
  is_master: boolean;
  status: string;
  error_message: string | null;
  uploaded_at: string;
  extracted_at: string | null;
  confirmed_at: string | null;
  text_preview: string | null;
}

export interface CVExtraction {
  id: number;
  cv_id: number;
  confirmed: boolean;
  created_at: string;
  confirmed_at: string | null;
  data: ExtractedCV;
  issues: string[];
  text_length: number;
}

export interface ExtractedCV {
  name: string | null;
  professional_title: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  summary: string | null;
  experience: ExtractedExperience[];
  education: ExtractedEducation[];
  projects: ExtractedProject[];
  skills: ExtractedSkill[];
  certifications: ExtractedCertification[];
  other: string[];
  issues: string[];
}

export interface ExtractedExperience {
  company: string;
  title: string;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
  responsibilities: string[];
  achievements: string[];
  is_current: boolean;
}

export interface ExtractedEducation {
  institution: string;
  degree: string | null;
  field: string | null;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
}

export interface ExtractedProject {
  name: string;
  description: string | null;
  technologies: string[];
  results: string | null;
}

export interface ExtractedSkill {
  name: string;
  category: string | null;
}

export interface ExtractedCertification {
  name: string;
  issuer: string | null;
  date: string | null;
}

export interface Job {
  id: number;
  title: string;
  company: string | null;
  location: string | null;
  url: string | null;
  source: string | null;
  source_id: string | null;
  external_id: string | null;
  is_discovered: boolean;
  description: string | null;
  employment_type: string | null;
  remote_status: string | null;
  salary_min: number | null;
  salary_max: number | null;
  posted_at: string | null;
  created_at: string;
  updated_at: string;
  requirements_extracted: boolean;
  extraction_status: string | null;
  extraction_error_code: string | null;
  requires_review: boolean;
  requirements: JobRequirement[];
  latest_match: MatchSummary | null;
}

export interface JobRequirement {
  id: number;
  requirement_type: string;
  name: string;
  description: string | null;
  importance: string;
  years_required: number | null;
}

export interface MatchSummary {
  id: number;
  job_id: number;
  overall_score: number;
  recommendation: string;
  confidence: number;
  created_at: string;
}

export interface MatchItem {
  category: string;
  name: string;
  detail: string;
  importance: string;
}

export interface MatchResult {
  id: number;
  candidate_id: number;
  job_id: number;
  technical_score: number;
  experience_score: number;
  education_score: number;
  location_score: number;
  other_score: number;
  overall_score: number;
  recommendation: string;
  confidence: number;
  matched_items: MatchItem[];
  gap_items: MatchItem[];
  blocker_items: MatchItem[];
  unknown_items: MatchItem[];
  explanation: string | null;
  /**
   * Which CV profile produced this result.
   * `null` means the shared Candidate record — which is also what every result
   * created before profiles existed carries. Never infer one from the other.
   */
  cv_profile_id: number | null;
  created_at: string;
  job: Job | null;
}

export interface CVAnalysis {
  relevant_experience: string[];
  relevant_skills: string[];
  relevant_projects: string[];
  evidence_to_emphasize: string[];
  content_to_de_emphasize: string[];
  missing_requirements: string[];
  potential_problems: string[];
  recommended_changes: string[];
}

export interface TailoredCV {
  id: number;
  candidate_id: number;
  job_id: number;
  source_cv_id: number | null;
  /** CV profile this document was generated from; null = shared Candidate. */
  cv_profile_id: number | null;
  version: number;
  filename: string;
  storage_path: string;
  summary: string | null;
  analysis: CVAnalysis | null;
  changes_summary: string[];
  validation_status: string;
  validation_issues: { severity: string; code: string; message: string; detail?: string }[];
  created_at: string;
}

export interface CoverLetter {
  id: number;
  candidate_id: number;
  job_id: number;
  content: string;
  /** CV profile this letter was generated from; null = shared Candidate. */
  cv_profile_id: number | null;
  validation_status: string;
  validation_issues: { severity: string; code: string; message: string; detail?: string }[];
  created_at: string;
}

export interface Application {
  id: number;
  candidate_id: number;
  job_id: number;
  match_id: number | null;
  tailored_cv_id: number | null;
  cover_letter_id: number | null;
  /** CV profile this application is tracked under; null = shared Candidate. */
  cv_profile_id: number | null;
  status: string;
  applied_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  job: Job | null;
  tailored_cv: TailoredCV | null;
  cover_letter: CoverLetter | null;
  match: MatchResult | null;
}

export interface JobSearchRequest {
  query: string;
  country: string;
  location?: string;
  remote_only?: boolean;
  max_results?: number;
  /**
   * Match against this confirmed CV profile instead of the shared Candidate
   * record. Omit for the legacy behaviour.
   */
  cv_profile_id?: number;
}

// ------------------------------------------------------------- CV profiles

export type CVProfileStatus =
  | "AWAITING_EXTRACTION"
  | "AWAITING_REVIEW"
  | "CONFIRMED"
  | "EXTRACTION_FAILED";

export interface CVProfileSkill {
  name: string;
  category: string | null;
  proficiency: string | null;
  years_experience: number | null;
}

export interface CVProfileConfirmed {
  name: string | null;
  professional_title: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  summary: string | null;
  years_of_experience: number | null;
  preferred_roles: string[];
  preferred_locations: string[];
  remote_preference: string | null;
  minimum_salary: number | null;
  skills: CVProfileSkill[];
  experience: {
    company: string;
    title: string;
    start_date: string | null;
    end_date: string | null;
    description: string | null;
  }[];
  education: {
    institution: string;
    degree: string | null;
    field: string | null;
    start_date: string | null;
    end_date: string | null;
    description: string | null;
  }[];
  projects: { name: string; description: string | null; technologies: string[] }[];
}

export interface CVProfileOut {
  id: number;
  candidate_id: number;
  cv_id: number | null;
  label: string;
  status: CVProfileStatus;
  error_message: string | null;
  extracted: ExtractedCV | null;
  extracted_issues: string[];
  confirmed: CVProfileConfirmed | null;
  text_length: number;
  /** Set when the profile is retired; it can no longer be used for new work. */
  archived_at: string | null;
  created_at: string;
  updated_at: string;
  extracted_at: string | null;
  confirmed_at: string | null;
}

export interface SearchRelevance {
  label: string;
  reason: string;
}

export interface Freshness {
  status: string;
  reason: string;
}

export interface DuplicateReview {
  status: string;
  reason: string;
  related_job_ids: number[];
}

export interface DiscoveredJobOut {
  job: Job;
  match: MatchResult | null;
  shortlisted: boolean;
  search_relevance: SearchRelevance | null;
  freshness: Freshness | null;
  duplicate_review: DuplicateReview | null;
}

export interface JobSearchResponse {
  jobs: DiscoveredJobOut[];
  total: number;
  query: string;
  country: string;
}

export interface DashboardStats {
  jobs: number;
  strong_matches: number;
  apply: number;
  apply_with_tailoring: number;
  stretch: number;
  skip: number;
  applications: number;
  interviews: number;
  offers: number;
}

export interface DashboardEntry {
  job_id: number;
  title: string;
  company: string | null;
  location: string | null;
  overall_score: number;
  recommendation: string;
  match_id: number | null;
  application_status: string | null;
}

export interface Dashboard {
  stats: DashboardStats;
  opportunities: DashboardEntry[];
  recent_applications: Application[];
  profile_complete: boolean;
  warnings: string[];
}

// ------------------------------------------------------- application strategy (V2)

export interface Strength {
  requirement_id: number | null;
  requirement_name: string;
  evidence_ids: string[];
  statement: string;
  strength: string;
}

export interface StrategyGap {
  requirement_id: number | null;
  requirement_name: string;
  importance: string;
  severity: string;
  statement: string;
}

export interface StrategyBlocker {
  requirement_id: number | null;
  requirement_name: string;
  statement: string;
  severity: string;
}

export interface TransferableEvidence {
  requirement_id: number | null;
  requirement_name: string;
  evidence_ids: string[];
  relationship: string;
  confidence: number;
  statement: string;
}

export interface EvidenceEmphasis {
  evidence_ids: string[];
  statement: string;
  priority: number;
}

export interface ClaimRestriction {
  requirement_id: number | null;
  subject: string;
  statement: string;
  reason: string;
}

export interface StrategyAction {
  priority: number;
  action: string;
  rationale: string;
}

export interface StrategyReviewNote {
  severity: string;
  statement: string;
}

export interface ApplicationStrategy {
  id: number;
  candidate_id: number;
  job_id: number;
  match_id: number | null;
  version: number;
  status: "CURRENT" | "STALE";
  decision: string;
  decision_summary: string;
  strengths: Strength[];
  gaps: StrategyGap[];
  blockers: StrategyBlocker[];
  transferable_evidence: TransferableEvidence[];
  evidence_emphasis: EvidenceEmphasis[];
  claim_restrictions: ClaimRestriction[];
  actions: StrategyAction[];
  review_notes: StrategyReviewNote[];
  created_at: string;
  updated_at: string;
}
