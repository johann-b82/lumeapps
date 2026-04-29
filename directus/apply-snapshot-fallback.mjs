#!/usr/bin/env node
// apply-snapshot-fallback.mjs — REST-based metadata sync invoked by
// apply-snapshot-idempotent.sh when `directus schema apply` hits #25760.
//
// Reads the snapshot YAML, extracts top-level collection names + their
// `meta` blocks, then PATCHes /collections/{name} for each so our
// snapshot-defined metadata (note/hidden/singleton/etc.) overlays the
// auto-introspected default metadata Directus created on cold boot.
//
// Uses only Node built-ins (no npm install) so it runs inside the
// directus/directus image as-is. fs + fetch are both available on
// Node 22 which Directus 11.17 ships with.

import { readFileSync } from 'node:fs';

const log = (...args) => console.log('[apply-snapshot-fallback]', ...args);

const snapshotPath = process.argv[2] || process.env.SNAPSHOT_FILE || '/snapshots/v1.22.yaml';
const directusUrl = process.env.DIRECTUS_URL || 'http://directus:8055';
const adminEmail = process.env.DIRECTUS_ADMIN_EMAIL;
const adminPassword = process.env.DIRECTUS_ADMIN_PASSWORD;

if (!adminEmail || !adminPassword) {
  console.error('FATAL: DIRECTUS_ADMIN_EMAIL / DIRECTUS_ADMIN_PASSWORD not set');
  process.exit(3);
}

// Tiny YAML parser tailored to the snapshot's shape: top-level
// `collections:` list of `- collection: <name>` entries each followed by an
// indented `meta:` block. We DO NOT need a full YAML parser — only collection
// names and their meta scalar fields (note, hidden, singleton, icon).
function parseCollections(yaml) {
  const lines = yaml.split('\n');
  const collections = [];
  let inCollections = false;
  let current = null; // { name, meta }
  let inMeta = false;

  for (const raw of lines) {
    if (raw.startsWith('collections:')) { inCollections = true; continue; }
    if (!inCollections) continue;

    // Top-level list entry: "  - collection: <name>"
    const head = raw.match(/^  - collection:\s+(\S+)\s*$/);
    if (head) {
      if (current) collections.push(current);
      current = { name: head[1], meta: {} };
      inMeta = false;
      continue;
    }

    if (!current) continue;

    // Bail out of `collections:` if we hit a different top-level key
    // (e.g. `fields:`, `relations:`).
    if (/^[a-zA-Z]/.test(raw)) {
      if (current) { collections.push(current); current = null; }
      inCollections = false;
      continue;
    }

    if (/^    meta:\s*$/.test(raw)) { inMeta = true; continue; }
    // Any other 4-space key under the collection ends the meta block.
    if (/^    [a-zA-Z]/.test(raw) && !/^    meta:/.test(raw)) { inMeta = false; }

    if (inMeta) {
      const kv = raw.match(/^      ([a-zA-Z_]+):\s*(.*)$/);
      if (kv) {
        const key = kv[1];
        let val = kv[2].trim();
        // Strip surrounding quotes.
        if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1);
        else if (val.startsWith("'") && val.endsWith("'")) val = val.slice(1, -1);
        // Coerce booleans.
        if (val === 'true') val = true;
        else if (val === 'false') val = false;
        current.meta[key] = val;
      }
    }
  }
  if (current) collections.push(current);
  return collections;
}

const yaml = readFileSync(snapshotPath, 'utf8');
const collections = parseCollections(yaml);

if (!collections.length) {
  console.error('FATAL: no top-level collections parsed from', snapshotPath);
  process.exit(4);
}

log(`parsed ${collections.length} collections from ${snapshotPath}`);

const loginRes = await fetch(`${directusUrl}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: adminEmail, password: adminPassword }),
});
if (!loginRes.ok) {
  console.error(`FATAL: admin login failed (${loginRes.status})`);
  console.error(await loginRes.text());
  process.exit(3);
}
const { data: { access_token: token } } = await loginRes.json();

let okCount = 0;
let warnCount = 0;
for (const { name, meta } of collections) {
  const body = {
    meta: {
      collection: name,
      note: meta.note ?? null,
      hidden: meta.hidden ?? false,
      singleton: meta.singleton ?? false,
      ...(meta.icon ? { icon: meta.icon } : {}),
    },
  };
  const res = await fetch(`${directusUrl}/collections/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (res.ok) {
    okCount += 1;
    log(`  ok   PATCH /collections/${name}`);
  } else if (res.status === 403 || res.status === 404) {
    warnCount += 1;
    log(`  warn ${res.status} on /collections/${name} (skipped)`);
  } else {
    const text = await res.text();
    console.error(`  FAIL ${res.status} on /collections/${name}: ${text}`);
    process.exit(5);
  }
}

log(`metadata sync complete: ${okCount} ok, ${warnCount} skipped`);
