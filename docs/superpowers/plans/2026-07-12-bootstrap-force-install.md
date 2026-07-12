# Bootstrap Force Install Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make automatic bootstrap resolve dependency cycles when the original build uses `--forceInstallAll=true`, without weakening forced resolution for unrelated dependencies.

**Architecture:** Store names of successfully bootstrap-built cycle breakers in `dependencyContext`. While reconstructing a dependency graph in forced mode, treat an installed dependency in that set as satisfied; all other installed dependencies continue to be re-resolved. Change `liblzo2` to select the existing Autotools build macro explicitly.

**Tech Stack:** Nim, kpkg dependency resolver, Nim `unittest`, Kongue run3.

---

## File Structure

- Modify: `/Users/kreato/Sources/personal/src/kpkg/modules/dephandler.nim` - carry bootstrap-satisfied package names through graph resolution and skip only those installed nodes during a forced retry.
- Modify: `/Users/kreato/Sources/personal/src/kpkg/commands/buildcmd.nim` - record each successful automatic bootstrap result before retrying the original build.
- Modify: `/Users/kreato/Sources/personal/src/tests/kpkg/test_dephandler_queue.nim` - cover the installed-dependency skip rule in normal, forced, and bootstrap-satisfied forced cases.
- Modify: `/Users/kreato/Sources/personal/kpkg-repo/liblzo2/run3` - use the Autotools build macro.

### Task 1: Specify Bootstrap-Satisfied Resolver Behavior

**Files:**
- Modify: `/Users/kreato/Sources/personal/src/tests/kpkg/test_dephandler_queue.nim:1-120`

- [ ] **Step 1: Add the failing resolver-policy test and import `sets`**

```nim
import sets

test "forced resolution keeps only bootstrap-satisfied installed dependencies skipped":
  var rootPackages = initHashSet[string]()
  var bootstrapSatisfied = initHashSet[string]()
  bootstrapSatisfied.incl("gobject-introspection")

  check shouldSkipInstalledDependency(true, "noupgrade", "gobject-introspection",
      rootPackages, false, bootstrapSatisfied)
  check not shouldSkipInstalledDependency(true, "noupgrade", "gobject-introspection",
      rootPackages, true, initHashSet[string]())
  check shouldSkipInstalledDependency(true, "noupgrade", "gobject-introspection",
      rootPackages, true, bootstrapSatisfied)
  check not shouldSkipInstalledDependency(true, "noupgrade", "glib",
      rootPackages, true, bootstrapSatisfied)
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `nim c -r tests/kpkg/test_dephandler_queue.nim`

Expected: compilation fails because `shouldSkipInstalledDependency` does not exist.

- [ ] **Step 3: Add the pure installed-dependency policy helper**

In `/Users/kreato/Sources/personal/src/kpkg/modules/dephandler.nim`, after `addEdge`, add:

```nim
proc shouldSkipInstalledDependency*(isInstalled: bool, versionAction: string,
    depName: string, rootPkgNames: HashSet[string], forceInstallAll: bool,
    bootstrapSatisfied: HashSet[string]): bool =
  isInstalled and versionAction != "upgrade" and depName notin rootPkgNames and
    (not forceInstallAll or depName in bootstrapSatisfied)
```

- [ ] **Step 4: Run the focused test to verify the policy**

Run: `nim c -r tests/kpkg/test_dephandler_queue.nim`

Expected: the new test passes, confirming forced mode still resolves ordinary installed packages and skips only successful bootstrap nodes.

### Task 2: Apply The Policy To Dependency Graph Construction

**Files:**
- Modify: `/Users/kreato/Sources/personal/src/kpkg/modules/dephandler.nim:25-37,273-443,581-680,720-800`
- Test: `/Users/kreato/Sources/personal/src/tests/kpkg/test_dephandler_queue.nim`

- [ ] **Step 1: Extend the dependency context with bootstrap-satisfied names**

Add this field to `dependencyContext`:

```nim
bootstrapSatisfied*: HashSet[string]
```

Existing context constructors may omit this field; the default empty `HashSet` preserves their current behavior.

- [ ] **Step 2: Replace both installed-dependency conditions**

For the build dependency loop and the runtime dependency loop, replace each direct `packageExists(...) and ... not ctx.forceInstallAll ...` condition with:

```nim
if shouldSkipInstalledDependency(packageExists(depName, ctx.root), chkVer[0],
    depName, rootPkgNames, ctx.forceInstallAll, ctx.bootstrapSatisfied):
  debug "dephandler: Package '" & depName & "' already installed, skipping"
  continue
```

Keep the existing self-dependency behavior and queueing logic unchanged. This makes the exception apply only before graph edges are added.

- [ ] **Step 3: Preserve the context field while rebuilding the graph**

Add an optional argument to `dephandlerWithGraph`:

```nim
bootstrapSatisfied = initHashSet[string]()
```

Set this field in its `dependencyContext(...)` construction. In
`resolveBuildOrder`, pass `ctx.bootstrapSatisfied` to `dephandlerWithGraph`:

```nim
headRunfileCache = ctx.headRunfileCache,
bootstrapSatisfied = ctx.bootstrapSatisfied)
```

Preserve default behavior for all existing callers.

- [ ] **Step 4: Run the resolver test file**

Run: `nim c -r tests/kpkg/test_dephandler_queue.nim`

Expected: all `dephandler build queue` tests pass.

### Task 3: Mark Successful Automatic Bootstrap Results

**Files:**
- Modify: `/Users/kreato/Sources/personal/src/kpkg/commands/buildcmd.nim:239-293`
- Test: `/Users/kreato/Sources/personal/src/tests/kpkg/test_dephandler_queue.nim`

- [ ] **Step 1: Import `sets` in `buildcmd.nim` if it is not already imported**

Use:

```nim
import sets
```

- [ ] **Step 2: Record only successful bootstrap packages**

Before the `for pkg in pkgsWithBsdeps:` loop, create:

```nim
var bootstrapSatisfied = initHashSet[string]()
```

After the existing nonzero-result guard, add:

```nim
bootstrapSatisfied.incl(pkg)
```

Do not add a name before `bootstrapResult == 0`; a failed bootstrap must still abort without changing retry behavior.

- [ ] **Step 3: Put the successful set on the retry context only**

Immediately before the existing retry call, add:

```nim
depCtx.bootstrapSatisfied = bootstrapSatisfied
```

Keep the existing `resolveBuildOrder(packages, depCtx, false, isInstallDir)` call unchanged. The initial resolution sees the default empty set; only the retry receives the successful bootstrap names.

- [ ] **Step 4: Build kpkg and run the focused resolver tests**

Run: `make kpkg && nim c -r tests/kpkg/test_dephandler_queue.nim`

Expected: kpkg builds and every focused test passes.

### Task 4: Correct The liblzo2 Build Macro

**Files:**
- Modify: `/Users/kreato/Sources/personal/kpkg-repo/liblzo2/run3:12-14`

- [ ] **Step 1: Set the explicit Autotools build macro**

Replace:

```kongue
build {
  macro build 
}
```

with:

```kongue
build {
  macro build --configure
}
```

- [ ] **Step 2: Validate the runfile**

Run: `kpkg run3 validate liblzo2/run3`

Expected: validation succeeds. If the local kpkg does not expose `run3 validate`, build `../src` first and use its run3 validation command; do not modify the recipe further.

### Task 5: Final Regression Verification

**Files:**
- Verify: `/Users/kreato/Sources/personal/src/kpkg/modules/dephandler.nim`
- Verify: `/Users/kreato/Sources/personal/src/kpkg/commands/buildcmd.nim`
- Verify: `/Users/kreato/Sources/personal/kpkg-repo/liblzo2/run3`

- [ ] **Step 1: Run the complete kpkg test target, if available**

Run: `nimble test`

Expected: all kpkg tests pass. If the repository does not define this target, record that fact and retain the passing focused test command from Task 3.

- [ ] **Step 2: Inspect the resulting diffs**

Run: `git diff --check` in both `/Users/kreato/Sources/personal/src` and `/Users/kreato/Sources/personal/kpkg-repo`.

Expected: no whitespace errors; the only kpkg-repo recipe change is `liblzo2/run3`, and the only source changes are the resolver, build command, and focused test.
