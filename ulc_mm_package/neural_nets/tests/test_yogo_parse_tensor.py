import unittest
import time

import numpy as np

from ulc_mm_package.neural_nets.YOGOInference import YOGO
from ulc_mm_package.neural_nets.utils import (
    get_all_argmax_class_confidences_for_all_classes,
    get_all_argmax_confs_for_specific_class,
    get_all_confs_for_all_classes,
    get_all_confs_for_specific_class,
    get_class_counts,
    nms,
    parse_prediction_tensor,
    get_specific_class_from_parsed_tensor,
    get_vals_greater_than_conf_thresh,
    get_vals_less_than_conf_thresh,
    get_individual_prediction_objs_from_parsed_tensor,
    DTYPE,
)

from ulc_mm_package.neural_nets.predictions_handler import (
    NUM_CLASSES,
)

MOCK_YOGO_IMG_H = 772
MOCK_YOGO_IMG_W = 1032
MOCK_YOGO_OUTPUT = "mock_yogo_output.npy"
MOCK_OUTPUT_NUM_CLASSES = (
    7  # the mock output I used was from a newer model which predicts 7 classes
)


class TestYOGOTensorParsing(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestYOGOTensorParsing, self).__init__(*args, **kwargs)

        self.img_id = 0
        self.img_h = MOCK_YOGO_IMG_H
        self.img_w = MOCK_YOGO_IMG_W
        self.raw_mock_yogo_output: np.ndarray = np.load(
            MOCK_YOGO_OUTPUT
        )  # 1 x (5+NUM_CLASSES) x 97 x 129
        self.mock_yogo_output = YOGO._format_res(
            self.raw_mock_yogo_output
        )  # 1 x (5+NUM_CLASSES) x 12,513

    def setUp(self):
        self.parsed_predictions = parse_prediction_tensor(
            self.img_id, self.mock_yogo_output, self.img_h, self.img_w
        )
        self.start_time = time.time()

    def tearDown(self):
        t = time.time() - self.start_time
        print(f"{self.id()} - {t*1e6:.1f}us")

    def test_verify_raw_yogo_output_shape(self):
        (
            d1,
            d2,
            _,
        ) = self.mock_yogo_output.shape

        self.assertEqual(d1, 1)
        self.assertEqual(d2, 5 + MOCK_OUTPUT_NUM_CLASSES)

    def test_filtered_tensor_shape(self):
        d1, d2 = YOGO.filter_res(self.mock_yogo_output).squeeze().shape

        self.assertEqual(d1, 5 + MOCK_OUTPUT_NUM_CLASSES)
        self.assertGreater(d2, 1)

    def test_parse_pred_tensor(self):
        d1, d2 = self.parsed_predictions.shape

        self.assertEqual(d1, 8 + MOCK_OUTPUT_NUM_CLASSES)
        self.assertGreater(d2, 1)
        self.assertEqual(self.parsed_predictions.dtype, DTYPE)

    def test_get_specific_class(self):
        healthy_cells = get_specific_class_from_parsed_tensor(
            self.parsed_predictions, 0
        )

        self.assertGreater(healthy_cells.shape[1], 0)

    def test_get_vals_greater_than_conf_thresh(self):
        healthy_cells = get_specific_class_from_parsed_tensor(
            self.parsed_predictions, 0
        )
        above_thresh = get_vals_greater_than_conf_thresh(healthy_cells, 0.9)

        self.assertEqual(above_thresh.shape[0], healthy_cells.shape[0])
        self.assertLess(above_thresh.shape[1], healthy_cells.shape[1])

    def test_get_vals_less_than_conf_thresh(self):
        healthy_cells = get_specific_class_from_parsed_tensor(
            self.parsed_predictions, 0
        )
        below_thresh = get_vals_less_than_conf_thresh(healthy_cells, 0.9)

        self.assertEqual(below_thresh.shape[0], healthy_cells.shape[0])
        self.assertLess(below_thresh.shape[1], healthy_cells.shape[1])

    def test_get_individual_prediction_objs(self):
        single_objs = get_individual_prediction_objs_from_parsed_tensor(
            self.parsed_predictions, ([0, 1, 3]), flip_conf_sign=False
        )

        self.assertEqual(len(single_objs), 3)
        self.assertEqual(single_objs[0].parsed.dtype, DTYPE)
        self.assertEqual(single_objs[0].parsed.shape[0], 8 + MOCK_OUTPUT_NUM_CLASSES)

    def test_get_all_argmax_confs_for_specific_class(self):
        class_id = 0
        healthy_confs = get_all_argmax_confs_for_specific_class(
            class_id, self.parsed_predictions
        )

        self.assertGreater(healthy_confs.shape[0], 0)
        self.assertGreater(np.mean(healthy_confs), 0.9)

    def get_all_argmax_class_confidences_for_all_classes(self):
        all_confs = get_all_argmax_class_confidences_for_all_classes(
            self.parsed_predictions
        )

        self.assertEqual(len(all_confs), NUM_CLASSES)

    def test_get_all_confs_for_specific_class(self):
        class_id = 0
        all_healthy_confs = get_all_confs_for_specific_class(
            class_id, self.parsed_predictions
        )

        self.assertGreater(all_healthy_confs.shape[0], 0)
        self.assertGreater(np.mean(all_healthy_confs), 0.9)

    def test_get_all_confs_for_all_classes(self):
        all_confs = get_all_confs_for_all_classes(self.parsed_predictions)

        self.assertEqual(len(all_confs), NUM_CLASSES)

    def test_get_class_counts(self):
        class_counts = get_class_counts(self.parsed_predictions)

        self.assertEqual(len(class_counts), NUM_CLASSES)
        self.assertGreater(class_counts[0], 0)

    def test_nms(self):
        # Add more robust tests later, this is just a quick
        # no dumb run-time crashes check
        keep_idxs = nms(self.parsed_predictions, 0.5)
        self.assertEqual(self.parsed_predictions.shape[1], 58)
        self.assertEqual(len(keep_idxs), 47)


if __name__ == "__main__":
    unittest.main()
