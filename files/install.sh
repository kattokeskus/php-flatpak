#!/bin/sh
# Copies PHP and the installed extension packages into /app, for apps that run
# PHP: SDK extensions exist only at build time. In an app manifest:
#   /usr/lib/sdk/@NAME@/install.sh
# The modules' RPATH into /usr/lib/sdk is gone at runtime; the loader falls
# back to /app/lib, where the libraries are copied.
set -eu

prefix=/usr/lib/sdk/@NAME@
appdir=${1:-/app}

install -d "$appdir/bin" "$appdir/lib" "$appdir/lib/php/modules" "$appdir/etc/php"

install -m755 "$prefix/bin/php" "$appdir/bin/php"
install -m644 "$prefix/etc/php/php.ini" "$appdir/etc/php/php.ini"

for lib in "$prefix"/lib/*.so*; do
    [ -e "$lib" ] || continue
    cp -aP "$lib" "$appdir/lib/"
done

# shared modules of PHP itself (opcache on 8.4); their ini files get absolute paths
extdir=$("$prefix/bin/php-config" --extension-dir)
for so in "$extdir"/*.so; do
    [ -e "$so" ] || continue
    install -m755 "$so" "$appdir/lib/php/modules/"
done
for ini in "$prefix"/etc/php/conf.d/*.ini; do
    [ -e "$ini" ] || continue
    sed -E "s#^[[:space:]]*(zend_extension|extension)[[:space:]]*=[[:space:]]*([^/[:space:]]+)\$#\1=$appdir/lib/php/modules/\2#" \
        "$ini" > "$appdir/etc/php/${ini##*/}"
done

for dir in /usr/lib/sdk/@NAME@-*; do
    [ -d "$dir" ] || continue

    for so in "$dir"/lib/php/modules/*.so; do
        [ -e "$so" ] || continue
        install -m755 "$so" "$appdir/lib/php/modules/"
    done

    for lib in "$dir"/lib/*.so*; do
        [ -e "$lib" ] || continue
        cp -aP "$lib" "$appdir/lib/"
    done

    for ini in "$dir"/etc/conf.d/*.ini; do
        [ -e "$ini" ] || continue
        sed -e "s|$dir/lib/php/modules|$appdir/lib/php/modules|g" \
            "$ini" > "$appdir/etc/php/${ini##*/}"
    done
done
