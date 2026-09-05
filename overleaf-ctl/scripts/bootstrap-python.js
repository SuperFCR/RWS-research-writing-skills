#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const root = path.resolve(__dirname, "..");
const venvPython = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const candidates = [venvPython, process.env.PYTHON,
  "python3.14", "python3.13", "python3.12", "python3.11", "python3.10", "python3", "python"].filter(Boolean);
const python = candidates.find(candidate => spawnSync(candidate,
  ["-c", "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)"],
  {stdio: "ignore"}).status === 0);
if (!python) {
  console.error("Python >= 3.10 is required. Set PYTHON to its executable or use scripts/install.py directly.");
  process.exit(1);
}
const result = spawnSync(python, [path.join(root, "scripts/install.py"), ...process.argv.slice(2)],
  {cwd: root, stdio: "inherit"});
if (result.error) console.error(result.error.message);
process.exit(result.status === null ? 1 : result.status);
