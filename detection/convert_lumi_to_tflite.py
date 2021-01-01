import argparse
import os

import tensorflow as tf

# Program to convert lumi checkpoint to tflite model


def convert_lumi_to_tflite(trained_checkpoint_prefix, output_dir):
    # path to the SavedModel directory
    export_dir = os.path.join(output_dir, '0')
    graph = tf.Graph()
    with tf.Session(graph=graph) as sess:
        sess.run(tf.local_variables_initializer())
        # Restore from checkpoint
        loader = tf.train.import_meta_graph(
            trained_checkpoint_prefix + '.meta')
        loader.restore(sess, trained_checkpoint_prefix)

        # Export checkpoint to SavedModel
        builder = tf.saved_model.builder.SavedModelBuilder(export_dir)
        builder.add_meta_graph_and_variables(
            sess, ["train", "serve"])
        builder.save()

    # Convert the model
    converter = tf.lite.TFLiteConverter.from_saved_model(export_dir)
    tflite_model = converter.convert()

    # Save the model.
    with open(os.path.join(output_dir, 'model.tflite'), 'wb') as f:
        f.write(tflite_model)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-o', '--output_dir', required=True,
        help='File path of output dir where tflite and export_dir for SavedModel should eb stored')
    parser.add_argument(
        '-i', '--trained_checkpoint_prefix', required=True,
        help='File path of checkpoint to convert')
    args = parser.parse_args()
    path = os.path.abspath(args.output_dir)
    if not os.path.exists(path):
        os.makedirs(path)
    else:
        print("Path {} already exists, might be overwriting data".format(path))
    convert_lumi_to_tflite(args.trained_checkpoint_prefix, path)


if __name__ == '__main__':
    main()
