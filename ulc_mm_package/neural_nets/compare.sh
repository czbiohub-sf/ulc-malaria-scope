#! /usr/bin/bash

echo "base infer..."
(time MS_BATCH="" ./infer_on_steps.sh;) &> base_infer_results.txt
echo "asyn infer..."
(time MS_BATCH="asyn_infer" ./infer_on_steps.sh;) &> asyn_infer_results.txt
echo "no infer..."
(time MS_BATCH="no_infer" ./infer_on_steps.sh;) &> no_infer_results.txt

