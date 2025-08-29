#!/usr/bin/env node
// Update checksum variables (SHA256SUM, SHA512SUM, B2SUM) in kpkg runfiles after version bumps.
// - Parses SOURCES entries
// - Downloads URL sources (http/https) and computes hashes
// - Leaves non-URL/git sources as SKIP
// - Preserves original quoting and variable case when updating

import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import http from 'node:http';
import https from 'node:https';

const repoRoot = process.cwd();

async function* walk(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name === '.git' || entry.name === 'node_modules') continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walk(fullPath);
    } else if (entry.isFile() && entry.name === 'run') {
      yield fullPath;
    }
  }
}

function isUrlSource(token) {
  return /^https?:\/\//i.test(token);
}

function isGitSource(token) {
  // kpkg docs mention git:: schema within SOURCES; treat any token containing 'git::' as git
  return /(^|;)git::/i.test(token);
}

async function fetchHash(url, algo, redirects = 0) {
  if (redirects > 5) throw new Error(`Too many redirects for ${url}`);
  const client = url.startsWith('https:') ? https : http;
  return new Promise((resolve, reject) => {
    const req = client.get(url, { headers: { 'User-Agent': 'kpkg-renovate-checksums' } }, (res) => {
      if (res.statusCode && [301, 302, 303, 307, 308].includes(res.statusCode)) {
        const loc = res.headers.location;
        if (!loc) return reject(new Error(`Redirect with no Location for ${url}`));
        const nextUrl = new URL(loc, url).toString();
        res.resume();
        fetchHash(nextUrl, algo, redirects + 1).then(resolve, reject);
        return;
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`HTTP ${res.statusCode} for ${url}`));
      }
      const hash = crypto.createHash(algo);
      res.on('data', (chunk) => hash.update(chunk));
      res.on('error', reject);
      res.on('end', () => resolve(hash.digest('hex')));
    });
    req.on('error', reject);
    req.setTimeout(120_000, () => {
      req.destroy(new Error(`Timeout fetching ${url}`));
    });
  });
}

function tokenizeSources(value) {
  // SOURCES value can include URLs and local file names, separated by whitespace.
  // Do not split on semicolons so patterns like 'https...;git::...' remain single tokens.
  const parts = value.trim().split(/\s+/).filter(Boolean);
  return parts;
}

function extractVar(content, varName) {
  const re = new RegExp(String.raw`(^|\n)(\s*)(${varName})\s*=\s*(["'])([\s\S]*?)\4`, 'i');
  const m = content.match(re);
  if (!m) return null;
  return { fullMatch: m[0], indent: m[2], key: m[3], quote: m[4], value: m[5], index: m.index };
}

function setVar(content, capture, newValue) {
  const before = content.slice(0, capture.index);
  const after = content.slice(capture.index + capture.fullMatch.length);
  const newlinePrefix = capture.fullMatch.startsWith('\n') ? '\n' : '';
  const updated = `${newlinePrefix}${capture.indent}${capture.key}=${capture.quote}${newValue}${capture.quote}`;
  return before + updated + after;
}

function expandVariables(str, vars) {
  if (!str) return str;
  return str.replace(/\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?/g, (m, name) => {
    const key = String(name).toUpperCase();
    if (Object.prototype.hasOwnProperty.call(vars, key)) return vars[key];
    return m; // leave untouched if unknown
  });
}

function explodeCompositeToken(token) {
  // Allow composite sources like "https://...tar.gz;git::https://..."
  // Split by ';' and return individual parts
  return token.split(';').filter(Boolean);
}

async function processRunFile(filePath) {
  let text = await fs.readFile(filePath, 'utf8');

  // Extract SOURCES line
  const sourcesCap = extractVar(text, 'SOURCES');
  if (!sourcesCap) return false;
  // Gather simple vars to expand within SOURCES
  const vars = {};
  for (const k of ['NAME', 'VERSION', 'RELEASE']) {
    const cap = extractVar(text, k);
    if (cap) vars[k] = cap.value;
  }
  const expandedSources = expandVariables(sourcesCap.value, vars);
  const sourceTokens = tokenizeSources(expandedSources);
  if (sourceTokens.length === 0) return false;

  // Determine which checksum variables exist (update only those present)
  const varsToUpdate = [
    extractVar(text, 'SHA256SUM') && 'SHA256SUM',
    extractVar(text, 'SHA512SUM') && 'SHA512SUM',
    extractVar(text, 'B2SUM') && 'B2SUM',
  ].filter(Boolean);
  if (varsToUpdate.length === 0) return false;

  // Precompute needed algorithms based on present variables
  const algos = new Set();
  if (varsToUpdate.includes('SHA256SUM')) algos.add('sha256');
  if (varsToUpdate.includes('SHA512SUM')) algos.add('sha512');
  if (varsToUpdate.includes('B2SUM')) algos.add('blake2b512');

  // Compute hashes for URL sources; non-URL or git sources become SKIP
  const resultsByAlgo = new Map();
  for (const algo of algos) resultsByAlgo.set(algo, []);

  for (const rawToken of sourceTokens) {
    const parts = explodeCompositeToken(rawToken);
    for (const token of parts) {
      if (isGitSource(token) || !isUrlSource(token)) {
        for (const algo of algos) resultsByAlgo.get(algo).push('SKIP');
        continue;
      }
      for (const algo of algos) {
        try {
          const h = await fetchHash(token, algo);
          resultsByAlgo.get(algo).push(h);
        } catch (_e) {
          console.error(`[checksums] Failed ${token}:`, _e.message);
          // On error, mark as SKIP to avoid blocking Renovate PR creation
          resultsByAlgo.get(algo).push('SKIP');
        }
      }
    }
  }

  let changed = false;
  // Update each present checksum variable
  for (const varName of varsToUpdate) {
    const cap = extractVar(text, varName);
    if (!cap) continue;
    const algo = varName === 'SHA256SUM' ? 'sha256' : varName === 'SHA512SUM' ? 'sha512' : 'blake2b512';
    const newValue = resultsByAlgo.get(algo).join(' ');
    if (cap.value !== newValue) {
      text = setVar(text, cap, newValue);
      changed = true;
    }
  }

  if (changed) {
    await fs.writeFile(filePath, text, 'utf8');
  }
  return changed;
}

async function main() {
  let runFiles = [];
  const args = process.argv.slice(2);
  if (args.length > 0) {
    // Process only the provided runfile path(s)
    for (const p of args) {
      const abs = path.isAbsolute(p) ? p : path.join(repoRoot, p);
      try {
        const st = await fs.stat(abs);
        if (st.isDirectory()) {
          const candidate = path.join(abs, 'run');
          try {
            const st2 = await fs.stat(candidate);
            if (st2.isFile()) runFiles.push(candidate);
            else console.error(`[checksums] Skipping ${abs}: no run file`);
          } catch {
            console.error(`[checksums] Skipping ${abs}: no run file`);
          }
        } else if (st.isFile()) {
          if (path.basename(abs) === 'run') runFiles.push(abs);
          else console.error(`[checksums] Skipping ${abs}: not a run file`);
        }
      } catch (e) {
        console.error(`[checksums] Skipping ${abs}: ${e.message}`);
      }
    }
  } else {
    for await (const f of walk(repoRoot)) runFiles.push(f);
  }

  let updated = 0;
  for (const f of runFiles) {
    try {
      const did = await processRunFile(f);
      if (did) updated += 1;
    } catch (e) {
      // Log and continue
      console.error(`[checksums] Failed ${f}:`, e.message);
    }
  }
  console.log(`[checksums] Updated checksum lines in ${updated} file(s).`);
}

main().catch((e) => {
  console.error('[checksums] Fatal:', e);
  process.exit(1);
});


