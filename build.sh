#!/bin/bash
# Generate the manifests and build them with flatpak-builder.
#
#   ./build.sh                                                  # every package, every SDK branch
#   ./build.sh org.freedesktop.Sdk.Extension.kattokeskus-php84  # just these
#   ./build.sh org.freedesktop.Sdk.Extension.kattokeskus-php84//25.08  # on one branch
#   SDK=25.08 ./build.sh                                        # every package on one branch
#   INSTALL=1 ./build.sh                                        # also install --user
#   TESTS=0 ./build.sh                                          # skip the test suites
#   BUNDLES=bundles ./build.sh                                  # also write <id>-<branch>-<arch>.flatpak bundles
#   FLATPAK_BUILDER="<command>" ./build.sh                      # another builder
#
# Without a host flatpak-builder it runs org.flatpak.Builder; inside a flatpak
# (VS Code) through flatpak-spawn --host.
set -euo pipefail

cd "$(dirname "$0")"

if command -v flatpak >/dev/null; then
    flatpak=(flatpak)
else
    flatpak=(flatpak-spawn --host flatpak)
fi
if [[ -n "${FLATPAK_BUILDER:-}" ]]; then
    read -ra builder <<< "$FLATPAK_BUILDER"
elif command -v flatpak-builder >/dev/null; then
    builder=(flatpak-builder)
else
    builder=("${flatpak[@]}" run org.flatpak.Builder)
fi
# no rofiles-fuse, as in flatpak/flatpak-github-actions: not available in containers
args=(--force-clean --disable-rofiles-fuse --repo=repo --state-dir=.flatpak-builder)
[[ ${INSTALL:-0} != 1 ]] || args+=(--user --install)
generate=()
[[ ${TESTS:-1} == 0 ]] || generate+=(--tests)
[[ -z ${SDK:-} ]] || generate+=(--sdk="$SDK")

mapfile -t manifests < <(./generate.py "${generate[@]}" "$@")

# build/<id>-<branch>.json; a branch has no dash
ref() { echo "${1%-*}//${1##*-}"; }

# a failing package does not stop the others
failed=()
for manifest in "${manifests[@]}"; do
    name=$(basename "$manifest" .json)
    echo "==> $(ref "$name")"
    "${builder[@]}" "${args[@]}" "build/$name" "$manifest" || failed+=("$name")
done

if [[ -n "${BUNDLES:-}" ]]; then
    mkdir -p "$BUNDLES"
    for manifest in "${manifests[@]}"; do
        name=$(basename "$manifest" .json)
        [[ " ${failed[*]} " != *" $name "* ]] || continue
        "${flatpak[@]}" build-bundle --runtime --runtime-repo=https://flathub.org/repo/flathub.flatpakrepo \
            repo "$BUNDLES/$name-$(uname -m).flatpak" "${name%-*}" "${name##*-}"
    done
fi

echo
echo "==> built $((${#manifests[@]} - ${#failed[@]})) of ${#manifests[@]}"
if [[ ${#failed[@]} -gt 0 ]]; then
    for name in "${failed[@]}"; do
        echo "FAILED $(ref "$name")"
    done
    exit 1
fi
