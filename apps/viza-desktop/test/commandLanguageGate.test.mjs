// Phase 34 language-gate test.
//
// VIZA's product boundary (`docs/viza_end_product/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md`
// §5 and §7) is: command-language words like BUY_TO_OPEN / TRIM_LONG / etc.
// are allowed ONLY inside components labelled as simulation/live cards
// (the whitelist lives in `config/viza_command_language_gate.json` on the
// engine side). Free-text prose anywhere else must not contain them.
//
// This test scans the desktop source tree and asserts:
//
// 1. Every command word from the gate file appears only in whitelisted files.
// 2. Always-blocked phrases ("buy AAPL now", "act now", "trade today", …)
//    appear nowhere in the source.
//
// The test is static — it reads files from disk, not a running app — so it
// fails CI before a regression ships rather than at QA time.

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const repoRoot = path.resolve(".", "..", "..");
const desktopRoot = path.resolve(".");
const configPath = path.join(repoRoot, "config", "viza_command_language_gate.json");

const gate = JSON.parse(fs.readFileSync(configPath, "utf-8"));
const whitelist = new Set(gate.whitelisted_component_display_names);
const commandWords = gate.command_words_to_gate;
const alwaysBlocked = gate.always_blocked_phrases;

// File-path → displayName-on-the-whitelist mapping. The convention is:
// a file `Foo.tsx` whose component sets `Foo.displayName = "Foo"` is the
// owner. We accept files whose name (without extension) is in the
// whitelist.
function whitelistedFile(absolutePath) {
  const base = path.basename(absolutePath, ".tsx");
  if (whitelist.has(base)) {
    return true;
  }
  // Source files under src/features/decisions/ that re-export or wrap
  // a whitelisted card are allowed if they import from those cards;
  // we infer that by reading the file and checking for an import.
  // To keep this test simple, anything not explicitly on the whitelist
  // is treated as non-whitelisted.
  return false;
}

function walkTsxFiles(rootDir) {
  const out = [];
  const stack = [rootDir];
  while (stack.length > 0) {
    const current = stack.pop();
    const entries = fs.readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === "node_modules" || entry.name.startsWith(".")) {
          continue;
        }
        stack.push(full);
        continue;
      }
      if (
        entry.isFile() &&
        (full.endsWith(".tsx") || full.endsWith(".ts")) &&
        !full.endsWith(".d.ts")
      ) {
        out.push(full);
      }
    }
  }
  return out;
}

const srcRoot = path.join(desktopRoot, "src");
const desktopFiles = walkTsxFiles(srcRoot);

test("command words appear only in whitelisted components", () => {
  const violations = [];
  for (const file of desktopFiles) {
    const text = fs.readFileSync(file, "utf-8");
    for (const word of commandWords) {
      // Word-boundary match prevents incidental hits in unrelated identifiers.
      const pattern = new RegExp(`\\b${word}\\b`);
      if (!pattern.test(text)) continue;
      if (whitelistedFile(file)) continue;
      // Type definitions (radarTypes.ts) are allowed to reference the
      // CommandKind / Urgency enums by string literal — those are schema
      // types, not user-visible text. Detect by checking whether the
      // matched line is inside a TypeScript string literal in a `type`
      // declaration. Heuristic: if the file path ends with "radarTypes.ts"
      // or "types.ts", allow.
      if (file.endsWith("radarTypes.ts") || file.endsWith("types.ts")) {
        continue;
      }
      violations.push({ file, word });
    }
  }
  assert.deepEqual(
    violations,
    [],
    `Command words found outside whitelisted components: ${JSON.stringify(violations, null, 2)}`,
  );
});

test("always-blocked phrases appear nowhere in desktop source", () => {
  const violations = [];
  for (const file of desktopFiles) {
    const text = fs.readFileSync(file, "utf-8");
    for (const phrase of alwaysBlocked) {
      if (text.toLowerCase().includes(phrase.toLowerCase())) {
        violations.push({ file, phrase });
      }
    }
  }
  assert.deepEqual(
    violations,
    [],
    `Always-blocked phrases found in desktop source: ${JSON.stringify(violations, null, 2)}`,
  );
});

test("the three Phase-27 cards are present", () => {
  // Smoke-check: the components must exist and define a `displayName`
  // matching the whitelist entry. The dispatch in RadarItemList relies on
  // these being importable from the same directory.
  const expected = ["DecisionCommandCard", "BlockedCommandCard", "WatchCommandCard"];
  for (const name of expected) {
    const file = path.join(srcRoot, "features", "decisions", `${name}.tsx`);
    assert.ok(fs.existsSync(file), `expected component file ${file}`);
    const text = fs.readFileSync(file, "utf-8");
    assert.match(text, new RegExp(`${name}\\.displayName\\s*=\\s*"${name}"`));
  }
});

test("the radar mode selector lists three modes", () => {
  const selector = fs.readFileSync(
    path.join(srcRoot, "features", "decisions", "RadarModeSelector.tsx"),
    "utf-8",
  );
  assert.match(selector, /ranking_only/);
  assert.match(selector, /decisions_only/);
  assert.match(selector, /mixed/);
});
