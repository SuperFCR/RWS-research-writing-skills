#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const root = path.resolve(__dirname, "..");
const venvPython = process.platform === "win32"
  ? path.join(root, ".venv", "Scripts", "python.exe")
  : path.join(root, ".venv", "bin", "python");

function pythonCandidates() {
  const names = [];
  if (process.env.PYTHON) names.push(process.env.PYTHON);
  names.push("python3.14", "python3.13", "python3.12", "python3.11", "python3.10", "python3", "python");
  return names;
}

function findSystemPython() {
  for (const name of pythonCandidates()) {
    const probe = spawnSync(name, [
      "-c",
      "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)",
    ], { stdio: "ignore" });
    if (probe.status === 0) return name;
  }
  return null;
}

function pythonEnv() {
  const env = { ...process.env };
  env.PYTHONPATH = env.PYTHONPATH ? `${path.join(root, "tools")}${path.delimiter}${env.PYTHONPATH}` : path.join(root, "tools");
  return env;
}

// A system interpreter may lack click/rich (fresh `npm install`, no .venv yet).
// Without this preflight the user gets a bare ModuleNotFoundError instead of
// an actionable hint.
function hasDeps(python) {
  const probe = spawnSync(
    python,
    ["-c", "import click, rich, overleaf_sync"],
    { stdio: "ignore", env: pythonEnv() },
  );
  return probe.status === 0;
}

function runPython(python) {
  const result = spawnSync(
    python,
    [
      "-c",
      "import sys; sys.argv[0] = 'overleaf-ctl'; from overleaf_sync.cli import main; main()",
      ...process.argv.slice(2),
    ],
    { stdio: "inherit", env: pythonEnv() },
  );
  if (result.error) {
    console.error(`failed to launch overleaf-ctl CLI: ${result.error.message}`);
    process.exit(1);
  }
  if (result.signal) {
    console.error(`overleaf-ctl: Python process terminated by signal ${result.signal}`);
    process.exit(1);
  }
  process.exit(result.status === null ? 1 : result.status);
}

if (fs.existsSync(venvPython)) {
  if (!hasDeps(venvPython)) {
    console.error("overleaf-ctl: .venv exists but its dependencies are incomplete. Run npm run setup.");
    process.exit(1);
  }
  runPython(venvPython);
}

const fallback = findSystemPython();
if (fallback) {
  if (!hasDeps(fallback)) {
    console.error("overleaf-ctl: Python dependencies missing (click/rich) — the bundled .venv is not set up yet.");
    console.error(`Run: cd ${root} && npm run setup`);
    process.exit(1);
  }
  runPython(fallback);
}

console.error("overleaf-ctl requires Python >= 3.10.");
console.error(`Run: cd ${root} && npm run setup`);
process.exit(1);
