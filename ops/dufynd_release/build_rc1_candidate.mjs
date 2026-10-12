#!/usr/bin/env node
/**
 * DUFYND RC1: prepare a two-file Rabanne-only source patch against the
 * pinned scentai-mvp commit. Only a disposable Git worktree is changed.
 * No merge, deploy, customer event, merchant access or release authorization.
 */
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const manifestPath = join(root, "ops/dufynd_release/rc1_rabanne_base_overlay.json");

function command(cmd, args, cwd, quiet = true) {
  return execFileSync(cmd, args, {
    cwd,
    encoding: "utf8",
    stdio: quiet ? ["ignore", "pipe", "pipe"] : "inherit",
    maxBuffer: 20 * 1024 * 1024,
  })?.trimEnd() ?? "";
}

function invariant(ok, message) {
  if (!ok) throw new Error(message);
}

function build() {
  const args = process.argv.slice(2);
  invariant(args.includes("--out"), "Specify --out <directory>");
  const outArg = args[args.indexOf("--out") + 1];
  invariant(outArg && !outArg.startsWith("--"), "Invalid --out");
  invariant(args.every((arg, i) => arg === "--build" || arg === "--out" || i === args.indexOf("--out") + 1), "Unsupported option");
  const smokeBuild = args.includes("--build");
  const output = resolve(outArg);
  const relOut = relative(root, output);
  invariant(output !== root && !(relOut === ".git" || relOut.startsWith(".git/")), "Refusing repository metadata as output");
  const plan = JSON.parse(readFileSync(manifestPath, "utf8"));
  invariant(plan.schema_version === 1 && plan.repository === "tncommerce/commerce-agents", "Unrecognized overlay manifest");
  invariant(plan.product_id === "SC-RABANNE-1-MILLION-EDT-100", "Unexpected product");
  invariant(/^[a-f0-9]{40}$/.test(plan.integration_base_sha), "Require immutable base SHA");
  const allowed = plan.allowed_changed_paths;
  invariant(Array.isArray(allowed) && allowed.length === 2, "Expected exactly two source paths");
  invariant(Array.isArray(plan.overlay_files) && plan.overlay_files.length === 2, "Expected exactly two source files");
  invariant(JSON.stringify([...allowed].sort()) === JSON.stringify(plan.overlay_files.map(x => x.path).sort()), "Manifest scope mismatch");
  const base = plan.integration_base_sha;
  command("git", ["cat-file", "-e", base + "^{commit}"], root);
  mkdirSync(output, { recursive: true });

  const scratch = mkdtempSync(join(tmpdir(), "dufynd-rc1-"));
  const candidate = join(scratch, "candidate");
  let added = false;
  try {
    command("git", ["worktree", "add", "--detach", candidate, base], root);
    added = true;
    const verified = [];
    for (const source of plan.overlay_files) {
      const rel = source.path;
      invariant(typeof rel === "string" && !isAbsolute(rel) && !rel.split("/").includes(".."), "Unsafe relative source path");
      invariant(allowed.includes(rel), "Unapproved file: " + rel);
      const location = resolve(candidate, rel);
      invariant(realpathSync(location).startsWith(realpathSync(candidate) + "/"), "Path escapes disposable worktree");
      const blobSha = command("git", ["hash-object", location], candidate);
      invariant(blobSha === source.expected_base_blob_sha, "Pinned base drift: " + rel);
      let text = readFileSync(location, "utf8");
      const counts = [];
      for (const rule of source.edits) {
        const { find, replace } = rule;
        invariant(typeof find === "string" && typeof replace === "string" && find && replace && find !== replace, "Invalid replacement");
        const count = text.split(find).length - 1;
        const expected = find === '        <OfficialProductLink productId={productId} />' ? 2 : 1;
        invariant(count === expected, "Ambiguous " + rel + ": expected " + expected + ", got " + count + " (" + find.slice(0, 48) + ")");
        text = text.split(find).join(replace);
        counts.push(count);
      }
      writeFileSync(location, text, "utf8");
      verified.push({ path: rel, base_blob_sha: blobSha, replacements: counts });
    }
    const changed = command("git", ["diff", "--name-only"], candidate).split("\n").filter(Boolean).sort();
    invariant(JSON.stringify(changed) === JSON.stringify([...allowed].sort()), "Unexpected candidate files: " + changed.join(", "));
    command("git", ["diff", "--check"], candidate);
    const patch = command("git", ["diff", "--binary", "--", ...allowed], candidate);
    invariant(patch.startsWith("diff --git "), "Empty candidate patch");
    const patchBytes = patch + "\n";
    writeFileSync(join(output, "rabanne_rc1_base_bound.patch"), patchBytes);
    const proof = {
      status: "ISOLATED_PATCH_ONLY",
      owner_release_go: false,
      base_sha: base,
      product_id: plan.product_id,
      changed_files: changed,
      verified,
      patch_sha256: createHash("sha256").update(patchBytes).digest("hex"),
      tested_build: false,
      production_mutations: 0,
      merchant_clickouts: 0,
      photo_rights_unresolved: true,
    };
    if (smokeBuild) {
      command("npm", ["ci", "--no-audit", "--no-fund"], join(candidate, "examples"), false);
      command("npm", ["run", "build", "--workspace", "acme-retail-storefront-web"], join(candidate, "examples"), false);
      invariant(existsSync(join(candidate, "examples/retail/storefront-web/out")), "Static storefront build missing");
      proof.tested_build = true;
      proof.status = "BASE_BOUND_BUILD_PASS_RELEASE_STILL_HOLD";
    }
    writeFileSync(join(output, "rabanne_rc1_evidence.json"), JSON.stringify(proof, null, 2) + "\n");
    process.stdout.write(JSON.stringify(proof, null, 2) + "\n");
  } finally {
    if (added) command("git", ["worktree", "remove", "--force", candidate], root);
    rmSync(scratch, { recursive: true, force: true });
  }
}

try {
  build();
} catch (error) {
  process.stderr.write("RC1 NO-GO: " + error.message + "\n");
  process.exitCode = 1;
}
