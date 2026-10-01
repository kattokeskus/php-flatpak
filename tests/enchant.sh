#!/bin/bash
set -euo pipefail

php_source_dir="${PHP_SOURCE_DIR:-/usr/src/php}"
tests_dir="${php_source_dir}/ext/enchant/tests"

# bug13181.phpt needs an "en" dictionary; the SDK only has en_US etc.
test_file="${tests_dir}/bug13181.phpt"
if [[ -f "${test_file}" ]] && ! grep -q 'en dictionary not installed' "${test_file}"; then
  sed -i '/^if (!enchant_broker_list_dicts($broker)) {$/i\
if (!enchant_broker_dict_exists($broker, "en")) {\
    @enchant_broker_free($broker);\
    die("skip en dictionary not installed");\
}\
' "${test_file}"
fi
