import argparse
import os
import re

import tensorflow as tf
from luminoth.datasets import get_dataset
from luminoth.models import get_model
from luminoth.utils.config import get_config
from luminoth.utils.training import get_optimizer, clip_gradients_by_norm
# Program to convert lumi checkpoint to tflite model


def convert_lumi_to_tflite(model, config_file, checkpoint, output_dir):
    # path to the SavedModel directory
    tf.reset_default_graph()
    saver = tf.train.import_meta_graph(model)
    builder = tf.saved_model.builder.SavedModelBuilder(output_dir)
    # Create custom init for slots in optimizer, as we don't save them to
    # our checkpoints. An example of slots in an optimizer are the Momentum
    # variables in MomentumOptimizer. We do this because slot variables can
    # effectively duplicate the size of your checkpoint!
    config = get_config(config_file)
    model_class = get_model(config.model.type)
    model = model_class(config)
    dataset_class = get_dataset(config.dataset.type)
    dataset = dataset_class(config)
    train_dataset = dataset()
    train_image = train_dataset['image']
    train_bboxes = train_dataset['bboxes']

    prediction_dict = model(train_image, train_bboxes, is_training=False)
    total_loss = model.loss(prediction_dict)
    global_step = re.findall(r'[0-9]+', os.path.basename(checkpoint))
    optimizer = get_optimizer(config.train, global_step)
    trainable_vars = model.get_trainable_vars()
    # Compute, clip and apply gradients
    with tf.name_scope('gradients'):
        grads_and_vars = optimizer.compute_gradients(
            total_loss, trainable_vars
        )

        if config.train.clip_by_norm:
            grads_and_vars = clip_gradients_by_norm(grads_and_vars)

    # update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
    # with tf.control_dependencies(update_ops):
    #     optimizer.apply_gradients(
    #         grads_and_vars, global_step=global_step
    #     )
    slot_variables = [
        optimizer.get_slot(var, name)
        for name in optimizer.get_slot_names()
        for var in trainable_vars
    ]
    slot_init = tf.variables_initializer(
        slot_variables)

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
    converter = tf.lite.TFLiteConverter.from_saved_model(output_dir)
    tflite_model = converter.convert()

    # Save the model.
    with open(os.path.join(output_dir, 'model.tflite'), 'wb') as f:
        f.write(tflite_model)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-o', '--output_dir', required=True,
        help='File path of output dir where tflite and export_dir' +
        ' for SavedModel should be stored')
    parser.add_argument(
        '--checkpoint', type=str,
        dest='checkpoint',
        help='dir or .ckpt file to load checkpoint from',
        metavar='CHECKPOINT', required=True)
    parser.add_argument(
        '--config_file', type=str,
        dest='config_file',
        help='config file',
        metavar='CONFIG_FILE', required=True)
    parser.add_argument(
        '--model', type=str,
        dest='model',
        help='.meta for your model',
        metavar='MODEL', required=True)
    args = parser.parse_args()
    convert_lumi_to_tflite(
        args.model, args.config_file,
        args.checkpoint, os.path.abspath(args.output_dir))


if __name__ == '__main__':
    main()
