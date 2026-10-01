#!/bin/bash
# From docker-php, extensions/base/patches/pdo_firebird.sh.
set -euo pipefail

php_source_dir="${PHP_SOURCE_DIR:-/usr/src/php}"
tests_dir="${php_source_dir}/ext/pdo_firebird/tests"

# Backport php-src fec2055a: Firebird DSNs do not handle an IPv6 localhost
# address emitted by the payload server correctly.
sed -i 's#tcp://localhost:0#tcp://127.0.0.1:0#' \
  "${tests_dir}/payload_server.php"
