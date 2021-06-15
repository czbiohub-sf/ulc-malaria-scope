import argparse
import os

import tensorflow as tf
from luminoth.utils.config import get_config

# Program to convert lumi checkpoint to tflite model


def convert_lumi_to_tflite(config_file, output_dir):
    config = get_config(config_file)

    graph = tf.Graph()
    session = tf.Session(graph=graph)

    with graph.as_default():

        # Restore checkpoint
        if config.train.job_dir:
            job_dir = config.train.job_dir
            if config.train.run_name:
                job_dir = os.path.join(job_dir, config.train.run_name)
            ckpt = tf.train.get_checkpoint_state(job_dir)
            if not ckpt or not ckpt.all_model_checkpoint_paths:
                raise ValueError("Could not find checkpoint in {}.".format(job_dir))
            ckpt = ckpt.all_model_checkpoint_paths[-1]
            saver = tf.train.Saver(sharded=True, allow_empty=True)
            saver.restore(session, ckpt)
            tf.logging.info("Loaded checkpoint.")
        else:
            # A prediction without checkpoint is just used for testing
            tf.logging.warning("Could not load checkpoint. Using initialized model.")
            init_op = tf.group(
                tf.global_variables_initializer(), tf.local_variables_initializer()
            )
            session.run(init_op)
        # Restore variables from disk.
        builder = tf.saved_model.builder.SavedModelBuilder(output_dir)
        builder.add_meta_graph_and_variables(
            session,
            [tf.saved_model.TRAINING, tf.saved_model.SERVING],
            strip_default_attrs=True,
        )
        builder.save()

    # Convert the model
    converter = tf.lite.TFLiteConverter.from_saved_model(output_dir)
    tflite_model = converter.convert()

    # Save the model.
    with open(os.path.join(output_dir, "model.tflite"), "wb") as f:
        f.write(tflite_model)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        required=True,
        help="File path of output dir where tflite and export_dir"
        + " for SavedModel should be stored",
    )
    parser.add_argument(
        "--config_file",
        type=str,
        dest="config_file",
        help="config file",
        metavar="CONFIG_FILE",
        required=True,
    )
    args = parser.parse_args()
    convert_lumi_to_tflite(args.config_file, os.path.abspath(args.output_dir))


if __name__ == "__main__":
    main()
