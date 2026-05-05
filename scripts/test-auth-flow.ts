#!/usr/bin/env npx tsx
/**
 * Auth flow connectivity test.
 * Run: npx tsx scripts/test-auth-flow.ts
 * Run with real creds: npx tsx scripts/test-auth-flow.ts --email you@example.com --password yourpassword
 *
 * Tests every HTTP call the login flow makes in the compiled Tauri app.
 * A passing run means the Tauri native HTTP client will also succeed.
 */

const BASE_URL = "https://dailyiq.me";

// ── helpers ──────────────────────────────────────────────────────────────────

const RESET = "\x1b[0m";
const GREEN = "\x1b[32m";
const RED = "\x1b[31m";
const YELLOW = "\x1b[33m";
const BOLD = "\x1b[1m";

let passed = 0;
let failed = 0;

async function test(
  name: string,
  fn: () => Promise<void>
): Promise<void> {
  process.stdout.write(`  ${name} ... `);
  try {
    await fn();
    console.log(`${GREEN}PASS${RESET}`);
    passed++;
  } catch (e) {
    console.log(`${RED}FAIL${RESET}`);
    console.log(`    ${RED}${e instanceof Error ? e.message : String(e)}${RESET}`);
    failed++;
  }
}

function assert(condition: boolean, msg: string): void {
  if (!condition) throw new Error(msg);
}

// ── arg parsing ───────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const getArg = (flag: string) => {
  const idx = args.indexOf(flag);
  return idx !== -1 ? args[idx + 1] : undefined;
};
const testEmail = getArg("--email");
const testPassword = getArg("--password");

// ── tests ─────────────────────────────────────────────────────────────────────

console.log(`\n${BOLD}Auth Flow Tests — ${BASE_URL}${RESET}\n`);

console.log(`${BOLD}1. Endpoint reachability${RESET}`);

await test("dailyiq.me is reachable", async () => {
  const res = await fetch(`${BASE_URL}/`, { signal: AbortSignal.timeout(8000) });
  assert(res.status < 600, `Unexpected status ${res.status}`);
});

console.log(`\n${BOLD}2. terminal-login (POST /api-proxy/auth/terminal-login)${RESET}`);

await test("returns 4xx for invalid credentials (not a network error)", async () => {
  const res = await fetch(`${BASE_URL}/api-proxy/auth/terminal-login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "nobody@doesnotexist.invalid", password: "wrong" }),
    signal: AbortSignal.timeout(10000),
  });
  assert(
    res.status >= 400 && res.status < 600,
    `Expected 4xx/5xx for bad creds, got ${res.status}`
  );
});

await test("response body is valid JSON", async () => {
  const res = await fetch(`${BASE_URL}/api-proxy/auth/terminal-login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "nobody@doesnotexist.invalid", password: "wrong" }),
    signal: AbortSignal.timeout(10000),
  });
  const text = await res.text();
  JSON.parse(text); // throws if invalid
});

if (testEmail && testPassword) {
  console.log(`\n${BOLD}3. terminal-login with real credentials${RESET}`);

  await test(`login succeeds for ${testEmail}`, async () => {
    const res = await fetch(`${BASE_URL}/api-proxy/auth/terminal-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: testEmail, password: testPassword }),
      signal: AbortSignal.timeout(10000),
    });
    const data = await res.json();
    assert(res.ok, `Login failed (${res.status}): ${data?.detail ?? JSON.stringify(data)}`);
    assert(typeof data.api_key === "string" && data.api_key.length > 0, "Missing api_key in response");
    assert(typeof data.email === "string", "Missing email in response");
    assert(typeof data.user_id === "string" || typeof data.user_id === "number", "Missing user_id in response");
    console.log(`    ${YELLOW}role: ${data.role ?? "not set"}${RESET}`);
  });
} else {
  console.log(`\n${YELLOW}  Skipping real-credentials test. Pass --email and --password to include it.${RESET}`);
}

console.log(`\n${BOLD}4. terminal-google-url (GET /api-proxy/auth/terminal-google-url)${RESET}`);

await test("returns 200 with a URL", async () => {
  const res = await fetch(`${BASE_URL}/api-proxy/auth/terminal-google-url`, {
    signal: AbortSignal.timeout(10000),
  });
  assert(res.ok, `Expected 200, got ${res.status}`);
  const data = await res.json();
  assert(typeof data.url === "string" && data.url.startsWith("https://"), `Expected url field, got: ${JSON.stringify(data)}`);
  console.log(`    ${YELLOW}OAuth URL host: ${new URL(data.url).hostname}${RESET}`);
});

console.log(`\n${BOLD}5. terminal-signup (POST /api-proxy/auth/terminal-signup)${RESET}`);

await test("returns 4xx for duplicate/invalid signup (not a network error)", async () => {
  const res = await fetch(`${BASE_URL}/api-proxy/auth/terminal-signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: "Test", email: "nobody@doesnotexist.invalid", password: "short" }),
    signal: AbortSignal.timeout(10000),
  });
  assert(
    res.status >= 400 && res.status < 600,
    `Expected 4xx/5xx, got ${res.status}`
  );
});

// ── summary ───────────────────────────────────────────────────────────────────

const total = passed + failed;
console.log(`\n${"─".repeat(40)}`);
if (failed === 0) {
  console.log(`${GREEN}${BOLD}All ${total} tests passed.${RESET}`);
} else {
  console.log(`${RED}${BOLD}${failed}/${total} tests failed.${RESET}`);
  process.exit(1);
}
