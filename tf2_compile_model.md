# Starting docker container for object detection
```
  CORAL_DIR=${HOME}/google-coral && mkdir -p ${CORAL_DIR}
  cd ${CORAL_DIR}
  git clone https://github.com/google-coral/tutorials.git
  cd tutorials/docker/object_detection
  docker build . -t detect-tutorial-tf1
  nvidia-docker run -it -p 4000:8888 -p 4001:6006 -v "/mnt/ibm_lg/pranathi:/data/" -v "/data/users/biohub/pranathi/code:/code/" detect-tutorial-tf1:latest bash
  wget http://download.tensorflow.org/models/object_detection/tf2/20200711/ssd_resnet50_v1_fpn_640x640_coco17_tpu-
  8.tar.gz
  apt-get install cuda-cudart-10-1
  python3.6 -m pip install tensorflow-gpu
```

# Train
`
python3.6 ${RESEARCH_DIR}/object_detection/model_main_tf2.py --model_dir=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn_sep24 --pipeline_config_path=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn/pipeline.config 
`

# Evaluation
`
python3.6 ${RESEARCH_DIR}/object_detection/model_main_tf2.py --model_dir=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn --pipeline_config_path=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn/pipeline.config --checkpoint_dir=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn
`

# Convert checkpoint to savedmodel
`
python3.6 ${RESEARCH_DIR}/object_detection/exporter_main_v2.py --input_type image_tensor --pipeline_config_path /data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn/pipeline.config --trained_checkpoint_dir /data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn_sep24 --output_directory /data/uv_microscopy_data/uv_multi_color/training_demo/models/export_sep25/
`

# Convert checkpoint to savedmodel
`
python3.6 ${RESEARCH_DIR}/object_detection/export_tflite_graph_tf2.py --pipeline_config_path=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn/pipeline.config --trained_checkpoint_dir=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn_sep24 --output_directory=/data/uv_microscopy_data/uv_multi_color/training_demo/models/export_sep28/
`

# Saved model to tflite 2 tensorflow 2 version
```
INPUT_TENSORS='normalized_input_image_tensor'
OUTPUT_TENSORS='TFLite_Detection_PostProcess,TFLite_Detection_PostProcess:1,TFLite_Detection_PostProcess:2,TFLite_Detection_PostProcess:3'
tflite_convert \
  --output_file=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn/detect.tflite \
  --saved_model_dir=/data/uv_microscopy_data/uv_multi_color/training_demo/models/export_sep25/saved_model/ \
  --inference_type=QUANTIZED_UINT8 \
  --input_arrays="${INPUT_TENSORS}" \
  --output_arrays="${OUTPUT_TENSORS}" \
  --mean_values=128 \
  --std_dev_values=128 \
  --input_shapes=1,1024,768,3 \
  --change_concat_input_ranges=false \
  --allow_nudging_weights_to_use_fast_gemm_kernel=true \
  --allow_custom_ops
```
# Saved model to edge tpu compatible tflite tensorflow 2 version
`
edgetpu_compiler /data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn/out/output_tflite_graph.tflite
`
