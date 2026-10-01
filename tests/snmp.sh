#!/bin/bash
set -euo pipefail

php_source_dir="${PHP_SOURCE_DIR:-/usr/src/php}"
tests_dir="${php_source_dir}/ext/snmp/tests"

# bug60749.phpt resolves php.net but has no online check.
test_file="${tests_dir}/bug60749.phpt"
if [[ -f "${test_file}" ]] && ! grep -q 'SKIP_ONLINE_TESTS' "${test_file}"; then
  sed -i "0,/^require_once(__DIR__.'\/skipif.inc');\$/s//&\\
if (getenv('SKIP_ONLINE_TESTS')) die('skip online test, resolves php.net');/" "${test_file}"
fi
