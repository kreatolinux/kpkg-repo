# Bootstrap With Forced Dependency Resolution

## Goal

Allow CI builds that use `--forceInstallAll=true` to recover from dependency
cycles that kpkg can break with `bootstrap_depends`.

## Scope

- Update `../src` so automatic bootstrap records the packages that were built
  successfully to break a detected cycle.
- Preserve `forceInstallAll` for the original build and its retry.
- During that retry, prevent only the successful bootstrap cycle breakers from
  being re-expanded into the same dependency cycle.
- Update `liblzo2/run3` to explicitly use its Autotools `configure` build.

## Design

`kpkg build` detects a cycle, identifies cycle nodes with
`bootstrap_depends`, builds those nodes in bootstrap mode, then retries the
original build. With `forceInstallAll=true`, the retry currently resolves all
already installed dependencies again, including the bootstrap-built cycle
nodes, and recreates the cycle.

The dependency resolver will accept an explicit set of bootstrap-satisfied
packages for a forced retry. It will preserve normal forced dependency
resolution, but treat only those nodes as already satisfied while building the
retry graph. This confines the exception to the proven cycle breakers instead
of weakening forced resolution for unrelated dependencies.

## Verification

- Add or update a focused kpkg test that resolves the
  `gobject-introspection -> glib -> gobject-introspection` cycle with forced
  installation enabled and bootstrap metadata present.
- Confirm the test fails before the resolver change and succeeds afterward.
- Run the relevant kpkg test suite.
- Validate `liblzo2/run3` syntax and run the targeted CI packages again.
