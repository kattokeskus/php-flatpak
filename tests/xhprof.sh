#!/bin/bash
# From docker-php, extensions/xhprof/patches/xhprof.sh; runs in extension/.
set -euo pipefail

# PHP 8.5 deprecated curl_close(), a no-op since PHP 8.0: its notice and the
# Deprecated::__construct call it records break the expected output.
test_file="tests/xhprof_012.phpt"
if [[ -f "${test_file}" ]]; then
  sed -i -e '/^curl_close(\$ch);$/d' -e '/^main()==>curl_close /d' "${test_file}"
fi
