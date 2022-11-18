#! /bin/bash

mkdir -p ~/Documents/autofocus-test-data/results/steps
mkdir -p ~/Documents/autofocus-test-data/results/allan

echo "to be run on a Raspberry Pi for measuring Autofocus inference"

echo "starting step inferences..."

MS_SIMULATE=1 python3 infer.py --images ~/Documents/autofocus-test-data/2022-11-03-164007-local_zstack > ~/Documents/autofocus-test-data/results/steps/avt-03-11-164007-zstack.txt
echo "."
MS_SIMULATE=1 python3 infer.py --images ~/Documents/autofocus-test-data/2022-11-03-171427-local_zstack > ~/Documents/autofocus-test-data/results/steps/avt-03-11-171427-zstack.txt
echo "."
MS_SIMULATE=1 python3 infer.py --images ~/Documents/autofocus-test-data/2022-08-11-123340-local_zstack > ~/Documents/autofocus-test-data/results/steps/basler-08-11-123340-zstack.txt
echo "."
MS_SIMULATE=1 python3 infer.py --images ~/Documents/autofocus-test-data/2022-08-11-124116-local_zstack > ~/Documents/autofocus-test-data/results/steps/basler-08-11-124116-zstack.txt
echo "."

echo "starting allan dev calcs..."

MS_SIMULATE=1 python3 infer.py --allan-dev --zarr ~/Documents/autofocus-test-data/2022-11-17-112855_medflow_ohmu_focaldrift.zip --output ~/Documents/autofocus-test-data/results/allan/2022-11-17-112855_medflow_ohmu_focaldrift
echo "."
MS_SIMULATE=1 python3 infer.py --allan-dev --zarr ~/Documents/autofocus-test-data/2022-11-17-113250_medflow_ohmu_focaldrift.zip --output ~/Documents/autofocus-test-data/results/allan/2022-11-17-113250_medflow_ohmu_focaldrift
echo "."
MS_SIMULATE=1 python3 infer.py --allan-dev --zarr ~/Documents/autofocus-test-data/2022-11-10-181748_focaldrift.zip --output ~/Documents/autofocus-test-data/results/allan/2022-11-10-181748_focaldrift
echo "."
