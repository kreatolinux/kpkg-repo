# AI CI Triage Runbook

This workflow (`ai-triage.yml`) is a manual recovery path for failed `ci.yml` runs.

It uses OpenCode GitHub Action (`anomalyco/opencode/github@latest`) for fix and verify steps, with a bash-only poll job between them to avoid wasting tokens during CI waiting.

## Trigger

- Workflow: `AI CI Triage`
- Type: `workflow_dispatch` only
- Inputs:
  - `run` (optional): failed `ci.yml` run ID or URL
  - `tail_lines` (optional, default `200`): lines included from failure logs
  - `package` (optional): comma-separated package list (empty = infer from logs)

If `run` is empty, targets latest failed `ci.yml` run.

## Required Secrets

- `ALIBABA_CODING_PLAN_API_KEY`
- `GITHUB_TOKEN` (auto-provided, used via `use_github_token: true`)

## Agent/Model

- Action: `anomalyco/opencode/github@latest`
- Model: `alibaba-coding-plan/glm-5`

## Job Chain

1. **prepare**: Resolve target run, infer packages, read prompt files, prepare context-base.json
2. **fix** (AI, matrix): Checkout, prepare context.json, run fixer agent
   - Agent reads logs-first, makes minimal targeted fixes, commits/pushes, dispatches ci.yml, writes dispatch.json
3. **poll** (bash, matrix): Poll verification run every 180s until completed
   - Timeout: 180 minutes max
   - Writes poll-result.json with status, conclusion, logs
4. **verify** (AI, matrix): Run verifier agent to analyze poll-result.json
   - Writes result.json with verified status
5. **pr** (matrix): Cross-check verification via GitHub API, create PR if verified

## Single Attempt

No retries. If verification fails, workflow exits without PR.

## Outputs

Artifacts per package:
- `triage-context`: run-jobs.json, raw-logs.txt, context-base.json
- `triage-dispatch-{pkg}`: dispatch.json
- `triage-poll-{pkg}`: poll-result.json
- `triage-result-{pkg}`: result.json

## Anti-Hallucination Guardrails

- Fixer prompt mandates logs-first analysis
- Cross-package edits allowed only when logs justify dependency failure
- PR creation workflow-gated, not agent-gated
- Cross-check verifies: conclusion=success, event=workflow_dispatch, path contains ci.yml, branch matches, SHA matches

## Common Failure Modes

- **Package inference failed**: Provide explicit `package` input or increase `tail_lines`
- **No dispatch.json**: Fixer didn't complete fix/dispatch steps - check fixer logs
- **Poll timeout**: CI took >180 min - check verification run status
- **Verification failed**: Check poll-result.json logs field for error details
- **Cross-check mismatch**: Verification run not on correct branch or not ci.yml

## Operator Notes

- Manual-only trigger
- Sequential matrix (`max-parallel: 1`) for multiple packages
- Separate PRs per package
- 180s poll interval, 180min max wait