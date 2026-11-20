import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

let lock;
try {
  lock = JSON.parse(readFileSync("skills-lock.json", "utf8"));
} catch (error) {
  if (error.code === "ENOENT") {
    console.log("No skills-lock.json; no Matt Pocock skills to uninstall.");
    process.exit(0);
  }
  console.error(`Cannot read skills-lock.json: ${error.message}`);
  process.exit(1);
}

if (!lock?.skills || typeof lock.skills !== "object" || Array.isArray(lock.skills)) {
  console.error("Invalid skills-lock.json: expected a skills object.");
  process.exit(1);
}

const names = Object.entries(lock.skills)
  .filter(([, metadata]) => metadata?.source === "mattpocock/skills")
  .map(([name]) => name);

if (names.length === 0) {
  console.log("No Matt Pocock skills to uninstall.");
  process.exit(0);
}

// Reject option-like names and paths before passing lockfile entries to the CLI.
if (names.some((name) => !/^[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(name))) {
  console.error("Invalid Matt Pocock skill name in skills-lock.json.");
  process.exit(1);
}

const result = spawnSync(
  "npx",
  ["--yes", "skills@latest", "remove", ...names, "--yes"],
  { stdio: "inherit" },
);
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
