#! /bin/bash

echo "starting step inferences..."

mkdir -p ~/Documents/autofocus-test-data/results/steps

MS_SIMULATE=1 ./various_image_batch_sizes.py --images ~/Documents/autofocus-test-data/2022-11-03-164007-local_zstack "$@" > 11_03_16.txt
echo "."
MS_SIMULATE=1 ./various_image_batch_sizes.py --images ~/Documents/autofocus-test-data/2022-08-11-123340-local_zstack "$@" > 08_11_12.txt
echo "."
MS_SIMULATE=1 ./various_image_batch_sizes.py --images ~/Documents/autofocus-test-data/2022-11-03-171427-local_zstack "$@" > 11_03_17.txt
echo "."
MS_SIMULATE=1 ./various_image_batch_sizes.py --images ~/Documents/autofocus-test-data/2022-08-11-124116-local_zstack "$@" > 08_11-12.txt
echo "."
