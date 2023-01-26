#! /bin/bash

# Fancy a game of Roulette?
#
# Rules:
# - spin the wheel with "./roulette.sh"
# - whatever TODO or FIXME you get, you must fix!
# - total number of TODOs or FIXMEs must go down - i.e.
#   don't introduce more TODOs or FIXMEs than you clean

echo "number of 'FIXME's, 'TODO's, and 'print's: $(git grep -niE '(FIXME|TODO|print)' | wc -l)"
git grep -niE '(FIXME|TODO|print)' | shuf -n 1
