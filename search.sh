#!/bin/bash

#
# same as grep but with the correct orders (by Ep)
#

find outputs -type f -name \*.txt -print0 | sort -V -z | xargs -0 grep --color=always -n "$@"
