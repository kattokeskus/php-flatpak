# PHP SDK extensions for org.freedesktop.Sdk

PHP, Composer and PHP extensions as `org.freedesktop.Sdk//25.08` extensions,
for developing and packaging PHP applications with Flatpak.

| Package | |
| --- | --- |
| `org.freedesktop.Sdk.Extension.kattokeskus-php84`, `-php85` | PHP 8.4, 8.5 |
| `org.freedesktop.Sdk.Extension.kattokeskus-composer` | Composer, runs on the enabled PHP |
| `org.freedesktop.Sdk.Extension.kattokeskus-php84-<ext>`, `-php85-<ext>` | an extension |

Extensions: apcu, bcmath, bz2, calendar, dba, enchant, exif, ffi, ftp, gd,
gettext, gmp, imagick, intl, ldap, mysqli, pcntl, pdo_dblib, pdo_firebird,
pdo_mysql, pdo_odbc, pdo_pgsql, pgsql, redis, shmop, snmp, soap, sockets, sodium,
spx, sysvmsg, sysvsem, sysvshm, tidy, vips, xdebug, xhprof, xsl, zip. pdo,
pdo_sqlite, opcache and the other common extensions are built into PHP. No
imap: its c-client library is unmaintained.

## Usage

```sh
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak remote-add --if-not-exists kattokeskus-php https://kattokeskus.github.io/php-flatpak/kattokeskus-php.flatpakrepo
flatpak install kattokeskus-php org.freedesktop.Sdk.Extension.kattokeskus-php84//25.08
```

IDE (VS Code, GNOME Builder) - the PHP package picks up every installed
extension package:

```
FLATPAK_ENABLE_SDK_EXT=kattokeskus-php84,kattokeskus-composer
KATTOKESKUS_PHP84_DISABLE="xdebug,spx"     # optional: leave some out
```

App manifest:

```yaml
sdk-extensions:
  - org.freedesktop.Sdk.Extension.kattokeskus-php84
  - org.freedesktop.Sdk.Extension.kattokeskus-php84-mysqli
build-options:
  append-path: /usr/lib/sdk/kattokeskus-php84/bin
build-commands:
  - /usr/lib/sdk/kattokeskus-php84/install.sh   # PHP at runtime: copies it into /app
```

A bundle installs without a repository: `flatpak install --user <id>-<arch>.flatpak`.
vips is libvips for the [php-vips](https://github.com/libvips/php-vips)
Composer package and needs the ffi package as well.

## Building

```sh
flatpak install flathub org.freedesktop.Sdk//25.08

./build.sh                                                  # every package
./build.sh org.freedesktop.Sdk.Extension.kattokeskus-php84  # just these
INSTALL=1 ./build.sh                                        # and install --user
TESTS=0 ./build.sh                                          # without test suites
BUNDLES=bundles ./build.sh                                  # and bundles/<id>-<arch>.flatpak
```

Needs python3 and flatpak-builder (else it runs `org.flatpak.Builder`; from
VS Code's terminal once: `flatpak override --user
--talk-name=org.freedesktop.Flatpak com.visualstudio.code`). Extension
packages build against the installed PHP package: use `INSTALL=1`. It builds
for the host's architecture; CI builds each one in `arches`.

## CI

Results are images `ghcr.io/kattokeskus/php-flatpak/<name>` holding the bundles
of every architecture (the same for each platform), tagged
`build-<fingerprint>`; a package whose tag exists is not built again. The
fingerprint (`./generate.py --plan`) covers the manifest with its source
checksums, local files, the architectures and the packages it builds against.
On main they also get `8.4.26`, `6.3.0-php8.4.26` (PECL), `2.9.3` (Composer)
and `latest`.

[build.yaml](.github/workflows/build.yaml) runs on pull requests, pushes to main
and by hand, on `ubuntu-26.04` (`ubuntu-26.04-arm` for aarch64): plan → php →
composer and extensions ([package.yaml](.github/workflows/package.yaml): the
generated manifest built with
[flatpak-builder](https://github.com/marketplace/actions/flatpak-builder);
`MAX_PARALLEL`, default 4) → on main, tag and pages: every package as a flatpak
repository on GitHub Pages, signed with the key in secrets `GPG_PRIVATE_KEY`,
`GPG_PASSPHRASE` and variables `GPG_KEY_ID`, `GPG_KEY_GREP` (its keygrip). A pull
request builds and pushes the images; main, after the merge, finds them.
Get a bundle:
`echo 'FROM ghcr.io/kattokeskus/php-flatpak/<name>:<tag>' | docker buildx build -o <dir> -`.

## Development

[packages.json](packages.json) holds versions and build options;
[generate.py](generate.py) writes the manifests to `build/` with source URLs
and checksums, so a version bump (also by Renovate) is one line. With
`--tests` the manifests run the test suites (`build.sh` passes it); `--index`
writes the Pages index.

### packages.json

| Key | |
| --- | --- |
| `name` | id prefix: `kattokeskus` |
| `arches` | the architectures CI builds |
| `sdk`, `composer.version` | runtime and branch; Composer release |
| `php.config-opts`, `.ini`, `.patches` | for all versions; `{prefix}`, `{minor}` expanded |
| `php.versions.<minor>` | release, plus its own `config-opts`, `ini`, `patches` |
| `extensions.<name>` | see below |
| `deps.<name>` | a library built into the packages that list it: `version`, `url`, `arch` (per architecture `{arch}` in the URL), flatpak-builder module keys, `patches`, `keep-bin`, `renovate` |
| `services.<name>` | a test server, see Tests |

An extension: `source` (`bundled`, `pecl` with `version`, `url` with `version`
and `url`, or `none` for FFI-only), `subdir`, `deps`, `config-opts` (`{prefix}`
is its own prefix), `ini`, `zend`, `priority` (ini prefix, default 30),
`requires`, `php` (versions), `renovate`, `tests`.

### Tests

Each extension's build loads the module, runs `tests/<ext>.sh` if present
(test patches), then the upstream suite on `php -n`; a
failure fails the build. `tests` in packages.json: `skip`, `commands`, `env`,
`args`, `dir`, `with` (other bundled extensions the suite needs),
`services`, `network`, or `false`.

Servers run inside the build sandbox, built and started in the test step and
never installed. A service: `from` (a dep's source) or `sources` (`version`,
`url`, `arch`, `dest`, `type`, `dest-filename`), `files`, `build`, `start` (may
export the suite's settings), `stop`.

| Service | Suites |
| --- | --- |
| postgres | pgsql, pdo_pgsql |
| mysql (8.4 minimal build) | mysqli, pdo_mysql |
| ldap (slapd, as php-src's `setup-slapd.sh`) | ldap |
| snmp (snmpd) | snmp |
| firebird | pdo_firebird |

pdo_dblib and pdo_odbc skip their server tests: they need SQL Server.

### Patches

- `php-8.4-no-deepbind.patch`: backport from 8.5; with `RTLD_DEEPBIND` xsl lost text.
- `phpdbg-scan-dir.patch`: phpdbg crashed on start without `PHP_INI_SCAN_DIR`.
- `net-snmp-session-reuse.patch`: net-snmp 5.9.5 failed every request after a session's first.

### Notes

- `kattokeskus-` prefix: Flathub owns `php84`, and SDK extensions must stay
  under `org.freedesktop.Sdk.Extension.`.
- `-<ext>`, not `.<ext>`: `flatpak build` rejects a dotted extension id.
- Headers and `lib/php/build` are kept so extensions can build against PHP.
- Bundled libraries are found through RPATH; `enable.sh` adds their `lib`
  to `LD_LIBRARY_PATH` only for FFI.
- `PHP_INI_SCAN_DIR` replaces the compiled-in scan dir, so `enable.sh`
  repeats `/app/etc/php` and `/var/config/php/<version>/ini`.

## License

The files in this repository are MIT, see [LICENSE](LICENSE); the patches in
[patches/](patches/) change PHP and net-snmp and are under their licenses.

The built packages contain PHP, Composer, extensions and libraries under their
own licenses (PHP License, LGPL, GPL-3.0 for spx, ...), installed in each
package's `share/licenses/`. Each package's sources, with checksums, are listed
in its manifest (`./generate.py`).
