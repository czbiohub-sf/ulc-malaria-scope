import os
import tensorflow as tf

trained_checkpoint_prefix = '/data/ai_mosquito_data/jobs_frcnn_oct17_alameda_mosquito/frcnn-oct17-alameda-mosquito/model.ckpt-49652'
export_dir = os.path.join('export_dir', '0')

graph = tf.Graph()
with tf.Session(graph=graph) as sess:
	# Restore from checkpoint
	loader = tf.train.import_meta_graph(trained_checkpoint_prefix + '.meta')
	loader.restore(sess, trained_checkpoint_prefix)

	# Export checkpoint to SavedModel
	builder = tf.saved_model.builder.SavedModelBuilder(export_dir)
	builder.add_meta_graph_and_variables(sess,
		[tf.saved_model.TRAINING, tf.saved_model.SERVING],
		strip_default_attrs=True)
	builder.save()

# Convert the model
converter = tf.lite.TFLiteConverter.from_saved_model(export_dir) # path to the SavedModel directory
tflite_model = converter.convert()

# Save the model.
with open('model.tflite', 'wb') as f:
	f.write(tflite_model)
