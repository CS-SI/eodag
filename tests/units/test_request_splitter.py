import datetime
import os
import unittest

from eodag.api.product.request_splitter import RequestSplitter
from eodag.config import PluginConfig
from eodag.utils.exceptions import MisconfiguredError
from tests import TEST_RESOURCES_PATH


class TestRequestSplitter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestRequestSplitter, cls).setUpClass()
        cls.constraints_file_path = os.path.join(
            TEST_RESOURCES_PATH, "constraints.json"
        )

    def test_invalid_config(self):
        metadata = {"year": "year", "month": "month", "day": "day", "time": "time"}
        multiselect_values = ["year"]
        split_time_values = {"param": "year", "duration": 2}
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": multiselect_values,
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
            }
        )
        with self.assertRaises(MisconfiguredError):
            RequestSplitter(config)

    def test_split_timespan_by_year(self):
        metadata = {"year": "year", "month": "month", "day": "day", "time": "time"}
        multiselect_values = ["year", "month", "day", "time"]
        split_time_values = {"param": "year", "duration": 2}
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": multiselect_values,
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
            }
        )
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
        self.assertDictEqual(expected_result[1], result[1])
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": ["month", "day", "time"],
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
            }
        )
        splitter = RequestSplitter(config)
        result = splitter.get_time_slices("2000-02-01", "2004-05-30")
        self.assertEqual(4, len(result))
        expected_result = [
            {
                "year": ["2000"],
                "month": ["1", "2", "3", "4", "5"],
                "day": ["1", "10", "20", "25"],
                "time": ["01:00", "12:00", "18:00", "22:00"],
            },
            {
                "year": ["2001"],
                "month": ["1", "2", "3", "4", "5"],
                "day": ["1", "10", "20", "25"],
                "time": ["01:00", "12:00", "18:00", "22:00"],
            },
            {
                "year": ["2002"],
                "month": ["1", "2", "3"],
                "day": ["1", "10", "20"],
                "time": ["01:00", "12:00", "18:00"],
            },
            {
                "year": ["2003"],
                "month": ["1", "2", "3"],
                "day": ["1", "10", "20"],
                "time": ["01:00", "12:00", "18:00"],
            },
        ]
        self.assertDictEqual(expected_result[0], result[0])
        self.assertDictEqual(expected_result[1], result[1])
        self.assertDictEqual(expected_result[2], result[2])
        self.assertDictEqual(expected_result[3], result[3])

    def test_split_timespan_by_month(self):
        metadata = {"year": "year", "month": "month", "day": "day", "time": "time"}
        multiselect_values = ["year", "month", "day", "time"]
        split_time_values = {"param": "month", "duration": 2}
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": multiselect_values,
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
            }
        )
        splitter = RequestSplitter(config)
        result = splitter.get_time_slices("2000-01-01", "2001-06-30")
        self.assertEqual(4, len(result))
        expected_result_row_1 = {
            "year": ["2000"],
            "month": ["1", "2"],
            "day": ["1", "10", "20", "25"],
            "time": ["01:00", "12:00", "18:00", "22:00"],
        }
        expected_result_row_3 = {
            "year": ["2001"],
            "month": ["1", "2"],
            "day": ["1", "10", "20", "25"],
            "time": ["01:00", "12:00", "18:00", "22:00"],
        }
        self.assertDictEqual(expected_result_row_1, result[0])
        self.assertDictEqual(expected_result_row_3, result[2])
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": ["year", "day", "time"],
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
            }
        )
        splitter = RequestSplitter(config)
        result = splitter.get_time_slices("2000-01-01", "2001-06-30")
        self.assertEqual(13, len(result))
        expected_result_row_1 = {
            "year": ["2000"],
            "month": ["1"],
            "day": ["1", "10", "20", "25"],
            "time": ["01:00", "12:00", "18:00", "22:00"],
        }
        expected_result_row_6 = {
            "year": ["2000"],
            "month": ["6"],
            "day": ["3", "5"],
            "time": ["01:00", "12:00", "18:00", "22:00"],
        }
        self.assertDictEqual(expected_result_row_1, result[0])
        self.assertDictEqual(expected_result_row_6, result[5])

    def test_split_timespan_by_year_with_dates(self):
        metadata = {
            "startTimeFromAscendingNode": [
                "date=startTimeFromAscendingNode/to/completionTimeFromAscendingNode",
                "$.date",
            ],
            "completionTimeFromAscendingNode": "$.date",
        }
        multiselect_values = []
        split_time_values = {"param": "year", "duration": 2}
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": multiselect_values,
                "constraints_file_path": os.path.join(
                    TEST_RESOURCES_PATH, "constraints_dates.json"
                ),
                "products_split_timedelta": split_time_values,
            }
        )
        splitter = RequestSplitter(config)
        result = splitter.get_time_slices("1999-02-01", "2004-05-30")
        self.assertEqual(3, len(result))
        expected_result = [
            {
                "start_date": datetime.datetime(2000, 1, 1),
                "end_date": datetime.datetime(2001, 12, 31),
            },
            {
                "start_date": datetime.datetime(2002, 1, 1),
                "end_date": datetime.datetime(2003, 12, 31),
            },
            {
                "start_date": datetime.datetime(2004, 1, 1),
                "end_date": datetime.datetime(2004, 12, 31),
            },
        ]
        self.assertDictEqual(expected_result[0], result[0])
        self.assertDictEqual(expected_result[1], result[1])
        self.assertDictEqual(expected_result[2], result[2])

    def test_split_timespan_by_month_with_dates(self):
        metadata = {
            "startTimeFromAscendingNode": [
                "date=startTimeFromAscendingNode/to/completionTimeFromAscendingNode",
                "$.date",
            ],
            "completionTimeFromAscendingNode": "$.date",
        }
        multiselect_values = []
        split_time_values = {"param": "month", "duration": 2}
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": multiselect_values,
                "constraints_file_path": os.path.join(
                    TEST_RESOURCES_PATH, "constraints_dates.json"
                ),
                "products_split_timedelta": split_time_values,
            }
        )
        splitter = RequestSplitter(config)
        result = splitter.get_time_slices("1999-02-01", "2001-06-30")
        self.assertEqual(9, len(result))
        expected_result_row_1 = {
            "start_date": datetime.datetime(2000, 2, 1),
            "end_date": datetime.datetime(2000, 3, 31),
        }
        expected_result_row_6 = {
            "start_date": datetime.datetime(2000, 12, 1),
            "end_date": datetime.datetime(2001, 1, 31),
        }
        expected_result_row_9 = {
            "start_date": datetime.datetime(2001, 6, 1),
            "end_date": datetime.datetime(2001, 6, 30),
        }
        self.assertDictEqual(expected_result_row_1, result[0])
        self.assertDictEqual(expected_result_row_6, result[5])
        self.assertDictEqual(expected_result_row_9, result[8])
