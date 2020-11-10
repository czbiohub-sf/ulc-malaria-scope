### Clone the repo with the scripts
git clone https://github.com/czbiohub/ulc-malaria-scope.git
cd ulc-malaria-scope/scripts

### Prepare training data and config file
./prepare_checkpoint_and_dataset.sh --network_type mobilenet_v1_ssd --train_whole_model false
NUM_TRAINING_STEPS=50000 && \
NUM_EVAL_STEPS=2000

### Start the training job: From the /tensorflow/models/research/ directory
./retrain_detection_model.sh \
--num_training_steps ${NUM_TRAINING_STEPS} \
--num_eval_steps ${NUM_EVAL_STEPS}

### From the Docker /tensorflow/models/research directory
./convert_checkpoint_to_edgetpu_tflite.sh --checkpoint_num ${NUM_TRAINING_STEPS}
cd ${HOME}/google-coral/tutorials/docker/object_detection/out/models
mv output_tflite_graph_edgetpu.tflite ssd_mobilenet_v2_cells_quant_edgetpu.tflite

### Now from the Dev Board shell (could be where the TPU is connected, your PC or raspberry pi), cd into detection code

### Install the example's requirements:

cd tflite/python/examples/detection
./install_requirements.sh

### Run detection through for a folder of images

python3 detect_image.py \
  --model ${HOME}/ssd_mobilenet_v2_cells_quant_edgetpu.tflite \
  --labels ${HOME}/labels.txt \
  --input ${HOME}/ \
  --output cells_result/

### Docker

It is recommended that you run object detection with tensorflow inside a Docker container, 
you can do so using:
```buildoutcfg
docker build -t object_detection_docker:gpu_py36_cu90 -f Dockerfile.object_detection_docker_py36_cu90 .
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

## Visualizing results

We strive to get useful and understandable summary and graph visualizations. We consider them to be essential not only for monitoring (duh!), but for getting a broader understanding of what's going under the hood. The same way it is important for code to be understandable and easy to follow, the computation graph should be as well.

By default summary and graph logs are saved to `jobs/` under the current directory. You can use TensorBoard by running:

```bash
tensorboard --logdir path/to/jobs