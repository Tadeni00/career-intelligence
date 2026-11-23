/** Official/verified public discovery pages, not a jobs API or scraped dataset.
 *  Visit the original portal to confirm employer, date, terms and apply link.
 */
export const BENIN_LOCAL_SOURCES = [
  {
    name: "ANPE Bénin — official job offers",
    url: "https://sica.anpe.bj/portail-offres",
    note: "Browse national employment notices; check the original details and deadline.",
  },
  {
    name: "ANPE Bénin — SALEC 2026",
    url: "https://salec.anpe.bj/",
    note: "Official employment fair and vacancy directory; verify actual vacancy status and registration requirements.",
  },
  {
    name: "Government of Benin — employment offers",
    url: "https://www.gouv.bj/opportunites/offres-emploi/",
    note: "Official recruitment notices; check eligibility and application instructions.",
  },
  {
    name: "BeninFindJob — Cotonou",
    url: "https://beninfindjob.com/emploi/cotonou",
    note: "Browse published Cotonou listings; verify the workplace and deadline.",
  },
  {
    name: "EmploiBenin",
    url: "https://www.emploibenin.com/",
    note: "Search local job postings in French and English.",
  },
  {
    name: "Trouve Ton Emploi — Benin",
    url: "https://skills.capprafrica.org/fr/offres?pays=BJ",
    note: "Browse Benin vacancies with links to the original announcements.",
  },
  {
    name: "Emplois Bénin",
    url: "https://emploisbenin.bj/",
    note: "Review Benin job announcements and their original application instructions.",
  },
  {
    name: "WabaJob — Benin vacancies",
    url: "https://www.wabajob.com/",
    note: "Browse Benin-listed vacancies; confirm employer, deadline and original application instructions before import.",
  },
  {
    name: "Opportafrik — Cotonou vacancies",
    url: "https://opportafrik.com/benin/cotonou",
    note: "Review Cotonou listings and follow the original employer posting; confirm availability and eligibility.",
  },
] as const;

export function showBeninLocalSources(country: string, remoteOnly: boolean): boolean {
  return country.trim().toLowerCase() === "bj" && !remoteOnly;
}
