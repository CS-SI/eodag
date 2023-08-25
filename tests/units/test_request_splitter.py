import os
import unittest

from eodag.api.product.request_splitter import RequestSplitter
from tests import TEST_RESOURCES_PATH


class TestRequestSplitter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestRequestSplitter, cls).setUpClass()
        cls.constraints_file_path = os.path.join(
            TEST_RESOURCES_PATH, "constraints.json"
        )

    def test_split_timespan_by_year(self):
        metadata = {"year": "year", "month": "month", "day": "day", "time": "time"}
        multiselect_values = ["year", "month", "day", "time"]
        split_time_values = {"param": "year", "duration": 2}
        config = {
            "metadata_mapping": metadata,
            "multi_select_values": multiselect_values,
            "constraints_file_path": self.constraints_file_path,
            "products_split_timedelta": split_time_values,
        }
        splitter = RequestSplitter(config)
        result = splitter.get_time_slices("2000-02-01", "2004-05-30")
        self.assertEqual(2, len(result))
        expected_result = [
            {
                "year": ["2000", "2001"],
                "month": ["1", "2", "3", "4", "5"],
                "day": ["1", "10", "20", "25"],
                "time": ["01:00", "12:00", "18:00", "22:00"],
            },
            {
                "year": ["2002", "2003"],
                "month": ["1", "2", "3"],
                "day": ["1", "10", "20"],
                "time": ["01:00", "12:00", "18:00"],
            },
        ]
        self.assertDictEqual(expected_result[0], result[0])
