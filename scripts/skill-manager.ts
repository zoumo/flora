#!/usr/bin/env bun
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { parseArgs } from "node:util";

export const manifestPath = resolve(import.meta.dir, "../skill-manager.yaml");
export type Skill = { name: string; path?: string };
export type Source = { ref: string; branch?: string; skills: Skill[] };
export type Manifest = { version: number; deploy_to: string[]; presets: Record<string, string[]>; sources: Source[] };

export function flattenSkills(data: Manifest) {
  return data.sources.flatMap(source => source.skills.map(skill => ({
    ...skill, source: { ref: source.ref.startsWith("https://")
      ? (skill.path ? `${source.ref.replace(/\.git\/?$/, "")}/tree/${source.branch}/${skill.path}` : source.ref)
      : `${source.ref}@${skill.name}` },
  })));
}

export function loadManifest(value: unknown): Manifest {
  const data = value as Manifest | null;
  if (data?.version !== 2 || !Array.isArray(data.sources)) {
    throw new Error("Use manifest version 2 with a sources list.");
  }
  if (!Array.isArray(data.deploy_to) || data.deploy_to.some(
    agent => typeof agent !== "string" || !/^[a-z_]+$/.test(agent),
  ) || new Set(data.deploy_to).size !== data.deploy_to.length) {
    throw new Error("Invalid shared deployment targets.");
  }
  const names = new Set<string>();
  const refs = new Set<string>();
  for (const source of data.sources) {
    if (!source || typeof source.ref !== "string" ||
      !/^(?:[\w.-]+\/[\w.-]+|https:\/\/\S+)$/.test(source.ref) || refs.has(source.ref) ||
      !Array.isArray(source.skills) || !source.skills.length) {
      throw new Error(`Invalid or duplicate source: ${source?.ref}`);
    }
    refs.add(source.ref);
    for (const skill of source.skills) {
      if (!skill || typeof skill.name !== "string" || !/^[\w.-]+$/.test(skill.name) || names.has(skill.name)) {
        throw new Error(`Invalid or duplicate skill name: ${skill?.name}`);
      }
      names.add(skill.name);
      if (skill.path !== undefined && (typeof skill.path !== "string" || !skill.path ||
        skill.path.startsWith("/") || skill.path.split("/").some(part => !part || part === "." || part === "..") ||
        !source.ref.startsWith("https://") || !source.branch)) {
        throw new Error(`Invalid Git skill path or missing branch: ${skill.name}`);
      }
    }
  }
  if (!data.presets || typeof data.presets !== "object" || Array.isArray(data.presets)) {
    throw new Error("presets must map preset names to skill lists.");
  }
  for (const [preset, members] of Object.entries(data.presets)) {
    if (!preset.trim() || !Array.isArray(members) || new Set(members).size !== members.length ||
      members.some(name => typeof name !== "string" || !names.has(name))) {
      throw new Error(`Invalid preset or unknown skill: ${preset}`);
    }
  }
  return data;
}

export function readManifest(path = manifestPath): Manifest {
  return loadManifest(Bun.YAML.parse(readFileSync(path, "utf8")));
}

export function writeManifest(data: Manifest, path = manifestPath): void {
  loadManifest(data);
  const header = readFileSync(path, "utf8").split("\n").filter(line => line.startsWith("#")).join("\n");
  const temp = `${path}.${crypto.randomUUID()}.tmp`;
  try {
    const yaml = Bun.YAML.stringify(data, null, 2)
      .replace(/:\s*\n\s+(\[\]|\{\})(?=\n|$)/g, ": $1")
      .replace(/[ \t]+$/gm, "");
    writeFileSync(temp, `${header ? `${header}\n` : ""}${yaml.trimEnd()}\n`, { flag: "wx" });
    renameSync(temp, path);
  } finally {
    rmSync(temp, { force: true });
  }
}

class CommandError extends Error {
  constructor(public exitCode: number, command: string) {
    super(`Command failed: ${command}`);
  }
}

function run(command: string[], capture = false): string {
  const result = Bun.spawnSync(command, {
    stdin: "inherit", stdout: capture ? "pipe" : "inherit", stderr: "inherit",
  });
  if (result.exitCode !== 0) throw new CommandError(result.exitCode || 1, command[0]!);
  return capture ? (result.stdout?.toString() ?? "") : "";
}

function available(command: string): boolean {
  return !!Bun.which(command) && Bun.spawnSync([command, "--version"]).exitCode === 0;
}

function bootstrapCli(binary: string): void {
  if (available("cargo") && available("rustc")) {
    run(["cargo", "install", "--git", "https://github.com/xingkongliang/skills-manager",
      "--bin", "skills-manager-cli", "--locked", "--root", join(homedir(), ".skills-manager")]);
    return;
  }
  const platform = { darwin: "macOS", linux: "Linux" }[process.platform as string];
  const arch = { arm64: "arm64", x64: "x64" }[process.arch as string];
  if (!platform || !arch) throw new Error("Unsupported operating system or architecture.");
  mkdirSync(dirname(binary), { recursive: true });
  const temp = mkdtempSync(join(dirname(binary), ".download-"));
  const download = join(temp, "skills-manager-cli");
  try {
    const base = "https://gh-proxy.org/https://github.com/xingkongliang/skills-manager/releases/latest/download";
    run(["curl", "--fail", "--location", "--retry", "3",
      `${base}/skills-manager-cli-${platform}-${arch}`, "--output", download]);
    chmodSync(download, 0o755);
    run([download, "--version"]);
    renameSync(download, binary);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
}

function resolveCli(): string {
  const bin = join(homedir(), ".skills-manager/bin");
  const stamp = join(bin, ".version");
  const binary = join(bin, "skills-manager-cli");
  const bridge = existsSync(binary) ? binary : `${binary}.exe`;
  const stamped = existsSync(stamp) && statSync(stamp).size > 0;
  if (stamped && existsSync(bridge) && Bun.which(bridge)) return bridge;
  if (stamped || existsSync(bridge)) {
    throw new Error("Incomplete Skills Manager bridge. Open the Skills Manager app to repair it.");
  }
  const installed = Bun.which("skills-manager-cli");
  if (installed) return installed;
  bootstrapCli(binary);
  return binary;
}

type InstalledSkill = { name: string; source_type: string; presets: string[]; deployed_to: string[] };

export function sync(data: Manifest, binary = resolveCli()): void {
  const cli = (args: string[], capture = false) => run([binary, "--json", ...args], capture);
  const list = (): InstalledSkill[] => JSON.parse(cli(["skills", "list"], true));
  run([binary, "--version"]);
  const skills = flattenSkills(data);
  const wanted = new Set(skills.map(skill => skill.name));
  const before = list();
  const existing = new Set(before.map(skill => skill.name));
  // Local and internal imports have their own lifecycle.
  const obsolete = before.filter(skill => !wanted.has(skill.name) && skill.source_type !== "local").map(skill => skill.name);
  for (const skill of skills) {
    if (!existing.has(skill.name)) cli(["skills", "install", skill.source.ref]);
  }
  const deploy = ["skills", "deploy", ...skills.map(skill => skill.name),
    ...data.deploy_to.flatMap(agent => ["--agent", agent])];
  if (skills.length && data.deploy_to.length) cli([...deploy, "--dry-run"]);
  if (obsolete.length) {
    cli(["skills", "remove", ...obsolete, "--dry-run"]);
    cli(["skills", "remove", ...obsolete, "--yes"]);
  }
  const current = list();
  const presets: { name: string }[] = JSON.parse(cli(["presets", "list"], true));
  const presetNames = new Set(presets.map(preset => preset.name));
  for (const [name, members] of Object.entries(data.presets)) {
    if (!presetNames.has(name)) cli(["presets", "create", name]);
    const missing = members.filter(member => !current.find(skill => skill.name === member)?.presets.includes(name));
    if (missing.length) cli(["presets", "add-skill", name, ...missing]);
  }
  for (const name of presetNames) {
    const extra = current.filter(skill => wanted.has(skill.name) && skill.presets.includes(name) &&
      !data.presets[name]?.includes(skill.name)).map(skill => skill.name);
    if (extra.length) cli(["presets", "remove-skill", name, ...extra]);
  }
  if (skills.length && data.deploy_to.length) cli(deploy);
  const after = list();
  for (const skill of skills) {
    const actual = after.find(row => row.name === skill.name);
    const expectedPresets = Object.entries(data.presets).filter(([, members]) => members.includes(skill.name)).map(([name]) => name).sort();
    if (!actual || data.deploy_to.some(agent => !actual.deployed_to.includes(agent)) ||
      JSON.stringify([...actual.presets].sort()) !== JSON.stringify(expectedPresets)) {
      throw new Error(`Readback failed: ${skill.name}`);
    }
  }
  if (after.some(skill => obsolete.includes(skill.name))) throw new Error("Removed skills remain in the library.");
  console.log(`Synced ${skills.length} skills. Removed ${obsolete.length}. Preserved ${after.filter(skill => !wanted.has(skill.name)).length} local imports.`);
}

export function add(data: Manifest, ref: string, name?: string, presets: string[] = []): void {
  const marketplace = /^([\w.-]+\/[\w.-]+)@([\w.-]+)$/.exec(ref);
  let skill: Skill;
  let sourceRef: string;
  let branch: string | undefined;
  if (marketplace) {
    if (name && name !== marketplace[2]) throw new Error("Marketplace names must match the install ref.");
    skill = { name: marketplace[2]! };
    sourceRef = marketplace[1]!;
  } else {
    if (!ref.startsWith("https://") || !name) throw new Error("Use owner/repo@skill, or an HTTPS Git URL with --name NAME.");
    const url = new URL(ref);
    const [root, tree] = url.pathname.split("/tree/");
    url.pathname = root!.replace(/\.git\/?$/, "").replace(/\/$/, "");
    url.search = "";
    url.hash = "";
    sourceRef = url.href;
    skill = { name };
    if (tree) {
      const [revision, ...parts] = tree.split("/");
      branch = revision;
      if (!parts.length) throw new Error("Use a repository URL or a URL with a skill subdirectory.");
      skill.path = parts.join("/");
    }
  }
  let source = data.sources.find(source => source.ref === sourceRef);
  if (!source) {
    source = { ref: sourceRef, ...(branch ? { branch } : {}), skills: [] };
    data.sources.push(source);
  }
  if (branch && source.branch && branch !== source.branch) throw new Error(`Source uses branch ${source.branch}: ${sourceRef}`);
  if (branch) source.branch = branch;
  source.skills.push(skill);
  source.skills.sort((a, b) => a.name.localeCompare(b.name, "en"));
  data.sources.sort((a, b) => a.ref.localeCompare(b.ref, "en"));
  for (const preset of presets) {
    const members = data.presets[preset] ||= [];
    if (!members.includes(skill.name)) members.push(skill.name);
    members.sort();
  }
  loadManifest(data);
}

export function remove(data: Manifest, name: string): void {
  const source = data.sources.find(source => source.skills.some(skill => skill.name === name));
  if (!source) throw new Error(`Skill not found: ${name}`);
  source.skills = source.skills.filter(skill => skill.name !== name);
  data.sources = data.sources.filter(source => source.skills.length);
  for (const preset of Object.keys(data.presets)) data.presets[preset] = data.presets[preset]!.filter(member => member !== name);
}

function main(): void {
  const { values, positionals } = parseArgs({
    args: process.argv.slice(2), strict: true, allowPositionals: true,
    options: {
      name: { type: "string" }, preset: { type: "string", multiple: true },
      file: { type: "string" }, cli: { type: "string" },
      "dry-run": { type: "boolean" }, help: { type: "boolean", short: "h" },
    },
  });
  if (values.help) {
    console.log("Usage: bun scripts/skill-manager.ts sync [--dry-run]\n       bun scripts/skill-manager.ts add REF [--name NAME] [--preset PRESET]\n       bun scripts/skill-manager.ts remove NAME\nOptions: --file PATH --cli PATH --dry-run");
    return;
  }
  const [command, ref] = positionals;
  if (!command || !["sync", "add", "remove"].includes(command) ||
    positionals.length !== (command === "sync" ? 1 : 2)) throw new Error("Use sync, add REF, or remove NAME. See --help.");
  if (command !== "add" && (values.name || values.preset)) throw new Error("--name and --preset apply to add only.");
  const path = values.file || manifestPath;
  const data = readManifest(path);
  if (command === "add") add(data, ref!, values.name, values.preset);
  if (command === "remove") remove(data, ref!);
  if (values["dry-run"]) {
    for (const source of data.sources) console.log(`${source.ref}: ${source.skills.length}`);
    console.log(`Total: ${flattenSkills(data).length}. Targets: ${data.deploy_to.join(", ") || "library only"}`);
    return;
  }
  sync(data, values.cli || resolveCli());
  if (command !== "sync") writeManifest(data, path);
}

if (import.meta.main) {
  try { main(); }
  catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = error instanceof CommandError ? error.exitCode : 1;
  }
}
