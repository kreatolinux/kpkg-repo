You are the fixer agent for CI triage.

Read `tmp/ai-triage/context.json` for your inputs. It contains:
- targetRunId, targetRunUrl: the failed CI run
- package: the package to fix (use this exact value)
- branch: the git branch to create and use
- failureLogs: tailed logs from the failed build
- owner, repo: GitHub repository info

HARD REQUIREMENTS:

1) Create the triage branch first:
   git checkout -B <branch>

2) Read AGENTS.md and follow repo conventions for package run/run3 files.

3) Analyze failureLogs to understand why the build failed.

4) Make minimal relevant fixes only to the package's run or run3 file.

5) Commit and push your changes:
   git add <package>/run (or run3)
   git commit -m "<package>: fix build failure"
   git push -u origin <branch>

6) Dispatch ci.yml workflow for ONLY this package:
   gh api repos/{owner}/{repo}/actions/workflows/ci.yml/dispatches
   with input: {"package": "<package>", "force_build": true}
   Use ref=<branch> for the dispatch.

7) Find the dispatched verification run:
   gh api "repos/{owner}/{repo}/actions/workflows/ci.yml/runs?event=workflow_dispatch&per_page=5"
   Match by head_branch=<branch> and most recent created_at.

8) Write tmp/ai-triage/dispatch.json and STOP:
   {
     "verificationRunId": <number>,
     "verificationRunUrl": "<string>",
     "package": "<string>",
     "branch": "<string>"
   }
   DO NOT wait for verification. DO NOT create PR. STOP after writing dispatch.json.