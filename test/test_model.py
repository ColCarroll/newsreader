import unittest
from model import Features


class TestFeatures(unittest.TestCase):
    def setUp(self):
        self.features = Features()

    def test_features(self):
        self.assertEqual(self.features.features.shape[0], self.features.labels.shape[0],
                         "Features and labels must have the same length")
