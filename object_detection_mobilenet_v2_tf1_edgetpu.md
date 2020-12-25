### Build docker and run it

It is recommended that you run object detection with tensorflow inside a Docker container, From the directory use Docker
you can do so using:
```buildoutcfg
docker build -t object_detection_docker:gpu_py36_cu90 -f Dockerfile .
```
Now you want to start a Docker container from your image, which is the virtual environment you will run your code in.
```buildoutcfg
nvidia-docker run -it -p <your port>:<exposed port> -v <your dir>:/<dirname inside docker> object_detection_docker:gpu_py36_cu90 bash
```
If you look in the Dockerfile, you can see that there are two ports exposed, one is typically used for Jupyter (8888)
and one for Tensorboard (6006). To be able to view these in your browser, you need map the port with the -p argument.
The -v arguments similarly maps directories. You can use multiple -p and -v arguments if you want to map multiple things.
The final 'bash' is to signify that you want to run bash (your usual Unix shell). 

If you want to launch a Jupyter notebook inside your container, you can do so with the following command:
```buildoutcfg
jupyter notebook --ip=0.0.0.0 --port=8888 --allow-root --no-browser
```
Then you can access your notebooks in your browser at:
```buildoutcfg
http://<your server name (e.g. fry)>:<whatever port you mapped to when starting up docker>
```
You will need to copy/paste the token generated in your Docker container.

### Clone and install luminoth-uv-imaging for using the utils
```
  pip install -e git+https://github.com/czbiohub/luminoth-uv-imaging.git
  export LC_ALL=C.UTF-8
  export LANG=C.UTF-8
```

### Clone the repo with the scripts. For reference, some of the instructions are from https://coral.ai/docs/edgetpu/retrain-detection/#using-the-coral-dev-board
```
git clone https://github.com/czbiohub/ulc-malaria-scope.git
cd ulc-malaria-scope/detection
```

### Convert to rgb jpgs - optional, only if the images are not 3 channeled jpgs
```
python3 convert_to_rgb_jpg.py -i /data/uv_microscopy_data/uv_multi_color/training_demo/annotations -o /data/uv_microscopy_data/uv_multi_color/training_demo/images/ -f png
```

### Use lumi to split to get train, val images, csv file
```
lumi split_train_val bb_labels.csv --output_dir lumi_csv --percentage 0.9 --random_seed 42 --input_image_format .jpg
```

### Convert to tf record given the training images and training csv file 
```
python3 generate_tfrecord.py --image_dir /data/uv_microscopy_data/uv_multi_color/training_demo/color_images_nov11/train --csv_input /data/uv_microscopy_data/uv_multi_color/training_demo/color_images_nov11/train.csv --output_path /data/uv_microscopy_data/uv_multi_color/training_demo/color_records_nov11/train.record
```

### Convert to tf record given the validation images and validation csv file 
```
python3 generate_tfrecord.py --image_dir /data/uv_microscopy_data/uv_multi_color/training_demo/color_images_nov11/val --csv_input /data/uv_microscopy_data/uv_multi_color/training_demo/color_images_nov11/val.csv --output_path /data/uv_microscopy_data/uv_multi_color/training_demo/color_records_nov11/val.record
```


### Prepare training data and config file, check for constants_cells.sh file
```
cd ../scripts
./prepare_checkpoint_and_dataset_cells.sh --network_type mobilenet_v2_ssd --train_whole_model true
NUM_TRAINING_STEPS=50000 && \
NUM_EVAL_STEPS=2000
```

### Start the training job
```
./retrain_detection_model_cells.sh \
--num_training_steps ${NUM_TRAINING_STEPS} \
--num_eval_steps ${NUM_EVAL_STEPS}
```

### From the Docker convert checkpoint graph from training to edge tpu model
```
./convert_checkpoint_to_edgetpu_tflite_cells.sh --checkpoint_num ${NUM_TRAINING_STEPS}

curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
sudo apt update
sudo apt-get install edgetpu-compiler

cd ${HOME}/google-coral/tutorials/docker/object_detection/out/models
edgetpu_compiler output_tflite_graph.tflite 
mv output_tflite_graph_edgetpu.tflite ssd_mobilenet_v2_cells_quant_edgetpu.tflite
```

### Now from where  the TPU is connected, (your PC or raspberry pi) install tflite runtime
For raspberry pi
```
pip3 install https://dl.google.com/coral/python/tflite_runtime-2.1.0.post1-cp35-cp35m-linux_armv7l.whl
pip3 install -r requirements_edgetpu.txt
```
For mac
```
pip3 install -r requirements_edgetpu.txt
pip3 install https://dl.google.com/coral/python/tflite_runtime-2.1.0.post1-cp35-cp35m-macosx_10_14_x86_64.whl
```


cd detection

### Run detection through for a folder of images, cd into detection code from ulc-malaria-scope
```
python3 detect_image.py \
  --model ${HOME}/ssd_mobilenet_v2_cells_quant_edgetpu.tflite \
  --labels ${HOME}/labels.txt \
  --input ${HOME}/ \
  --output cells_result/
```

### Confusion matrix and additional accuracy results install lumi dependencies and then clone, install lumi where you are running the below command from, If it is raspberry pi follow the instructions in lumi_installation_instruction_pi4.md

```
lumi confusion_matrix --groundtruth_csv /data/uv_microscopy_data/uv_multi_color/training_demo/images/val.csv --predicted_csv /data/ai_mosquito_data/lumi_csv/preds_val/preds_val.csv --output_txt /data/ai_mosquito_data/output.txt --classes_json /data/ai_mosquito_data/tfdata/classes.json --output_fig /data/ai_mosquito_data/cm.png
````

## Visualizing results

We strive to get useful and understandable summary and graph visualizations. We consider them to be essential not only for monitoring (duh!), but for getting a broader understanding of what's going under the hood. The same way it is important for code to be understandable and easy to follow, the computation graph should be as well.

By default summary and graph logs are saved to `jobs/` under the current directory. You can use TensorBoard by running:

```bash
tensorboard --logdir path/to/jobs
