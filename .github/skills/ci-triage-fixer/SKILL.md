---
name: ci-triage-fixer
description: Use when a user pastes a GitHub Actions run URL from kreatolinux/kpkg-repo, asks you to analyze CI failures, or asks you to fix failed package builds.
---

# CI Triage & Fixer

## Overview

Diagnose and fix failed CI builds from `kreatolinux/kpkg-repo` GitHub Actions runs. Given a run URL, discover all failed packages, analyze their logs via subagents, report findings, and fix `run3` files.

## Workflow

```
Run URL → Extract run ID → gh API for failed jobs
  → Per failed package: dispatch subagent → fetch logs (tail -200) → analyze
  → Synthesize all findings → Report to user
  → (On user prompt) Fix run3 files
```

## Step-by-Step

### Step 1: Extract Run ID

Parse the run ID from the URL or accept a raw numeric ID:

```
https://github.com/kreatolinux/kpkg-repo/actions/runs/26136520887
                                                    └─── RUN_ID ──┘
```

If the user pasted the ID as a number, use it directly.

### Step 2: List Failed Jobs

```bash
gh api repos/kreatolinux/kpkg-repo/actions/runs/<RUN_ID>/jobs --paginate \
  --jq '.jobs[] | select(.conclusion == "failure") | "\(.id)|\(.name)|\(.html_url)"'
```

Output format: `job_id|job_name|job_url`

Extract the **package name** from the job name. The CI matrix uses one package per job, so names look like:

| Job name pattern | Package |
|---|---|
| `build (curl)` | `curl` |
| `build (gtk4)` | `gtk4` |

Extract with: `echo "$job_name" | sed -n 's/.*(\(.*\))/\1/p'`

If no failed jobs, tell the user and stop.

### Step 3: Dispatch Log-Reading Subagents

For each unique failed package, dispatch a **subagent** using the `task` tool with `subagent_type: "general"`. Do NOT fetch logs in the main agent — subagents keep context clean.

**Subagent prompt template:**

```
You are a CI log analyzer for kreatolinux/kpkg-repo.

RUN_ID: <RUN_ID>
JOB_ID: <JOB_ID>
JOB_NAME: <JOB_NAME>
PACKAGE: <PACKAGE_NAME>

## Task

1. Fetch the job logs:
   gh api repos/kreatolinux/kpkg-repo/actions/jobs/<JOB_ID>/logs | tail -200

2. Analyze the failure for the package <PACKAGE_NAME>. Identify:
   - What error occurred (exact error message/exit code)
   - What command or step failed
   - The likely root cause (misconfigured build, missing dep, version mismatch, upstream change, checksum issue, etc.)
   - Whether it's a one-off flake or a deterministic failure

3. Return a STRUCTURED result in this exact format:

PACKAGE: <name>
RESULT: FAIL
ERROR_TYPE: <build_failure|dependency_missing|checksum_mismatch|fetch_failure|test_failure|timeout|unknown>
ERROR_LINE: <the key error line>
ROOT_CAUSE: <1-2 sentence diagnosis>
IS_FLAKE: <true|false>
LOG_TAIL: <last 20 lines of the log for context>

If you cannot find the failure in 200 lines, acknowledge that the tail
may be truncated but report what you can see.
```

Run one subagent per failed package. Wait for all subagents to complete before proceeding.

### Step 4: Synthesize Findings

Collect all subagent results and present a unified report:

```
## CI Failure Report — Run <RUN_ID>
<run_url>

### Failed packages (<N> total)

| Package | Error Type | Root Cause |
|---------|-----------|------------|
| curl    | checksum_mismatch | Upstream tarball changed |
| gtk4    | build_failure     | Missing libepoxy dep |

### Details

**curl:** <ROOT_CAUSE>
**gtk4:** <ROOT_CAUSE>

### Next steps

Tell the user what needs to happen:
- For each package, describe the fix needed
- Note any packages that look like flakes
- Ask if they want you to apply the fixes
```

### Step 5: Apply Fixes (User Prompted)

When the user tells you to fix, modify the package's `run3` file at `<PACKAGE>/run3`.

**What to fix based on error type:**

| Error Type | Likely Fix |
|---|---|
| `checksum_mismatch` | Update checksum in run3 file. Use `scripts/update-sums.mjs <package>` or update manually. |
| `build_failure` | Adjust build/packaging logic or dependencies. May need version bump or build macro change. |
| `dependency_missing` | Add missing package to `depends` or `build_depends` in run3. |
| `fetch_failure` | Fix source URL or add `sha256sum`/`sha512sum`/`b2sum` entry. |
| `version_outdated` | Bump `version` and update checksums. |

**After fixing, validate the run3 file follows AGENTS.md conventions:**
- Commands use `exec` (except `cd`, `print`, `env`)
- `macro build --configure` / `--meson` / `--cmake` / `--ninja` is correct
- Block braces `{ }` are balanced
- YAML-like frontmatter is valid

**CRITICAL:** Only modify `*/run3` files (not legacy `run` files) unless the user explicitly tells you otherwise.

## Quick Reference

```bash
# List failed jobs
gh api repos/kreatolinux/kpkg-repo/actions/runs/<ID>/jobs --paginate \
  --jq '.jobs[] | select(.conclusion == "failure") | "\(.id)|\(.name)"'

# Fetch logs for a single job
gh api repos/kreatolinux/kpkg-repo/actions/jobs/<JOB_ID>/logs | tail -200

# Extract package from job name
echo "build (curl)" | sed -n 's/.*(\(.*\))/\1/p'

# Update checksums
node scripts/update-sums.mjs <package>
```

## Common Mistakes

- **Fetching logs in the main agent.** Always dispatch subagents. One failed job's logs can exceed 1000 lines.
- **Fixing the wrong file.** Default to `run3` files. The legacy `run` files are shell scripts with a different syntax — only modify `run` if the user explicitly says so.
- **Not checking for flakes.** A single package failing after a successful previous build may be a resource issue. Check the run history briefly.
- **Over-fixing.** Make the smallest possible change to fix the failure. Don't refactor the entire run3 file.
- **Ignoring the job name format.** Some phases have names like `build (curl)` where the package is in parentheses. Extract carefully.
- **Forgetting to verify.** After fixing, the user should re-run CI to verify. Mention this.

## References

- `AGENTS.md` — repo conventions for run3 format, dependencies, variables
- `.github/workflows/ci.yml` — the CI workflow that runs these builds
- `.github/workflows/ci-build.yml` — the reusable build job
- `.github/workflows/ci-triage/verifier-subagent.md` — existing verifier prompt for syntax checking
