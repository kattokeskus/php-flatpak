#!/usr/bin/env python3
"""Generate the flatpak-builder manifests from packages.json.

    ./generate.py                                                         # every package
    ./generate.py org.freedesktop.Sdk.Extension.kattokeskus-php84-mysqli  # just these
    ./generate.py --tests                                                 # with run-tests
    ./generate.py --plan                                                  # fingerprints, tags (JSON)
    ./generate.py --index <url> <homepage>                                # the Pages index (HTML)

Manifests go to build/, PHP packages first: the others build against them.
Without --tests the test commands are there but off, as flatpak-builder has
no option to turn them on (the flatpak-builder action's run-tests does).
A source is downloaded once for its sha256, straight into flatpak-builder's
download cache; the checksum is kept in .cache/sources.json.
"""

import hashlib
import html
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "build"
CACHE = ROOT / ".cache" / "sources.json"
DOWNLOADS = ROOT / ".flatpak-builder" / "downloads"

ID_PREFIX = "org.freedesktop.Sdk.Extension."

# ini file prefixes: 10- PHP's own, 30- extensions, 50- Zend extensions
EXT_PRIORITY = 30


def load_cache():
    try:
        return json.loads(CACHE.read_text())
    except FileNotFoundError:
        return {}


def save_cache(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=4, sort_keys=True) + "\n")


def sha256_of(url, cache):
    if url in cache:
        return cache[url]

    print(f"  fetch {url}", file=sys.stderr)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with tempfile.NamedTemporaryFile(dir=DOWNLOADS, delete=False) as tmp:
        try:
            with urllib.request.urlopen(url) as response:
                while chunk := response.read(1 << 20):
                    digest.update(chunk)
                    tmp.write(chunk)
        except BaseException:
            os.unlink(tmp.name)
            raise

    sha256 = digest.hexdigest()
    dest = DOWNLOADS / sha256 / url.rsplit("/", 1)[-1]
    dest.parent.mkdir(exist_ok=True)
    os.chmod(tmp.name, 0o644)
    os.replace(tmp.name, dest)

    cache[url] = sha256
    return sha256


def source(kind, url, cache, **extra):
    return {"type": kind, "url": url, "sha256": sha256_of(url, cache), **extra}


def arch_sources(config, kind, spec, cache, **extra):
    """The source, or one per architecture when "arch" gives its {arch}."""
    names = spec.get("arch")
    if names is None:
        return [source(kind, spec["url"].format(**spec), cache, **extra)]
    missing = set(config["arches"]) - set(names)
    if missing:
        sys.exit(f"error: {spec['url']}: no arch for {' '.join(sorted(missing))}")
    return [source(kind, spec["url"].format(**{**spec, "arch": names[arch]}), cache,
                   **extra, **{"only-arches": [arch]})
            for arch in sorted(config["arches"])]


def php_name(config, minor):  # 8.4 -> kattokeskus-php84
    return f"{config['name']}-php" + minor.replace(".", "")


def composer_name(config):
    return f"{config['name']}-composer"


def php_tarball(config, minor, cache):
    version = config["php"]["versions"][minor]["version"]
    return source("archive", f"https://www.php.net/distributions/php-{version}.tar.xz", cache)


def write_ini(path, lines):
    """A build command that writes lines to an ini file."""
    return f"printf '%s\\n' {' '.join(json.dumps(line) for line in lines)} > {path}"


def base_manifest(config, name, **build_options):
    sdk = config["sdk"]
    prefix = f"/usr/lib/sdk/{name}"
    return {
        "id": ID_PREFIX + name,
        "branch": sdk["branch"],
        "runtime": sdk["id"],
        "runtime-version": sdk["branch"],
        "sdk": sdk["id"],
        "build-extension": True,
        "separate-locales": False,
        "appstream-compose": False,
        "build-options": {
            "prefix": prefix,
            "no-debuginfo": True,
            "strip": True,
            **build_options,
        },
    }


def php_manifest(config, minor, cache):
    php = config["php"]
    release = php["versions"][minor]
    name = php_name(config, minor)
    prefix = f"/usr/lib/sdk/{name}"

    def expand(opt):
        return opt.replace("{prefix}", prefix).replace("{minor}", minor)

    config_opts = [expand(o) for o in php["config-opts"] + release.get("config-opts", [])]

    # version-specific lines first
    ini = {}
    for section in (release.get("ini", {}), php.get("ini", {})):
        for file, lines in section.items():
            ini.setdefault(file, []).extend(lines)
    ini_commands = [
        write_ini(f"${{FLATPAK_DEST}}/etc/php/conf.d/{file}.ini", lines)
        for file, lines in sorted(ini.items())
    ]

    # @VAR@: the name as a shell variable name, without dashes
    var = name.replace("-", "_")
    substitute = (
        f"sed -e 's|@NAME@|{name}|g' -e 's|@VAR@|{var}|g' -e 's|@VAR_UC@|{var.upper()}|g'"
        f" -e 's|@MINOR@|{minor}|g'"
    )

    return {
        **base_manifest(config, name, **{"prepend-path": f"{prefix}/bin"}),
        # man pages and empty dirs; include/ stays for the extension packages
        "cleanup": ["/php", "/var"],
        "modules": [
            {
                "name": "php",
                "config-opts": config_opts,
                "sources": [
                    php_tarball(config, minor, cache),
                    *({"type": "patch", "path": f"../patches/{patch}"}
                      for patch in php.get("patches", []) + release.get("patches", [])),
                ],
                "post-install": [
                    "install -Dm644 php.ini-development ${FLATPAK_DEST}/etc/php/php.ini",
                    "install -Dm644 LICENSE ${FLATPAK_DEST}/share/licenses/php/LICENSE",
                    "install -d ${FLATPAK_DEST}/etc/php/conf.d",
                    *ini_commands,
                ],
            },
            {
                "name": "scripts",
                "buildsystem": "simple",
                "sources": [
                    {"type": "file", "path": "../files/enable.sh"},
                    {"type": "file", "path": "../files/install.sh"},
                ],
                "build-commands": [
                    f"{substitute} enable.sh > ${{FLATPAK_DEST}}/enable.sh",
                    f"{substitute} install.sh > ${{FLATPAK_DEST}}/install.sh",
                    "chmod 755 ${FLATPAK_DEST}/enable.sh ${FLATPAK_DEST}/install.sh",
                ],
            },
        ],
    }


def composer_manifest(config, cache):
    """One Composer for all PHP versions; it runs on the php first on PATH."""
    name = composer_name(config)
    version = config["composer"]["version"]
    php_ids = [ID_PREFIX + php_name(config, m) for m in config["php"]["versions"]]
    substitute = f"sed -e 's|@NAME@|{name}|g'"
    return {
        **base_manifest(config, name),
        "sdk-extensions": php_ids,  # for the test
        "modules": [
            {
                "name": "composer",
                "buildsystem": "simple",
                "sources": [
                    source("file", f"https://getcomposer.org/download/{version}/composer.phar", cache,
                           **{"dest-filename": "composer"}),
                    source("file", f"https://raw.githubusercontent.com/composer/composer/{version}/LICENSE",
                           cache),
                    {"type": "file", "path": "../files/composer-enable.sh"},
                ],
                "build-commands": [
                    "install -Dm755 composer ${FLATPAK_DEST}/bin/composer",
                    "install -Dm644 LICENSE ${FLATPAK_DEST}/share/licenses/composer/LICENSE",
                    f"{substitute} composer-enable.sh > ${{FLATPAK_DEST}}/enable.sh",
                    "chmod 755 ${FLATPAK_DEST}/enable.sh",
                ],
                "test-commands": [
                    f"/usr/lib/sdk/{php_name(config, m)}/bin/php ${{FLATPAK_DEST}}/bin/composer"
                    f" --version --no-interaction | grep -F 'Composer version {version} '"
                    for m in config["php"]["versions"]
                ],
            },
        ],
    }


# build-time leftovers of a bundled library
DEP_CLEANUP = ["/include", "/lib/pkgconfig", "/lib/cmake", "/share/man", "/share/doc",
               "/share/gtk-doc", "/share/info", "*.a", "*.la"]

# bundled extensions are in ext/<name>, PHP's LICENSE two up; postgres has
# COPYRIGHT, tidy README/LICENSE.md
FIND_LICENSE = (
    "lic=$(ls -d LICENSE* COPYING* ../LICENSE* ../COPYING* ../../LICENSE* ../../COPYING*"
    " 2>/dev/null | head -n1); [ -n \"$lic\" ]"
    " || lic=$(ls -d COPYRIGHT* README/LICENSE* 2>/dev/null | head -n1)"
)


def install_license(name):
    return (
        f"{FIND_LICENSE}; [ -z \"$lic\" ]"
        f" || install -Dm644 \"$lic\" ${{FLATPAK_DEST}}/share/licenses/{name}/LICENSE"
    )


def dep_module(config, dep, cache):
    spec = config["deps"][dep]
    module = {
        "name": dep,
        "buildsystem": spec["buildsystem"],
        "sources": [
            *arch_sources(config, "archive", spec, cache),
            *({"type": "patch", "path": f"../patches/{patch}"} for patch in spec.get("patches", [])),
        ],
        "cleanup": DEP_CLEANUP + ([] if spec.get("keep-bin") else ["/bin", "/sbin"]),
        "post-install": [install_license(dep)],
    }
    for key in ("subdir", "config-opts", "build-commands"):
        if key in spec:
            module[key] = spec[key]
    return module


def ext_source(spec, ext, php_source, cache):
    kind = spec["source"]
    if kind == "bundled":
        return [php_source], f"ext/{ext}"
    if kind == "pecl":
        url = f"https://pecl.php.net/get/{spec.get('package', ext)}-{spec['version']}.tgz"
    elif kind == "url":
        url = spec["url"].format(**spec)
    else:
        sys.exit(f"error: {ext}: unknown source {kind!r}")
    return [source("archive", url, cache)], spec.get("subdir")


def service_sources(config, name, cache):
    """A test service's sources and files, unpacked to _services/<name>."""
    spec = config["services"][name]
    srcs = [config["deps"][spec["from"]]] if "from" in spec else spec["sources"]
    sources = []
    for src in srcs:
        extra = {"dest": "/".join(filter(None, [f"_services/{name}", src.get("dest")]))}
        if "dest-filename" in src:
            extra["dest-filename"] = src["dest-filename"]
        sources += arch_sources(config, src.get("type", "archive"), src, cache, **extra)
    return sources + [
        {"type": "file", "path": f"../{path}", "dest": f"_services/{name}"}
        for path in spec.get("files", [])
    ]


def service_command(config, names, up, run):
    """Build and start the services, run, stop them - as one command, since
    flatpak-builder runs each test command in a sandbox of its own."""
    parts, stops = ["set -e"], []
    for name in names:
        spec = config["services"][name]
        var = "svc_" + name.replace("-", "_")
        def expand(line):
            return line.replace("{service}", f"${{{var}}}")
        parts.append(f"{var}=$(cd {up}_services/{name} && pwd)")
        build = " && ".join(expand(c) for c in spec["build"])
        # without the package's flags: its RPATH would load the package's
        # libraries instead of the server's own
        parts.append(f'echo "building test service {name}"')
        parts.append(f'(cd "${var}" && unset CPPFLAGS LDFLAGS PKG_CONFIG_PATH && {build})'
                     f' > "${var}.log" 2>&1 || {{ tail -n 50 "${var}.log"; exit 1; }}')
        parts.append(f'echo "starting test service {name}"')
        parts += [expand(c) for c in spec["start"]]
        stops += [expand(c) for c in spec.get("stop", [])]
    if stops:
        parts.append("trap '" + "; ".join(stops) + "' EXIT")
    parts += ["set +e", run]
    return "; ".join(parts)


def ext_tests(config, ext, spec, directive, subdir, expand, php_config, cache):
    """Load test, tests/<ext>.sh if there is one, then the phpt suite."""
    tests = spec.get("tests", {})
    if tests is False:
        return None
    sources, commands = [], [
        f"php -n -d {directive}=${{FLATPAK_DEST}}/lib/php/modules/{ext}.so"
        f" -r 'exit(extension_loaded(\"{ext}\") ? 0 : 1);'",
    ]
    env = " ".join(f"{k}={json.dumps(expand(v))}" for k, v in tests.get("env", {}).items())
    env = env + " " if env else ""

    script = ROOT / "tests" / f"{ext}.sh"
    if script.exists():
        source = {"type": "file", "path": f"../tests/{ext}.sh", "dest-filename": "flatpak-tests.sh"}
        if subdir:
            source["dest"] = subdir
        sources.append(source)
        php_src = "PHP_SOURCE_DIR=$(cd ../.. && pwd) " if spec["source"] == "bundled" else ""
        commands.append(f"{env}{php_src}bash flatpak-tests.sh")

    args = list(tests.get("args", []))
    if spec["source"] == "bundled":
        # make test sets TEST_PHP_SRCDIR to the extension's directory, but the
        # pdo_* suites and sapi/cli's test server expect the source tree there
        commands.append("[ -e ext ] || ln -s .. ext; [ -e sapi ] || ln -s ../../sapi sapi")
        # other bundled extensions the suite needs (ftp: pcntl)
        for other in tests.get("with", []):
            commands.append(f"cd ../{other} && phpize && ./configure --with-php-config={php_config}"
                            " && make -j${FLATPAK_BUILDER_N_JOBS}")
            args.append(f"-d extension=$(cd ../{other} && pwd)/modules/{other}.so")

    commands += [expand(c) for c in tests.get("commands", [])]
    commands += [f"rm -f {t}" for t in tests.get("skip", [])]
    run_tests = " ".join(["-j${FLATPAK_BUILDER_N_JOBS} -q --show-diff",
                          *args, tests.get("dir", "tests")])
    # The suites expect PHP's defaults (-n, as in php-src's CI), not our
    # php.ini-development. The sandbox has no network and no TMPDIR.
    commands.append(f"printf '#!/bin/sh\\nexec %s -n \"$@\"\\n' \"$({php_config} --php-binary)\" > php-n"
                    " && chmod +x php-n")
    run = (f'TMPDIR=${{TMPDIR:-/tmp}} {env}make test PHP_EXECUTABLE=$PWD/php-n NO_INTERACTION=1'
           f' SKIP_ONLINE_TESTS=1 TESTS="{run_tests}"')

    services = tests.get("services", [])
    unknown = set(services) - set(config.get("services", {}))
    if unknown:
        sys.exit(f"error: {ext}: no such service: {' '.join(sorted(unknown))}")
    if services:
        sources += [src for name in services for src in service_sources(config, name, cache)]
        up = "../" * len(subdir.split("/")) if subdir else ""
        run = service_command(config, services, up, run)
    commands.append(run)
    return {"sources": sources, "commands": commands, "network": tests.get("network", False)}


def ext_manifest(config, minor, ext, cache):
    spec = config["extensions"][ext]
    base = php_name(config, minor)
    name = f"{base}-{ext}"
    prefix = f"/usr/lib/sdk/{name}"
    php_prefix = f"/usr/lib/sdk/{base}"
    php_config = f"{php_prefix}/bin/php-config"
    deps = spec.get("deps", [])

    def expand(value):
        return (value.replace("{prefix}", prefix).replace("{php_prefix}", php_prefix)
                .replace("{minor}", minor))

    ini = [expand(line) for line in spec.get("ini", [])]
    for required in spec.get("requires", []):
        ini.insert(0, f"; needs {ID_PREFIX}{base}-{required}")
    directive = "zend_extension" if spec.get("zend") else "extension"
    if spec["source"] != "none":
        ini.insert(0, f"{directive}={prefix}/lib/php/modules/{ext}.so")
    ini_file = f"${{FLATPAK_DEST}}/etc/conf.d/{spec.get('priority', EXT_PRIORITY)}-{ext}.ini"

    build_options = {"prepend-path": f"{php_prefix}/bin"}
    if deps:
        # RPATH, not RUNPATH: it also covers bundled libraries' dependencies
        build_options = {
            "prepend-path": f"{prefix}/bin:{php_prefix}/bin",
            "prepend-pkg-config-path": f"{prefix}/lib/pkgconfig",
            "cppflags": f"-I{prefix}/include",
            "ldflags": f"-L{prefix}/lib -Wl,-rpath,{prefix}/lib -Wl,--disable-new-dtags",
        }

    modules = [dep_module(config, dep, cache) for dep in deps]

    if spec["source"] == "none":
        # a library for FFI (vips): no PHP module
        modules.append({
            "name": f"php-{ext}",
            "buildsystem": "simple",
            "sources": [],
            "build-commands": ["install -d ${FLATPAK_DEST}/etc/conf.d", write_ini(ini_file, ini)],
        })
    else:
        sources, subdir = ext_source(spec, ext, php_tarball(config, minor, cache), cache)
        configure = " ".join([f"./configure --with-php-config={php_config}",
                              *(expand(o) for o in spec.get("config-opts", []))])
        # extension_dir is in the read-only PHP package: install to a staging
        # root, then copy the module, headers and files of our own prefix
        stage = "${PWD}/_stage"
        # not <ext>: a bundled library can have the same name (enchant, tidy)
        module = {
            "name": f"php-{ext}",
            "buildsystem": "simple",
            "sources": sources,
            "build-commands": [
                "phpize",
                configure,
                "make -j${FLATPAK_BUILDER_N_JOBS}",
                f"make install INSTALL_ROOT={stage}",
                f"install -Dm755 {stage}$({php_config} --extension-dir)/{ext}.so"
                f" ${{FLATPAK_DEST}}/lib/php/modules/{ext}.so",
                f"if [ -d {stage}{php_prefix}/include/php/ext ]; then"
                f" install -d ${{FLATPAK_DEST}}/include/php"
                f" && cp -r {stage}{php_prefix}/include/php/ext ${{FLATPAK_DEST}}/include/php/; fi",
                f"if [ -d {stage}{prefix} ]; then cp -a {stage}{prefix}/. ${{FLATPAK_DEST}}/; fi",
                "install -d ${FLATPAK_DEST}/etc/conf.d",
                write_ini(ini_file, ini),
                install_license(f"php-{ext}"),
            ],
        }
        if subdir:
            module["subdir"] = subdir
        tests = ext_tests(config, ext, spec, directive, subdir, expand, php_config, cache)
        if tests:
            module["sources"] += tests["sources"]
            module["test-commands"] = tests["commands"]
            # flatpak-builder leaves test commands out of the cache key
            digest = hashlib.sha256(json.dumps(tests["commands"]).encode()).hexdigest()[:12]
            module["build-commands"].append(f": tests {digest}")
            if tests["network"]:
                build_options["test-args"] = ["--share=network"]
        modules.append(module)

    return {
        **base_manifest(config, name, **build_options),
        "sdk-extensions": [ID_PREFIX + base],
        "modules": modules,
    }


def packages(config):
    """Every package as (id, manifest function, arguments), PHP first."""
    minors = list(config["php"]["versions"])
    result = [(ID_PREFIX + php_name(config, m), php_manifest, (m,)) for m in minors]
    result.append((ID_PREFIX + composer_name(config), composer_manifest, ()))
    for ext, spec in config.get("extensions", {}).items():
        for m in spec.get("php", minors):
            result.append((f"{ID_PREFIX}{php_name(config, m)}-{ext}", ext_manifest, (m, ext)))
    return result


# flatpak's architecture names -> image platforms
PLATFORMS = {"x86_64": "linux/amd64", "aarch64": "linux/arm64"}


def fingerprint(manifest, needs, arches):
    """Hash of everything a build depends on: the manifest (sources with their
    checksums, commands), the local files it uses, the architectures it is
    built for and the packages it builds against."""
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode())
    digest.update(" ".join(sorted(arches)).encode())
    paths = sorted({src["path"] for module in manifest["modules"]
                    for src in module.get("sources", []) if "path" in src})
    for path in paths:
        # normalised: build/ need not exist
        digest.update(path.encode() + b"\0" + Path(os.path.normpath(OUT / path)).read_bytes())
    for need in needs:
        digest.update(need.encode())
    return digest.hexdigest()[:12]


def describe(config, make, args):
    """A package's kind, what it builds against, its version and its tags."""
    if make is php_manifest:
        minor, = args
        version = config["php"]["versions"][minor]["version"]
        return "php", [], version, [version]
    if make is composer_manifest:
        version = config["composer"]["version"]
        return ("composer", [ID_PREFIX + php_name(config, m) for m in config["php"]["versions"]],
                version, [version])
    minor, ext = args
    spec = config["extensions"][ext]
    needs = [ID_PREFIX + php_name(config, minor)]
    php_version = config["php"]["versions"][minor]["version"]
    if spec["source"] == "bundled":
        return "extension", needs, php_version, [php_version]
    version = spec.get("version") or config["deps"][spec["deps"][0]]["version"]
    return "extension", needs, version, [f"{version}-php{php_version}"]


def plan(config, cache):
    """Every package with what it needs, its fingerprint and its tags."""
    arches = config["arches"]
    result, fingerprints = [], {}
    for manifest_id, make, args in packages(config):
        kind, needs, version, tags = describe(config, make, args)
        fingerprints[manifest_id] = fingerprint(make(config, *args, cache),
                                                [fingerprints[n] for n in needs], arches)
        result.append({
            "id": manifest_id,
            "name": manifest_id[len(ID_PREFIX):],
            "kind": kind,
            "needs": needs,
            "fingerprint": fingerprints[manifest_id],
            "arches": arches,
            "platforms": ",".join(PLATFORMS[arch] for arch in arches),
            "version": version,
            "tags": tags + ["latest"],
        })
    return result


INDEX_STYLE = """
:root { color-scheme: light dark; font-family: system-ui, sans-serif; line-height: 1.5; }
body { max-width: 56rem; margin: 2rem auto; padding: 0 1rem; }
pre { padding: .6rem .8rem; overflow-x: auto; background: rgb(127 127 127 / .12); border-radius: 6px; }
summary { cursor: pointer; font-weight: 600; }
table { border-collapse: collapse; margin: .5rem 0 1rem; }
th, td { padding: .15rem 1.2rem .15rem 0; text-align: left; vertical-align: top; }
td code { font-size: .9em; }
"""


def index(config, url, homepage):
    """The Pages index: how to add the repository, each PHP version with its
    extensions, and Composer."""
    esc = html.escape
    title = f"{config['name'].capitalize()} PHP"
    remote = f"{config['name']}-php"
    branch = config["sdk"]["branch"]
    php, extensions, composer = {}, {}, None
    for manifest_id, make, args in packages(config):
        kind, _, version, _ = describe(config, make, args)
        if kind == "php":
            php[args[0]] = (manifest_id, version)
        elif kind == "composer":
            composer = (manifest_id, version)
        else:
            extensions.setdefault(args[0], []).append((args[1], version, manifest_id))

    def install(manifest_id):
        return f"<pre>flatpak install {esc(remote)} {esc(manifest_id)}//{esc(branch)}</pre>"

    out = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{esc(title)} Flatpak Repository</title>",
        f"<style>{INDEX_STYLE}</style>",
        "</head>",
        "<body>",
        f"<h1>{esc(title)}</h1>",
        f"<p>PHP, Composer and PHP extensions as <code>{esc(config['sdk']['id'])}//{esc(branch)}</code>"
        f" extensions, for {esc(' and '.join(config['arches']))}."
        f' Usage and sources: <a href="{esc(homepage)}">{esc(homepage)}</a>.</p>',
        "<pre>flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo",
        f"flatpak remote-add --if-not-exists {esc(remote)} {esc(url)}/{esc(remote)}.flatpakrepo</pre>",
    ]
    for minor, (manifest_id, version) in php.items():
        exts = sorted(extensions.get(minor, []))
        out += [f"<h2>PHP {esc(version)}</h2>", install(manifest_id),
                f"<details><summary>Extensions ({len(exts)})</summary>",
                "<table><tr><th>Extension</th><th>Version</th><th>Package</th></tr>"]
        out += [f"<tr><td>{esc(ext)}</td><td>{esc(v)}</td><td><code>{esc(i)}</code></td></tr>"
                for ext, v, i in exts]
        out += ["</table></details>"]
    if composer:
        manifest_id, version = composer
        out += [f"<h2>Composer {esc(version)}</h2>", "<p>Runs on the enabled PHP.</p>",
                install(manifest_id)]
    return "\n".join(out + ["</body>", "</html>"]) + "\n"


def main(argv):
    config = json.loads((ROOT / "packages.json").read_text())

    if argv[:1] == ["--index"]:
        if len(argv) != 3:
            sys.exit(__doc__)
        print(index(config, argv[1].rstrip("/"), argv[2]), end="")
        return

    cache = load_cache()

    if argv == ["--plan"]:
        try:
            print(json.dumps(plan(config, cache), indent=4))
        finally:
            save_cache(cache)
        return

    tests = "--tests" in argv
    ids = [a for a in argv if a != "--tests"]
    selected = [p for p in packages(config) if not ids or p[0] in ids]
    unknown = set(ids) - {p[0] for p in selected}
    if unknown:
        sys.exit(f"error: no such package: {' '.join(sorted(unknown))}")

    OUT.mkdir(exist_ok=True)
    try:
        for manifest_id, make, args in selected:
            manifest = make(config, *args, cache)
            if tests:
                for module in manifest["modules"]:
                    if "test-commands" in module:
                        module["run-tests"] = True
            path = OUT / f"{manifest_id}.json"
            path.write_text(json.dumps(manifest, indent=4) + "\n")
            print(path.relative_to(ROOT))
    finally:
        save_cache(cache)


if __name__ == "__main__":
    main(sys.argv[1:])
