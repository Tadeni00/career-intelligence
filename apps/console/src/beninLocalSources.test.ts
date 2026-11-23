import { BENIN_LOCAL_SOURCES, showBeninLocalSources } from "./beninLocalSources.ts";
const assert = {
  equal(actual: unknown, expected: unknown) {
    if (actual !== expected) throw new Error(`Expected ${String(expected)} but got ${String(actual)}`);
  },
  ok(condition: unknown, message = "Assertion failed") {
    if (!condition) throw new Error(message);
  },
};

assert.equal(showBeninLocalSources("bj", false), true);
assert.equal(showBeninLocalSources(" BJ ", false), true);
assert.equal(showBeninLocalSources("bj", true), false);
assert.equal(showBeninLocalSources("ng", false), false);
assert.ok(BENIN_LOCAL_SOURCES.length >= 9);
assert.ok(BENIN_LOCAL_SOURCES.some(source => source.url === "https://www.wabajob.com/"));
assert.ok(BENIN_LOCAL_SOURCES.some(source => source.url === "https://opportafrik.com/benin/cotonou"));

const hosts = new Set<string>();
for (const source of BENIN_LOCAL_SOURCES) {
  const parsed = new URL(source.url);
  assert.equal(parsed.protocol, "https:");
  assert.ok(parsed.hostname, "Source must have a host");
  assert.ok(source.note.length > 20, "Provide a non-promotional verification warning");
  assert.ok(!hosts.has(parsed.hostname), "Sources should be independent sites");
  hosts.add(parsed.hostname);
}
console.log("PASS Benin local source links, independent hosts and remote-mode separation");
