import datetime
import json
import re

from eodag.utils.exceptions import MisconfiguredError


def _hour_from_time(time):
    return int(time[:2])


class RequestSplitter:
    """
    provides methods to split a request into several requests based on the given config and constraints
    """

    def __init__(self, config):
        self.config = config.__dict__
        with open(self.config["constraints_file_path"]) as f:
            self.constraints = json.load(f)
        self.metadata = self.config["metadata_mapping"]
        if "multi_select_values" in self.config:
            self.multi_select_values = self.config["multi_select_values"]
        else:
            self.multi_select_values = []
        self.split_time_delta = self.config["products_split_timedelta"]
        self._check_config_valid()

    def _check_config_valid(self):
        split_param = self.split_time_delta["param"]
        if (
            split_param == "year"
            and "month" in self.metadata
            and "month" not in self.multi_select_values
        ):
            raise MisconfiguredError(
                "Configuration error: data cannot be split by "
                "year, choose a smaller granularity"
            )
        if (
            split_param == "month"
            and "day" in self.metadata
            and "day" not in self.multi_select_values
        ):
            raise MisconfiguredError(
                "Configuration error: data cannot be split by "
                "month, choose a smaller granularity"
            )

    def get_time_slices(self, start_date, end_date):
        """
        splits a timespan into slices based on the given config and constraints
        """
        split_param = self.split_time_delta["param"]
        slice_duration = self.split_time_delta["duration"]
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])
        if split_param == "year":
            return self._split_by_year(start_year, end_year, slice_duration)
        elif split_param == "month":
            start_month = int(start_date[5:7])
            end_month = int(end_date[5:7])
            return self._split_by_month(
                start_year, end_year, start_month, end_month, slice_duration
            )

    def _split_by_year(self, start_year, end_year, slice_duration):
        if "year" not in self.metadata:
            return self._split_by_year_with_dates(start_year, end_year, slice_duration)
        if "year" in self.multi_select_values:
            num_years = slice_duration
        else:
            num_years = 1
        i = 0
        years = []
        years_slice = []
        for y in range(start_year, end_year + 1):
            if i < num_years:
                years_slice.append(str(y))
                i += 1
            else:
                years.append(years_slice)
                years_slice = [str(y)]
                i = 1
        slices = []
        for row in years:
            record = {"year": row}
            if "month" in self.metadata:
                months = self._get_months_for_years(row)
                record["month"] = months
            if "day" in self.metadata:
                days = self._get_days_for_months_and_years(months, row)
                record["day"] = days
            if "time" in self.metadata:
                times = self._get_times_for_days_months_and_years(days, months, row)
                record["time"] = times
            slices.append(self._sort_record(record))
        return slices

    def _split_by_month(
        self, start_year, end_year, start_month, end_month, slice_duration
    ):
        if "month" not in self.metadata:
            return self._split_by_month_with_dates(
                start_year, end_year, start_month, end_month, slice_duration
            )
        if "month" in self.multi_select_values:
            num_months = slice_duration
        else:
            num_months = 1
        i = 0
        months_years = []
        months_slice = []
        m = start_month
        for y in range(start_year, end_year + 1):
            while (m <= 12 and y < end_year) or (m <= end_month and y == end_year):
                if i < num_months:
                    months_slice.append(str(m))
                    i += 1
                else:
                    months_years.append({"year": [str(y)], "month": months_slice})
                    months_slice = [str(m)]
                    i = 1
                if m == 12 or m == end_month and y == end_year:
                    # don't create slices that go over 2 years because this cannot be configured with multiselect boxes
                    months_years.append({"year": [str(y)], "month": months_slice})
                m += 1
            m = 1
            i = 0
            months_slice = []

        slices = []
        for row in months_years:
            record = {"year": row["year"], "month": row["month"]}
            days = []
            if "day" in self.metadata:
                days = self._get_days_for_months_and_years(row["month"], row["year"])
                if len(days) == 0:
                    continue
                record["day"] = days
            if "time" in self.metadata:
                times = self._get_times_for_days_months_and_years(
                    days, row["month"], row["year"]
                )
                if len(days) == 0:
                    continue
                record["time"] = times
            slices.append(self._sort_record(record))
        return slices

    def _get_months_for_years(self, years):
        months = {str(i) for i in range(1, 13)}
        for year in years:
            possible_months = self._get_months_for_year(year)
            months = months.intersection(set(possible_months))
        return list(months)

    def _get_months_for_year(self, year):
        months = []
        for constraint in self.constraints:
            if year in constraint["year"] and len(months) < len(constraint["month"]):
                months = constraint["month"]
        return months

    def _get_days_for_months_and_years(self, months, years):
        days = {str(i) for i in range(1, 32)}
        for month in months:
            constraints = self._get_constraints_for_month(month)
            possible_days = []
            for constraint in constraints:
                if len(set(years).intersection(set(constraint["year"]))) == len(
                    years
                ) and len(possible_days) < len(constraint["day"]):
                    possible_days = constraint["day"]
            days = days.intersection(set(possible_days))
        return list(days)

    def _get_constraints_for_month(self, month):
        constraints = []
        for constraint in self.constraints:
            if month in constraint["month"]:
                constraints.append(constraint)
        return constraints

    def _get_times_for_days_months_and_years(self, days, months, years):
        hours = [i for i in range(0, 24)]
        times = {datetime.time(h).strftime("%H:00") for h in hours}
        for day in days:
            constraints = self._get_constraints_for_day(day)
            possible_times = []
            for constraint in constraints:
                if (
                    len(set(years).intersection(set(constraint["year"]))) == len(years)
                    and len(set(months).intersection(set(constraint["month"])))
                    == len(months)
                    and len(possible_times) < len(constraint["time"])
                ):
                    possible_times = constraint["time"]
            times = times.intersection(set(possible_times))
        return list(times)

    def _get_constraints_for_day(self, day):
        constraints = []
        for constraint in self.constraints:
            if day in constraint["day"]:
                constraints.append(constraint)
        return constraints

    def _sort_record(self, record):
        record["year"] = sorted(record["year"], key=int)
        if "month" in record:
            record["month"] = sorted(record["month"], key=int)
        if "day" in record:
            record["day"] = sorted(record["day"], key=int)
        if "time" in record:
            record["time"] = sorted(record["time"], key=_hour_from_time)
        return record

    def _split_by_year_with_dates(self, start_year, end_year, slice_duration):
        slices = []
        min_max_dates = self._get_min_max_dates()
        start_year = max(start_year, min_max_dates["min_date"].year)
        end_year = min(end_year, min_max_dates["max_date"].year)
        for year in range(start_year, end_year + 1, slice_duration):
            start_date = datetime.datetime(year, 1, 1)
            end_date = datetime.datetime(year + slice_duration - 1, 12, 31)
            if end_date.year > end_year:
                end_date = datetime.datetime(end_year, 12, 31)
            slices.append({"start_date": start_date, "end_date": end_date})
        return slices

    def _split_by_month_with_dates(
        self, start_year, end_year, start_month, end_month, slice_duration
    ):
        slices = []
        min_max_dates = self._get_min_max_dates()
        start_date = datetime.datetime(start_year, start_month, 1)
        start_date = max(start_date, min_max_dates["min_date"])
        start_year = start_date.year
        start_month = start_date.month
        if end_month == 12:
            final_date = datetime.datetime(end_year, end_month, 31)
        else:
            final_date = datetime.datetime(
                end_year, end_month + 1, 1
            ) - datetime.timedelta(days=1)
        final_date = min(final_date, min_max_dates["max_date"])
        end_year = final_date.year
        end_month = final_date.month
        end_date = start_date
        current_year = start_year
        while end_date < final_date:
            new_month = start_date.month + slice_duration
            if new_month <= 12:
                end_date = datetime.datetime(
                    current_year, new_month, 1
                ) - datetime.timedelta(days=1)
            else:
                new_month = new_month - 12
                current_year += 1
                end_date = datetime.datetime(
                    current_year, new_month, 1
                ) - datetime.timedelta(days=1)
            if end_date > final_date:
                end_date = final_date
            slices.append({"start_date": start_date, "end_date": end_date})
            start_date = end_date + datetime.timedelta(days=1)
        return slices

    def _get_min_max_dates(self):
        if "startTimeFromAscendingNode" in self.metadata and isinstance(
            self.metadata["startTimeFromAscendingNode"], list
        ):
            date_var = self.metadata["startTimeFromAscendingNode"][0].split("=")[0]
        elif "completionTimeFromAscendingNode" in self.metadata and isinstance(
            self.metadata["completionTimeFromAscendingNode"], list
        ):
            date_var = self.metadata["completionTimeFromAscendingNode"][0].split("=")[0]
        else:
            raise MisconfiguredError(
                "No date variable configured; please check the configuration"
            )

        min_date = datetime.datetime(2100, 12, 31)
        max_date = datetime.datetime(1900, 1, 1)
        for constraint in self.constraints:
            date_value = constraint[date_var]
            if isinstance(date_value, list):
                for date_str in date_value:
                    dates = re.findall("[0-9]{4}-[0,1][0-9]-[0-3][0-9]", date_str)
                    start_date = datetime.datetime.strptime(dates[0], "%Y-%m-%d")
                    min_date = min(start_date, min_date)
                    end_date = datetime.datetime.strptime(dates[1], "%Y-%m-%d")
                    max_date = max(end_date, max_date)
            else:
                date_str = date_value
                dates = re.findall("[0-9]{4}-[0,1][0-9]-[0-3][0-9]", date_str)
                start_date = datetime.datetime.strptime(dates[0], "%Y-%m-%d")
                min_date = min(start_date, min_date)
                end_date = datetime.datetime.strptime(dates[1], "%Y-%m-%d")
                max_date = max(end_date, max_date)

        return {"min_date": min_date, "max_date": max_date}
