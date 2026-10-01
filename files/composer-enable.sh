#!/bin/sh
# Needs a PHP package enabled too. Prepended: wins over another SDK
# extension's composer. /var/config is XDG_CONFIG_HOME in a flatpak.
export PATH=/usr/lib/sdk/@NAME@/bin:$PATH:/var/config/composer/vendor/bin
