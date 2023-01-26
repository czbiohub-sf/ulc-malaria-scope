#! /bin/bash

# Fancy a game of Roulette?
#
# Rules:
# - spin the wheel with "./roulette.sh"
# - whatever TODO, FIXME, or type error you get, you must fix!
# - total number of TODOs, FIXMEs, or type error must go down

our_problems=$({ mypy ulc_mm_package --config-file mypy.ini --no-error-summary; git grep -niE '(FIXME|TODO)'; })

echo "number of 'FIXME's, 'TODO's, and type errors: $(echo "$our_problems" | wc -l)"
echo "$our_problems" | shuf -n 1
