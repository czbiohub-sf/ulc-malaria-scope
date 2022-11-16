#! /bin/bash

mkdir -p ~/Documents/steps

echo "starting inference"

MS_SIMULATE=1 python3 AutofocusInference.py ~/Documents/test-data/2022-11-03-164007-local_zstack > ~/Documents/steps/avt-03-11-164007-zstack.txt
echo "."
MS_SIMULATE=1 python3 AutofocusInference.py ~/Documents/test-data/2022-11-03-171427-local_zstack > ~/Documents/steps/avt-03-11-171427-zstack.txt
echo "."
MS_SIMULATE=1 python3 AutofocusInference.py ~/Documents/test-data/2022-08-11-123340-local_zstack > ~/Documents/steps/basler-08-11-123340-zstack.txt
echo "."
MS_SIMULATE=1 python3 AutofocusInference.py ~/Documents/test-data/2022-08-11-124116-local_zstack > ~/Documents/steps/basler-08-11-124116-zstack.txt
echo "."
