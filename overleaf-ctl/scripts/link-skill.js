#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

const root = path.resolve(__dirname, "..");
const skillName = "overleaf-ctl";

function usage() {
  console.log(`Usage: node scripts/link-skill.js [target] [--dry-run]

Targets:
  codex          ${"${CODEX_HOME:-~/.codex}"}/skills/${skillName}
  cc             ${"${CLAUDE_HOME:-~/.claude}"}/skills/${skillName}
  agents         ~/.agents/skills/${skillName}
  legacy-agents  ~/.agents/skills/overleaf-sync
  all            codex + cc + agents

Options:
  --dry-run      Validate target paths without creating links
`);
}

function expandHome(...parts) {
  return path.join(os.homedir(), ...parts);
}

function codexRoot() {
  return process.env.CODEX_HOME
    ? path.resolve(process.env.CODEX_HOME)
    : expandHome(".codex");
}

function claudeRoot() {
  return process.env.CLAUDE_HOME
    ? path.resolve(process.env.CLAUDE_HOME)
    : expandHome(".claude");
}

const targetMap = new Map([
  ["codex", path.join(codexRoot(), "skills", skillName)],
  ["cc", path.join(claudeRoot(), "skills", skillName)],
  ["agents", expandHome(".agents", "skills", skillName)],
  ["legacy-agents", expandHome(".agents", "skills", "overleaf-sync")],
]);

const rawArgs = process.argv.slice(2);
if (rawArgs.includes("-h") || rawArgs.includes("--help")) {
  usage();
  process.exit(0);
}

const dryRun = rawArgs.includes("--dry-run");
const positional = rawArgs.filter((arg) => arg !== "--dry-run");
const targetName = positional[0] || "codex";

if (positional.length > 1 || (!targetMap.has(targetName) && targetName !== "all")) {
  usage();
  process.exit(2);
}

function selectedTargets(name) {
  if (name === "all") {
    return ["codex", "cc", "agents"].map((target) => [target, targetMap.get(target)]);
  }
  return [[name, targetMap.get(name)]];
}

function assertInstallable() {
  for (const relative of ["tools/SKILL.md", "writings/SKILL.md", "tools/overleaf_sync/cli.py"]) {
    if (!fs.existsSync(path.join(root, relative))) {
      throw new Error(`Missing required integration resource: ${relative}`);
    }
  }
  const skillFile = path.join(root, "SKILL.md");
  if (!fs.existsSync(skillFile)) {
    throw new Error(`Missing required SKILL.md: ${skillFile}`);
  }
  const skillText = fs.readFileSync(skillFile, "utf8");
  if (!/^---\n[\s\S]*?\n---\n/.test(skillText)) {
    throw new Error("SKILL.md must start with YAML frontmatter");
  }
  if (!/^name:\s*overleaf-ctl\s*$/m.test(skillText)) {
    throw new Error("SKILL.md frontmatter must contain: name: overleaf-ctl");
  }
  if (!/^description:\s*.+$/m.test(skillText)) {
    throw new Error("SKILL.md frontmatter must contain a description");
  }
}

function linkTarget(label, skillPath) {
  let stat = null;
  try {
    stat = fs.lstatSync(skillPath);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }

  if (stat) {
    const realExisting = fs.realpathSync(skillPath);
    if (realExisting !== root) {
      throw new Error(
        [
          `Refusing to replace existing ${label} skill: ${skillPath}`,
          `Current target: ${realExisting}`,
          `New package:    ${root}`,
          "Move or rename the existing directory first, then rerun this command.",
        ].join("\n")
      );
    }
    console.log(`${dryRun ? "OK" : "Already linked"} ${label}: ${skillPath} -> ${root}`);
    return;
  }

  if (dryRun) {
    console.log(`OK ${label}: ${skillPath} can be linked to ${root}`);
    return;
  }

  fs.mkdirSync(path.dirname(skillPath), { recursive: true });
  fs.symlinkSync(root, skillPath, "dir");
  console.log(`Linked ${label}: ${skillPath} -> ${root}`);
}

try {
  assertInstallable();
  for (const [label, skillPath] of selectedTargets(targetName)) {
    linkTarget(label, skillPath);
  }
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
