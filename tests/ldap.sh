#!/bin/bash
set -euo pipefail

php_source_dir="${PHP_SOURCE_DIR:-/usr/src/php}"
tests_dir="${php_source_dir}/ext/ldap/tests"

# ldaps_basic.phpt hard-codes port 636; slapd cannot listen below 1024 here.
test_file="${tests_dir}/ldaps_basic.phpt"
if [[ -f "${test_file}" ]] && ! grep -q 'LDAP_TEST_LDAPS_PORT' "${test_file}"; then
  sed -i 's|\$uri = "ldaps://\$host:636";|$uri = "ldaps://$host:" . (getenv("LDAP_TEST_LDAPS_PORT") ?: 636);|' "${test_file}"
fi
