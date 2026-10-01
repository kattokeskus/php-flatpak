#!/bin/bash
set -euo pipefail

php_source_dir="${PHP_SOURCE_DIR:-/usr/src/php}"
tests_dir="${php_source_dir}/ext/sockets/tests"

# bug63000.phpt joins a multicast group, which fails with ENODEV without a
# route (the sandbox has only loopback). Skip as the other multicast tests do.
test_file="${tests_dir}/bug63000.phpt"
if [[ -f "${test_file}" ]] && ! grep -q -- '--SKIPIF--' "${test_file}"; then
  sed -i '/^--FILE--$/i\
--SKIPIF--\
<?php\
$s = socket_create(AF_INET, SOCK_DGRAM, SOL_UDP);\
if (@socket_set_option($s, IPPROTO_IP, MCAST_JOIN_GROUP, ["group" => "224.0.0.251", "interface" => 0]) === false\
    && socket_last_error($s) === SOCKET_ENODEV) {\
    die("skip no route for multicast (ENODEV)");\
}\
?>' "${test_file}"
fi

# These skip only for non-root. With the host's network (the flatpak-builder
# action's run-tests) root in the sandbox may not create raw sockets.
for spec in "socket_icmp.phpt|AF_INET, SOCK_RAW, IPPROTO_ICMP" "socket_afpacket.phpt|AF_PACKET, SOCK_RAW, ETH_P_IP"; do
  test_file="${tests_dir}/${spec%%|*}"
  if [[ -f "${test_file}" ]] && ! grep -q 'cannot create raw sockets' "${test_file}"; then
    sed -i "/^--FILE--\$/i\\
<?php if (@socket_create(${spec#*|}) === false) die('skip cannot create raw sockets'); ?>" "${test_file}"
  fi
done
