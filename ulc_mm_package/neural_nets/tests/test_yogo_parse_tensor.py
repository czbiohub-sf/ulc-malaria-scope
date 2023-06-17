import unittest
import time

import numpy as np

from ulc_mm_package.neural_nets.YOGOInference import YOGO, AsyncInferenceResult

MOCK_YOGO_IMG_H = 772
MOCK_YOGO_IMG_W = 1032
MOCK_YOGO_OUTPUT = "mock_yogo_output.npy"
NUM_CLASSES = 7  # variable, older models predicted 5 classes


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
        self.assertEqual(d2, 5 + NUM_CLASSES)

    def test_filtered_tensor_shape(self):
        d1, d2 = YOGO.filter_res(self.mock_yogo_output).squeeze().shape

        self.assertEqual(d1, 5 + NUM_CLASSES)
        self.assertGreater(d2, 1)

    def test_parse_pred_tensor(self):
        parsed_predictions: np.ndarray = YOGO.parse_prediction_tensor(
            self.mock_yogo_output, self.img_h, self.img_w
        )
        d1, d2 = parsed_predictions.shape

        self.assertEqual(d1, 7)
        self.assertGreater(d2, 1)

    def test_parse_AsyncInferenceResult(self):
        res = AsyncInferenceResult(self.img_id, self.mock_yogo_output)
        parsed_predictions = YOGO.parse_prediction(res, self.img_h, self.img_w)
        d1, d2 = parsed_predictions.bboxes_and_classes.shape

        self.assertEqual(parsed_predictions.id, self.img_id)
        self.assertEqual(d1, 7)
        self.assertGreater(d2, 1)


if __name__ == "__main__":
    unittest.main()
