/** Official/verified public discovery pages, not a jobs API or scraped dataset.
 *  Visit the original portal to confirm employer, date, terms and apply link.
 */
export const BENIN_LOCAL_SOURCES = [
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
] as const;

export function showBeninLocalSources(country: string, remoteOnly: boolean): boolean {
  return country.trim().toLowerCase() === "bj" && !remoteOnly;
}
