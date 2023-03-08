#! /bin/bash

echo "starting allan dev calcs..."

mkdir -p ~/Documents/autofocus-test-data/results/allan

MS_SIMULATE=1 python3 infer.py --allan-dev --zarr ~/Documents/allan/2023-03-03-123831__allssaf1/2023-03-03-123831__allssaf1.zip --output ~/Documents/allan/results/allssaf1 --model "autofocus"
echo "."
#MS_SIMULATE=1 python3 infer.py --allan-dev --zarr ~/Documents/allan/2023-03-03-125005__allssaf2/2023-03-03-125005__allssaf2.zip --output ~/Documents/allan/results/allssaf2 --model "autofocus"
#echo "."
#MS_SIMULATE=1 python3 infer.py --allan-dev --zarr ~/Documents/allan/2023-03-03-130225__nomax1/2023-03-03-130225__nomax1.zip --output ~/Documents/allan/results/nomax1 --model "autofocus"
#echo "."
#MS_SIMULATE=1 python3 infer.py --allan-dev --zarr ~/Documents/allan/2023-03-03-131806__nomax2/2023-03-03-131806__nomax2.zip --output ~/Documents/allan/results/nomax2 --model "autofocus"
#echo "."
#MS_SIMULATE=1 python3 infer.py --allan-dev --zarr ~/Documents/allan/2023-03-03-132239__nomaxnoflowcontrol1/2023-03-03-132239__nomaxnoflowcontrol1.zip --output ~/Documents/allan/results/nomaxnoflowcontrol1 --model "autofocus"
#echo "."
#MS_SIMULATE=1 python3 infer.py --allan-dev --zarr ~/Documents/allan/2023-03-03-135043__nomaxnoflowcontrol2/2023-03-03-135043__nomaxnoflowcontrol2.zip --output ~/Documents/allan/results/nomaxnoflowcontrol2 --model "autofocus"
#echo "."
