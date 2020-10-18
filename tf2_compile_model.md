`CORAL_DIR=${HOME}/google-coral && mkdir -p ${CORAL_DIR}
cd ${CORAL_DIR}
git clone https://github.com/google-coral/tutorials.git
cd tutorials/docker/object_detection
docker build . -t detect-tutorial-tf1
nvidia-docker run -it -p 4000:8888 -p 4001:6006 -v "/mnt/ibm_lg/pranathi:/data/" -v "/data/users/biohub/pranathi/code:/code/" detect-tutorial-tf1:latest bash
wget http://download.tensorflow.org/models/object_detection/tf2/20200711/ssd_resnet50_v1_fpn_640x640_coco17_tpu-
8.tar.gz
apt-get install cuda-cudart-10-1
python3.6 -m pip install tensorflow-gpu
`

`
wget http://download.tensorflow.org/models/object_detection/tf2/20200711/ssd_resnet50_v1_fpn_640x640_coco17_tpu-8.tar.gz
tar -xzf ssd_resnet50_v1_fpn_640x640_coco17_tpu-8.tar.gz .
# Use lumi to split and get transform to records but this might be different tensorflow version
lumi split_train_val annotated_bounding_boxes.txt annotated_bounding_boxes_1.txt annotated_bounding_boxes_2.txt --output_dir all_data_lumi_csv --percentage 0.9 --random_seed 42 --input_image_format .tif
lumi dataset transform --type csv --data-dir /lumi_csv/ --output-dir /tfdata/ --split train --split val --only-classes=table
`
`
python3.6 generate_tfrecord.py -i /data/uv_microscopy_data/uv_multi_color/training_demo/images/train -c /data/uv_microscopy_data/uv_multi_color/training_demo/images/train.csv -l /data/uv_microscopy_data/uv_multi_color/training_demo/annotations/label_map.pbtxt -o /data/uv_microscopy_data/uv_multi_color/training_demo/annotations/train.record
`
`
python3.6 generate_tfrecord.py -i /data/uv_microscopy_data/uv_multi_color/training_demo/images/val -c /data/uv_microscopy_data/uv_multi_color/training_demo/images/val.csv -l /data/uv_microscopy_data/uv_multi_color/training_demo/annotations/label_map.pbtxt -o /data/uv_microscopy_data/uv_multi_color/training_demo/annotations/val.record
`
`
add-apt-repository ppa:deadsnakes/ppa
apt-get update
apt-get install python3.6-dev
apt-get install python3-pip
apt-get install python3.6
python3.6 -m pip install --upgrade pip

python3 -m pip install absl-py
python3.6 -m pip install --ignore-installed --upgrade tensorflow==2.2.0
python3.6 -m pip install tf_slim
python3.6 -m pip install matplotlib
python3.6 -m pip install pycocotools
protoc object_detection/protos/*.proto --python_out=.
https://tensorflow-object-detection-api-tutorial.readthedocs.io/en/latest/install.html#tf-models-install
mkdir code

git clone https://github.com/tensorflow/models.git
git clone https://github.com/tensorflow/tutorials.git

export TF_FORCE_GPU_ALLOW_GROWTH=true


python3.6 object_detection/model_main_tf2.py --model_dir=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn --pipeline_config_path=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn/pipeline.config

INPUT_TENSORS='normalized_input_image_tensor'
OUTPUT_TENSORS='TFLite_Detection_PostProcess,TFLite_Detection_PostProcess:1,TFLite_Detection_PostProcess:2,TFLite_Detection_PostProcess:3'

python3.6 ${RESEARCH_DIR}/object_detection/export_tflite_graph_tf2.py --pipeline_config_path=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn/pipeline.config --trained_checkpoint_dir=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn/ --output_directory=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn/out/ --ssd_max_detections=50


tflite_convert \
  --output_file=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn/out/output_tflite_graph.tflite \
  --saved_model_dir=/data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn/out/saved_model/ \
  --inference_type=QUANTIZED_UINT8 \
  --input_arrays="${INPUT_TENSORS}" \
  --output_arrays="${OUTPUT_TENSORS}" \
  --mean_values=128 \
  --std_dev_values=128 \
  --input_shapes=1,300,300,3 \
  --change_concat_input_ranges=false \
  --allow_nudging_weights_to_use_fast_gemm_kernel=true \
  --allow_custom_ops

edgetpu_compiler /data/uv_microscopy_data/uv_multi_color/training_demo/models/my_ssd_resnet50_v1_fpn/out/output_tflite_graph.tflite
`
