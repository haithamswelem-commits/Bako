#!/bin/sh
set -e

RESOLVER_IPS=$(awk 'BEGIN{ORS=" "} $1=="nameserver" {print $2}' /etc/resolv.conf)

sed -i "s/RESOLVER_PLACEHOLDER/${RESOLVER_IPS}/" /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"