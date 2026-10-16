import { expect, test } from "bun:test";
import { chmodSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { add, remove, loadManifest, readManifest, flattenSkills } from "./skill-manager";

const fixture = () => ({ version: 2, deploy_to: ["claude_code", "codex", "grok", "pi"],
  presets: { test: ["keep"] }, sources: [{ ref: "owner/repo", skills: [{ name: "keep" }] }] });

type MockSkill = { name: string; source_type: string; presets: string[]; deployed_to: string[] };
const readState = (path: string): MockSkill[] => JSON.parse(readFileSync(path, "utf8"));

test("Git sources and preset references remain consistent", () => {
  const data = fixture();
  add(data, "https://github.com/owner/git/tree/main/skills/example", "example", ["test"]);
  expect(flattenSkills(data)[0]!.source.ref).toBe("https://github.com/owner/git/tree/main/skills/example");
  remove(data, "example");
  expect(data).toEqual(fixture());
  expect(() => loadManifest({ ...data, presets: { test: ["missing"] } })).toThrow();
  expect(() => add(data, "owner/repo@keep")).toThrow();
});

function sandbox(action: (options: { run: (...args: string[]) => ReturnType<typeof Bun.spawnSync>; file: string; state: string; log: string }) => void, refuse = false) {
  const dir = mkdtempSync(join(tmpdir(), "flora-sync-test-"));
  try {
    const file = join(dir, "manifest.yaml"), state = join(dir, "state.json"), log = join(dir, "calls.jsonl"), cli = join(dir, "cli");
    writeFileSync(file, "# metadata\n" + Bun.YAML.stringify(fixture(), null, 2));
    writeFileSync(state, JSON.stringify([
      { name: "keep", source_type: "skillssh", presets: ["old"], deployed_to: [] },
      { name: "obsolete", source_type: "git", presets: [], deployed_to: [] },
      { name: "internal", source_type: "local", presets: ["private"], deployed_to: ["codex"] },
    ]));
    writeFileSync(cli, `#!${process.execPath}
import {readFileSync,writeFileSync,appendFileSync} from 'node:fs';
let a=process.argv.slice(2); appendFileSync(process.env.FLORA_LOG,JSON.stringify(a)+'\\n');
if(a[0]==='--version'){console.log('test-cli');process.exit(0);}
a=a.slice(1);let rows=JSON.parse(readFileSync(process.env.FLORA_STATE,'utf8'));let out={};
if(a[0]==='skills'&&a[1]==='list')out=rows;
if(a[0]==='skills'&&a[1]==='install')rows.push({name:a[2].split('@').pop(),source_type:'skillssh',presets:[],deployed_to:[]});
if(a[0]==='skills'&&a[1]==='remove'&&!a.includes('--dry-run'))rows=rows.filter(r=>!a.slice(2).includes(r.name));
if(a[0]==='skills'&&a[1]==='deploy'){
 if(a.includes('--dry-run')&&process.env.FLORA_REFUSE==='true')process.exit(7);
 if(!a.includes('--dry-run')){const end=a.indexOf('--agent');const names=a.slice(2,end);const agents=a.filter((v,i)=>a[i-1]==='--agent');for(const r of rows)if(names.includes(r.name))r.deployed_to=[...new Set([...r.deployed_to,...agents])];}
}
if(a[0]==='presets'&&a[1]==='list')out=[...new Set(rows.flatMap(r=>r.presets))].map(name=>({name}));
if(a[0]==='presets'&&a[1]==='add-skill')for(const r of rows)if(a.slice(3).includes(r.name))r.presets=[...new Set([...r.presets,a[2]])];
if(a[0]==='presets'&&a[1]==='remove-skill')for(const r of rows)if(a.slice(3).includes(r.name))r.presets=r.presets.filter(p=>p!==a[2]);
writeFileSync(process.env.FLORA_STATE,JSON.stringify(rows));console.log(JSON.stringify(out));
`);
    chmodSync(cli, 0o755);
    const run = (...args: string[]) => Bun.spawnSync([process.execPath, resolve(import.meta.dir, "skill-manager.ts"),
      ...args, "--file", file, "--cli", cli], { cwd: tmpdir(), env: { ...process.env,
        FLORA_STATE: state, FLORA_LOG: log, FLORA_REFUSE: String(refuse) } });
    action({ run, file, state, log });
  } finally { rmSync(dir, { recursive: true, force: true }); }
}

test("sync removes obsolete skills, preserves local imports, and verifies all targets", () => {
  sandbox(({run, state}) => {
    const result = run("sync");
    expect(result.exitCode).toBe(0);
    const rows = readState(state);
    expect(rows.find(r => r.name === "obsolete")).toBeUndefined();
    expect(rows.find(r => r.name === "internal")?.deployed_to).toEqual(["codex"]);
    expect(rows.find(r => r.name === "keep")?.deployed_to).toEqual(fixture().deploy_to);
    expect(rows.find(r => r.name === "keep")?.presets).toEqual(["test"]);
  });
});

test("add and remove synchronize the manifest and the actual library", () => {
  sandbox(({run, file, state}) => {
    expect(run("add", "owner/repo@added", "--preset", "test").exitCode).toBe(0);
    expect(readManifest(file).presets.test).toContain("added");
    expect(readState(state).find(r=>r.name==='added')?.deployed_to).toEqual(fixture().deploy_to);
    expect(readFileSync(file,"utf8")).toContain("sources:\n  - ref: owner/repo\n");
    expect(run("remove", "added").exitCode).toBe(0);
    expect(flattenSkills(readManifest(file)).map(s=>s.name)).toEqual(["keep"]);
    expect(readState(state).some(r=>r.name==='added')).toBe(false);
    const text=readFileSync(file,"utf8");
    expect(run("remove","missing").exitCode).toBe(1);
    expect(readFileSync(file,"utf8")).toBe(text);
  });
});

test("a conflict prevents deletion and manifest writes", () => {
  sandbox(({run,file,state}) => {
    const before=readFileSync(file,"utf8");
    expect(run("sync").exitCode).toBe(7);
    expect(readState(state).some(r=>r.name==='obsolete')).toBe(true);
    expect(readFileSync(file,"utf8")).toBe(before);
  }, true);
});

test("preview requires no CLI and changes no files", () => {
  sandbox(({run,file,state}) => {
    const before=readFileSync(state,"utf8"),text=readFileSync(file,"utf8");
    expect(run("add","owner/repo@preview","--dry-run").exitCode).toBe(0);
    expect(readFileSync(state,"utf8")).toBe(before);
    expect(readFileSync(file,"utf8")).toBe(text);
  });
});
