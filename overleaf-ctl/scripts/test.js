#!/usr/bin/env node
"use strict";
const path = require("path");
const {spawnSync} = require("child_process");
const root = path.resolve(__dirname, "..");
const python = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const result = spawnSync(python, ["-m", "pytest", "-q", ...process.argv.slice(2)], {cwd: root, stdio: "inherit"});
if (result.error) console.error("Run npm run setup:dev first; tests do not install dependencies automatically.");
process.exit(result.status === null ? 1 : result.status);
