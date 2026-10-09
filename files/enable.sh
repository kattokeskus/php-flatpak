#!/bin/sh
# Enables PHP and every installed /usr/lib/sdk/@NAME@-<ext> package, through
# PHP_INI_SCAN_DIR. @VAR_UC@_DISABLE="xdebug,spx" leaves some out.

# prepended: wins over other enabled PHP SDK extensions
export PATH=/usr/lib/sdk/@NAME@/bin:$PATH

# comma- or space-separated (extension names have no spaces)
@VAR@_disable=$(printf '%s' "${@VAR_UC@_DISABLE:-}" | tr ',' ' ')

# sorted by ini file name, so the NN- prefix sets the load order across packages
@VAR@_confd=$(
    for @VAR@_ini in /usr/lib/sdk/@NAME@-*/etc/conf.d/*.ini; do
        [ -e "$@VAR@_ini" ] || continue
        @VAR@_name=${@VAR@_ini##*/}
        @VAR@_ext=${@VAR@_name#*-}
        @VAR@_ext=${@VAR@_ext%.ini}
        case " $@VAR@_disable " in
            *" $@VAR@_ext "*) continue ;;
        esac
        printf '%s\t%s\n' "$@VAR@_name" "${@VAR@_ini%/*}"
    done | sort | cut -f2 | awk '!seen[$0]++' | tr '\n' ':'
)

# PHP_INI_SCAN_DIR replaces the compiled-in default, so repeat it
export PHP_INI_SCAN_DIR="/usr/lib/sdk/@NAME@/etc/php/conf.d:${@VAR@_confd}/app/etc/php:/var/config/php/@MINOR@/ini"

# LD_LIBRARY_PATH for FFI (php-vips loads libvips by name); bin for magick, vips
for @VAR@_dir in /usr/lib/sdk/@NAME@-*; do
    [ ! -d "$@VAR@_dir/lib" ] || LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}$@VAR@_dir/lib"
    [ ! -d "$@VAR@_dir/bin" ] || PATH="$PATH:$@VAR@_dir/bin"
done
[ -z "${LD_LIBRARY_PATH:-}" ] || export LD_LIBRARY_PATH

unset @VAR@_disable @VAR@_confd @VAR@_ini @VAR@_name @VAR@_ext @VAR@_dir
