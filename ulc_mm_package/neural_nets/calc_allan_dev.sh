#! /bin/bash

echo "starting allan dev calcs..."

mkdir -p ~/Documents/autofocus-test-data/results/allan

MS_SIMULATE=1 python3 infer.py --allan-dev --zarr ~/Documents/autofocus-test-data/2022-11-17-112855_medflow_ohmu_focaldrift.zip --output ~/Documents/autofocus-test-data/results/allan/2022-11-17-112855_medflow_ohmu_focaldrift.png
echo "."
MS_SIMULATE=1 python3 infer.py --allan-dev --zarr ~/Documents/autofocus-test-data/2022-11-17-113250_medflow_ohmu_focaldrift.zip --output ~/Documents/autofocus-test-data/results/allan/2022-11-17-113250_medflow_ohmu_focaldrift.png
echo "."
MS_SIMULATE=1 python3 infer.py --allan-dev --zarr ~/Documents/autofocus-test-data/2022-11-10-181748_focaldrift.zip --output ~/Documents/autofocus-test-data/results/allan/2022-11-10-181748_focaldrift.png
echo "."
