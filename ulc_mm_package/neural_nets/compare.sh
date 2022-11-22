#! /usr/bin/bash

#echo "base infer..."
#(time MS_BATCH="" ./infer_on_steps.sh;) &> base_infer_results.txt
echo "batch infer..."
(time MS_BATCH="batch" ./infer_on_steps.sh;) #&> batch_infer_results.txt
#echo "manual batch infer..."
#(time MS_BATCH="manual_batch" ./infer_on_steps.sh;) &> manual_batch_infer_results.txt
#echo "no infer..."
#(time MS_BATCH="no_infer" ./infer_on_steps.sh;) &> no_infer_results.txt

