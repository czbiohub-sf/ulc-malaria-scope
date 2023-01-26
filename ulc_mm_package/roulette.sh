#! /bin/bash

# Fancy a game of Roulette?
#
# Rules:
# - spin the wheel with "./roulette.sh"
# - whatever TODO or FIXME you get, you must fix!
# - total number of TODOs or FIXMEs must go down - i.e.
#   don't introduce more TODOs or FIXMEs than you clean

echo "number of 'FIXMEs' and 'TODOs': $(git grep -niE '(FIXME|TODO)' | wc -l)"
git grep -niE '(FIXME|TODO)' | shuf -n 1
