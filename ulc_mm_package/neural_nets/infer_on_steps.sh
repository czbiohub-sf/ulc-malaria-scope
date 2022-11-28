#! /bin/bash

echo "starting step inferences..."

mkdir -p ~/Documents/autofocus-test-data/results/steps

MS_SIMULATE=1 python3 infer.py --images ~/Documents/autofocus-test-data/2022-11-03-164007-local_zstack --output ~/Documents/autofocus-test-data/results/steps/avt-03-11-164007-zstack.txt "$@"
echo "."
MS_SIMULATE=1 python3 infer.py --images ~/Documents/autofocus-test-data/2022-08-11-123340-local_zstack --output ~/Documents/autofocus-test-data/results/steps/basler-08-11-123340-zstack.txt "$@"
echo "."
MS_SIMULATE=1 python3 infer.py --images ~/Documents/autofocus-test-data/2022-11-03-171427-local_zstack --output ~/Documents/autofocus-test-data/results/steps/avt-03-11-171427-zstack.txt "$@"
echo "."
MS_SIMULATE=1 python3 infer.py --images ~/Documents/autofocus-test-data/2022-08-11-124116-local_zstack --output ~/Documents/autofocus-test-data/results/steps/basler-08-11-124116-zstack.txt "$@"
echo "."
