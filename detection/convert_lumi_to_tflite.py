import argparse
import os

import tensorflow as tf

# Program to convert lumi checkpoint to tflite model


def convert_lumi_to_tflite(model, checkpoint, output_dir):
    # path to the SavedModel directory
    export_dir = os.path.join(output_dir)
    tf.reset_default_graph()
    saver = tf.train.import_meta_graph(model)
    builder = tf.saved_model.builder.SavedModelBuilder(output_dir)
    with tf.Session() as sess:
        # Restore variables from disk.
        saver.restore(sess, checkpoint)
        print("Model restored.")
        builder.add_meta_graph_and_variables(
            sess,
            ['tfckpt2pb'],
            strip_default_attrs=False)
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
        help='File path of output dir where tflite and export_dir for SavedModel should be stored')
    parser.add_argument('--checkpoint', type=str,
                        dest='checkpoint',
                        help='dir or .ckpt file to load checkpoint from',
                        metavar='CHECKPOINT', required=True)
    parser.add_argument('--model', type=str,
                        dest='model',
                        help='.meta for your model',
                        metavar='MODEL', required=True)
    args = parser.parse_args()
    convert_lumi_to_tflite(args.model, args.checkpoint, path)


if __name__ == '__main__':
    main()
