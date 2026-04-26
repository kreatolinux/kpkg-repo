# Kreato Linux Package Repository

Each directory is a package containing `run` (legacy shell) and/or `run3` (Kongue format) runfiles.

## Package Structure

### Legacy `run` format (shell script)
```sh
NAME="package"
VERSION="1.2.3"
RELEASE="1"
SOURCES="https://..."
BUILD_DEPENDS="gmake"
DEPENDS=""
B2SUM="..."  # or SHA256SUM/SHA512SUM
DESCRIPTION="..."

build() { ./configure --prefix=/usr && make; }
package() { make DESTDIR=$ROOT install; }
```

### New `run3` format (Kongue - YAML-like)
```yaml
name: "package"
version: "1.2.3"
release: "1"
sources:
  - "https://..."
sha256sum:
  - "..."
build_depends:
  - "gmake"
depends:
  - "dependency1"

build { macro build --configure; }
package { macro package --configure; }
```

## Kongue Syntax Notes

- Variables: `$var` or `${var}`; methods like `${version.split('.').join('.')}`
- Commands need `exec`: `exec "make install"` (except `cd`, `print`, `env`)
- Functions: `func name { ... }` then call as `name "arg"`
- `macro build --configure/--meson/--cmake/--ninja` simplifies common builds
- `macro package --configure/--meson/--cmake/--ninja` simplifies installation
- `macro extract --autocd=true` for manual extraction control
- `prepare { }` block replaces automatic extraction
- `package_subpkg { }` creates subpackages with different `depends_subpkg`

## Conventions

- Version bumps: update VERSION and checksum (B2SUM/SHA256SUM/SHA512SUM)
- Git sources: use `SKIP` for checksums (e.g., `git::https://...::commit`)
- Cross-compilation: `$KPKG_ARCH` and `$KPKG_TARGET` are set automatically
- Install root: `$ROOT` is the staging directory for `package()`
- Optional deps: `opt_depends: ["pkg: description"]`

## CI

- 5 phases, ~250 packages each
- Pulls latest kpkg/chkupd binaries from kreatolinux/src workflow
- Mounts repo to `/etc/kpkg/repos/main`
- Builds with `kpkg build <pkg> --yes`
- Pushes to S3 (MinIO) on master merges

## Symlinks

- `kpkg -> src` (metapackage)
- `jumpstart -> src` (metapackage)
- `linux-headers -> linux`
- `grub-efi -> grub/`
- Various compat symlinks (webkitgtk3/4, ca-certificates variants)

## Useful Commands

- Checksum update: `scripts/update-sums.mjs` (for run3 files)
