#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const root = path.resolve(__dirname, "..");
const includeDev = process.argv.includes("--dev");
const venvDir = path.join(root, ".venv");
const venvPython = process.platform === "win32"
  ? path.join(venvDir, "Scripts", "python.exe")
  : path.join(venvDir, "bin", "python");

function run(cmd, args, options = {}) {
  const result = spawnSync(cmd, args, {
    cwd: root,
    stdio: "inherit",
    env: { ...process.env, ...options.env },
  });
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  if (result.status !== 0) {
    process.exit(result.status === null ? 1 : result.status);
  }
}

function pythonCandidates() {
  const names = [];
  if (process.env.PYTHON) names.push(process.env.PYTHON);
  names.push("python3.13", "python3.12", "python3.11", "python3.10", "python3", "python");
  return names;
}

function findPython() {
  for (const name of pythonCandidates()) {
    const probe = spawnSync(name, [
      "-c",
      "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)",
    ], { stdio: "ignore" });
    if (probe.status === 0) return name;
  }
  return null;
}

const python = findPython();
if (!python) {
  console.error("ERROR: no Python >= 3.10 found on PATH");
  process.exit(1);
}

if (!fs.existsSync(venvPython)) {
  run(python, ["-m", "venv", venvDir]);
}

const pipEnv = {
  // platform null device: /dev/null is meaningless on Windows
  PIP_CONFIG_FILE: process.platform === "win32" ? "NUL" : "/dev/null",
  PIP_INDEX_URL: process.env.PIP_INDEX_URL || "https://pypi.tuna.tsinghua.edu.cn/simple",
  HOMEBREW_PIP_INDEX_URL: "",
};

run(venvPython, ["-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], {
  env: pipEnv,
});
run(venvPython, [
  "-m",
  "pip",
  "install",
  "--no-build-isolation",
  "-e",
  includeDev ? ".[dev]" : ".",
], {
  env: pipEnv,
});
