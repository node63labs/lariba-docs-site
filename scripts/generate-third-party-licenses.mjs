import fs from "node:fs";
import crypto from "node:crypto";

const REPOSITORY = "lariba-docs-site";
const CONTRACT = "NODE63_S3C3_NPM_LOCKFILE_V2";

const mode = process.argv[2];

if (mode !== "--write" && mode !== "--check") {
  console.error("usage: generate-third-party-licenses.mjs --write|--check");
  process.exit(2);
}

const packageJsonPath = new URL("../package.json", import.meta.url);
const lockPath = new URL("../package-lock.json", import.meta.url);
const inventoryPath = new URL("../THIRD_PARTY_LICENSES.json", import.meta.url);

const packageJsonRaw = fs.readFileSync(packageJsonPath);
const lockRaw = fs.readFileSync(lockPath);

const pkg = JSON.parse(packageJsonRaw.toString("utf8"));
const lock = JSON.parse(lockRaw.toString("utf8"));

if (lock.lockfileVersion !== 3) {
  throw new Error(`unsupported lockfileVersion=${lock.lockfileVersion}`);
}

if (!lock.packages || !lock.packages[""]) {
  throw new Error("package-lock packages authority missing");
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function sortedKeys(value) {
  return Object.keys(value ?? {}).sort();
}

function sameArray(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

const packageHash = sha256(packageJsonRaw);
const lockHash = sha256(lockRaw);

const sourceAuthority = sha256(
  Buffer.from(`${packageHash}\n${lockHash}\n${CONTRACT}\n`)
);

const pkgProd = [...new Set([
  ...sortedKeys(pkg.dependencies),
  ...sortedKeys(pkg.optionalDependencies),
])].sort();

const pkgDev = sortedKeys(pkg.devDependencies);

const root = lock.packages[""];

const lockProd = [...new Set([
  ...sortedKeys(root.dependencies),
  ...sortedKeys(root.optionalDependencies),
])].sort();

const lockDev = sortedKeys(root.devDependencies);

if (!sameArray(pkgProd, lockProd)) {
  throw new Error("package.json production authority differs from package-lock root");
}

if (!sameArray(pkgDev, lockDev)) {
  throw new Error("package.json development authority differs from package-lock root");
}

const directProd = new Set(pkgProd);
const directDev = new Set(pkgDev);

function installedName(packagePath) {
  const marker = "node_modules/";
  const index = packagePath.lastIndexOf(marker);

  return index === -1
    ? packagePath
    : packagePath.slice(index + marker.length);
}

function resolvedName(installed, meta) {
  if (typeof meta.name === "string" && meta.name.trim()) {
    return meta.name.trim();
  }

  return installed;
}

function normalizeLicense(value) {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }

  if (Array.isArray(value) && value.length) {
    return value.map(String).sort().join(" OR ");
  }

  return "UNKNOWN";
}

function reviewReason(license) {
  const normalized = license.trim().toUpperCase();

  if (normalized === "UNKNOWN") return "LICENSE_METADATA_MISSING";
  if (normalized === "UNLICENSED") return "LICENSE_METADATA_UNLICENSED";
  if (normalized === "NONE") return "LICENSE_METADATA_NONE";
  if (normalized === "*") return "LICENSE_METADATA_AMBIGUOUS";

  if (normalized.startsWith("SEE LICENSE IN")) {
    return "LICENSE_REFERENCE_REQUIRES_REVIEW";
  }

  return null;
}

const entries = [];

for (const [packagePath, meta] of Object.entries(lock.packages)) {
  if (packagePath === "") continue;
  if (!meta || typeof meta !== "object") continue;
  if (meta.link === true) continue;

  const name = installedName(packagePath);
  const resolved = resolvedName(name, meta);
  const license = normalizeLicense(meta.license);
  const reason = reviewReason(license);

  const topLevel = packagePath === `node_modules/${name}`;

  let relationship = "TRANSITIVE";
  let dependencyScope =
    meta.dev === true ? "DEVELOPMENT" : "PRODUCTION";

  if (topLevel && directProd.has(name)) {
    relationship = "DIRECT";
    dependencyScope = "PRODUCTION";
  } else if (topLevel && directDev.has(name)) {
    relationship = "DIRECT";
    dependencyScope = "DEVELOPMENT";
  }

  entries.push({
    name,
    resolved_name: resolved,
    alias: name === resolved ? null : name,
    version: typeof meta.version === "string"
      ? meta.version
      : "UNKNOWN",
    package_path: packagePath,
    relationship,
    dependency_scope: dependencyScope,
    optional: meta.optional === true,
    license,
    review_required: reason !== null,
    review_reason: reason,
  });
}

entries.sort((a, b) =>
  a.name.localeCompare(b.name) ||
  a.version.localeCompare(b.version) ||
  a.package_path.localeCompare(b.package_path)
);

const counts = {
  total_entries: entries.length,
  direct_production: entries.filter(
    x => x.relationship === "DIRECT" &&
         x.dependency_scope === "PRODUCTION"
  ).length,
  direct_development: entries.filter(
    x => x.relationship === "DIRECT" &&
         x.dependency_scope === "DEVELOPMENT"
  ).length,
  transitive_production: entries.filter(
    x => x.relationship === "TRANSITIVE" &&
         x.dependency_scope === "PRODUCTION"
  ).length,
  transitive_development: entries.filter(
    x => x.relationship === "TRANSITIVE" &&
         x.dependency_scope === "DEVELOPMENT"
  ).length,
  optional_entries: entries.filter(x => x.optional).length,
  aliases: entries.filter(x => x.alias !== null).length,
  review_required: entries.filter(x => x.review_required).length,
};

const inventory = {
  schema: "node63.third-party-license-inventory.v1",
  repository: REPOSITORY,
  source_authority: `sha256:${sourceAuthority}`,
  generator_contract: CONTRACT,

  source: {
    package_json: "package.json",
    package_json_sha256: packageHash,
    package_lock: "package-lock.json",
    package_lock_sha256: lockHash,
    package_lock_version: lock.lockfileVersion,
  },

  declarations: {
    direct_production: pkgProd,
    direct_development: pkgDev,
  },

  policy: {
    inventory_scope: [
      "DIRECT_PRODUCTION",
      "DIRECT_DEVELOPMENT",
      "TRANSITIVE_PRODUCTION",
      "TRANSITIVE_DEVELOPMENT",
    ],
    declaration_identity: "INSTALLED_PACKAGE_NAME",
    resolved_package_identity: "LOCKFILE_METADATA_NAME",
    aliases: "PRESERVED_AS_DISTINCT_DECLARATIONS",
    legal_allowlist_evaluation: "OUT_OF_SCOPE_FOR_S3C3",
    missing_or_ambiguous_metadata: "REVIEW_REQUIRED",
    workspace_link_entries: "EXCLUDED",
  },

  counts,
  entries,
};

const rendered = JSON.stringify(inventory, null, 2) + "\n";

if (mode === "--write") {
  fs.writeFileSync(inventoryPath, rendered);
  console.log(`inventory_written=${inventoryPath.pathname}`);
  console.log(`entries=${counts.total_entries}`);
  console.log(`review_required=${counts.review_required}`);
  process.exit(0);
}

if (!fs.existsSync(inventoryPath)) {
  console.error("tracked inventory missing");
  process.exit(10);
}

const tracked = fs.readFileSync(inventoryPath, "utf8");

if (tracked !== rendered) {
  console.error("tracked third-party license inventory is stale");
  process.exit(11);
}

console.log("LICENSE_INVENTORY_CURRENT=PASS");
console.log(`entries=${counts.total_entries}`);
console.log(`review_required=${counts.review_required}`);
