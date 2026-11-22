/**
 * Focused checks for the application-destination rules.
 *
 * Run with:  node src/applicationUrl.test.ts      (no test framework needed)
 * Also type-checked by `tsc -b`, because tsconfig.app.json includes src/.
 */
import {
  applyActionLabel,
  applyActionNote,
  classifyApplicationUrl,
} from "./applicationUrl.ts";

// tsconfig.app.json only loads "vite/client" types, so Node's global is declared
// narrowly here rather than widening the project's compiler options.
declare const process: { exit(code: number): void };

let failures = 0;

function check(name: string, actual: unknown, expected: unknown): void {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) {
    console.log(`  PASS  ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL  ${name}\n          expected ${e}\n          actual   ${a}`);
  }
}

function kind(state: ReturnType<typeof classifyApplicationUrl>): string {
  return state.kind;
}

/** Narrows the union the same way the page does before reading `reason`. */
function reasonOf(state: ReturnType<typeof classifyApplicationUrl>): string {
  return state.kind === "ok" ? "" : state.reason;
}

// ---------------------------------------------------------------- valid URLs

check(
  "an https provider URL is safe to render",
  kind(classifyApplicationUrl("https://job-boards.greenhouse.io/monzo/jobs/8242603")),
  "ok",
);
check(
  "an http provider URL is safe to render",
  kind(classifyApplicationUrl("http://remoteok.com/remote-jobs/abc-1")),
  "ok",
);
check(
  "a URL with a query string and fragment is preserved verbatim",
  classifyApplicationUrl("https://example.com/jobs/9?src=feed#top"),
  { kind: "ok", href: "https://example.com/jobs/9?src=feed#top" },
);
check(
  "surrounding whitespace is trimmed before parsing",
  classifyApplicationUrl("  https://example.com/jobs/1  "),
  { kind: "ok", href: "https://example.com/jobs/1" },
);
check(
  "an explicit default port is kept, not rewritten",
  classifyApplicationUrl("https://example.com:443/jobs/1"),
  { kind: "ok", href: "https://example.com:443/jobs/1" },
);

// -------------------------------------------------------------- missing URLs

check("a null url is missing", kind(classifyApplicationUrl(null)), "missing");
check("an undefined url is missing", kind(classifyApplicationUrl(undefined)), "missing");
check("an empty string is missing", kind(classifyApplicationUrl("")), "missing");
check("a whitespace-only url is missing", kind(classifyApplicationUrl("   ")), "missing");
check(
  "a missing url explains itself",
  reasonOf(classifyApplicationUrl(null)),
  "No application link was provided by the job source.",
);

// --------------------------------------------------------------- unsafe URLs

check(
  "a javascript: scheme is refused",
  kind(classifyApplicationUrl("javascript:alert(1)")),
  "unsafe",
);
check(
  "a data: scheme is refused",
  kind(classifyApplicationUrl("data:text/html,<script>alert(1)</script>")),
  "unsafe",
);
check(
  "a file: scheme is refused",
  kind(classifyApplicationUrl("file:///etc/passwd")),
  "unsafe",
);
check(
  "a relative path is refused",
  kind(classifyApplicationUrl("/jobs/1")),
  "unsafe",
);
check(
  "a bare host with no scheme is refused",
  kind(classifyApplicationUrl("example.com/jobs/1")),
  "unsafe",
);
check(
  "free text is refused",
  kind(classifyApplicationUrl("see the careers page")),
  "unsafe",
);
check(
  "an unsafe url names the scheme it refused",
  reasonOf(classifyApplicationUrl("javascript:alert(1)")).includes("javascript:"),
  true,
);
check(
  "an unsafe url never yields an href",
  "href" in (classifyApplicationUrl("javascript:alert(1)") as object),
  false,
);
check(
  "an unsafe url never yields an href for a relative path",
  "href" in (classifyApplicationUrl("/jobs/1") as object),
  false,
);

// -------------------------------------------------------------------- labels

check("a short employer is named in the label", applyActionLabel("Monzo"), "Apply on Monzo's site");
check("a missing employer falls back to Apply", applyActionLabel(null), "Apply");
check("a blank employer falls back to Apply", applyActionLabel("   "), "Apply");
check("an undefined employer falls back to Apply", applyActionLabel(undefined), "Apply");
check(
  "a long employer collapses to Apply",
  applyActionLabel("International Business Machines Corporation"),
  "Apply",
);
check(
  "a 20-character employer is still named",
  applyActionLabel("Acme Global Holdings"),
  "Apply on Acme Global Holdings's site",
);

// --------------------------------------------------------------------- notes

check(
  "the note names the employer and the source",
  applyActionNote("Monzo", "Greenhouse").includes("Monzo's site (via Greenhouse)"),
  true,
);
check(
  "the note disclaims submitting on the user's behalf",
  applyActionNote("Monzo", "Greenhouse").includes("never submits applications on your behalf"),
  true,
);
check(
  "the note opens in a new tab",
  applyActionNote("Monzo", "Greenhouse").includes("in a new tab"),
  true,
);
check(
  "a missing employer still produces a readable note",
  applyActionNote(null, null),
  "Opens the original vacancy on the employer's site in a new tab. You read the posting and submit the application there; Career Intelligence never submits applications on your behalf.",
);
check(
  "a missing source does not emit an empty via clause",
  applyActionNote("Monzo", null).includes("()"),
  false,
);

// ------------------------------------------- no URL is ever constructed here

check(
  "the helper never synthesises a URL from title or employer",
  classifyApplicationUrl(null).kind === "ok",
  false,
);

if (failures > 0) {
  console.log(`\n${failures} application-URL check(s) failed.`);
  process.exit(1);
}
console.log("\nAll application-URL checks passed.");