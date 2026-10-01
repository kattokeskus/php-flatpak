#!/bin/bash
# Generate the manifests and build them with flatpak-builder.
#
#   ./build.sh                                                  # every package
#   ./build.sh org.freedesktop.Sdk.Extension.kattokeskus-php84  # just these
#   INSTALL=1 ./build.sh                                        # also install --user
#   TESTS=0 ./build.sh                                          # skip the test suites
#   BUNDLES=bundles ./build.sh                                  # also write <id>-<arch>.flatpak bundles
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

mapfile -t manifests < <(./generate.py "${generate[@]}" "$@")

# a failing package does not stop the others
failed=()
for manifest in "${manifests[@]}"; do
    id=$(basename "$manifest" .json)
    echo "==> $id"
    "${builder[@]}" "${args[@]}" "build/$id" "$manifest" || failed+=("$id")
done

if [[ -n "${BUNDLES:-}" ]]; then
    branch=$(python3 -c 'import json; print(json.load(open("packages.json"))["sdk"]["branch"])')
    mkdir -p "$BUNDLES"
    for manifest in "${manifests[@]}"; do
        id=$(basename "$manifest" .json)
        [[ " ${failed[*]} " != *" $id "* ]] || continue
        "${flatpak[@]}" build-bundle --runtime --runtime-repo=https://flathub.org/repo/flathub.flatpakrepo \
            repo "$BUNDLES/$id-$(uname -m).flatpak" "$id" "$branch"
    done
fi

echo
echo "==> built $((${#manifests[@]} - ${#failed[@]})) of ${#manifests[@]}"
if [[ ${#failed[@]} -gt 0 ]]; then
    printf 'FAILED %s\n' "${failed[@]}"
    exit 1
fi
