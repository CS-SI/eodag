import copy
import datetime
import json
import re

import requests

from eodag.utils.exceptions import MisconfiguredError


def _hour_from_time(time):
    return int(time[:2])


def _parse_dates_from_string(date_str):
    dates = re.findall("[0-9]{4}-[0,1][0-9]-[0-3][0-9]", date_str)
    start_date = datetime.datetime.strptime(dates[0], "%Y-%m-%d")
    end_date = datetime.datetime.strptime(dates[1], "%Y-%m-%d")
    return {"start_date": start_date, "end_date": end_date}


def _check_value_in_constraint(value, constraint_value):
    if not isinstance(value, list):
        return value in constraint_value or str(value) in constraint_value
    else:
        for record in value:
            if record not in constraint_value and str(record) not in constraint_value:
                return False
        return True


def _check_constraint_params(params, constraint, variable_name, variables):
    available_variables = []
    for key, value in params.items():
        if key not in constraint or _check_value_in_constraint(value, constraint[key]):
            if variables:
                variables_str = [str(v) for v in variables]
                v = set(variables_str).intersection(set(constraint[variable_name]))
                available_variables = list(v)
            else:
                available_variables = constraint[variable_name]
        else:
            available_variables = []
    return available_variables


class RequestSplitter:
    """
    provides methods to split a request into several requests based on the given config and constraints
    """

    def __init__(self, config):
        self.config = config.__dict__
        if (
            "constraints_file_path" in self.config
            and self.config["constraints_file_path"]
        ):
            with open(self.config["constraints_file_path"]) as f:
                self.constraints_data = json.load(f)
        elif (
            "constraints_file_url" in self.config
            and self.config["constraints_file_url"]
        ):
            if "auth" in self.config:
                headers = getattr(self.config["auth"], "headers", "")
                res = requests.get(self.config["constraints_file_url"], headers=headers)
            else:
                res = requests.get(self.config["constraints_file_url"])
            self.constraints_data = res.json()
        else:
            self.constraints_data = {}
        if "constraints_param" in self.config and self.config["constraints_param"]:
            self.constraints = self.constraints_data[self.config["constraints_param"]]
        else:
            self.constraints = self.constraints_data

        self.metadata = self.config["metadata_mapping"]
        if "multi_select_values" in self.config:
            self.multi_select_values = self.config["multi_select_values"]
        else:
            self.multi_select_values = []
        if "products_split_timedelta" in self.config:
            self.split_time_delta = self.config["products_split_timedelta"]
        else:
            self.split_time_delta = {}
        self._check_config_valid()

    def _check_config_valid(self):
        if not self.split_time_delta:  # config vide
            return True
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
            if (end_year - start_year) < slice_duration:
                return self._format_result(start_date, end_date)
            return self._split_by_year(start_year, end_year, slice_duration)
        elif split_param == "month":
            start_month = int(start_date[5:7])
            end_month = int(end_date[5:7])
            if start_year == end_year and (end_month - start_month) < slice_duration:
                return self._format_result(start_date, end_date)
            return self._split_by_month(
                start_year, end_year, start_month, end_month, slice_duration
            )

    def _format_result(self, start_date, end_date):
        if "year" not in self.metadata:
            return [{"start_date": start_date, "end_date": end_date}]
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])
        years = [str(y) for y in range(start_year, end_year + 1)]
        start_month = int(start_date[5:7])
        end_month = int(end_date[5:7])
        start_day = int(start_date[8:10])
        end_day = int(end_date[8:10])
        if len(years) == 1:
            selected_months = {
                "{:0>2d}".format(m) for m in range(start_month, end_month + 1)
            }
            months = self._get_months_for_years(years, selected_months)
        else:
            months = self._get_months_for_years(years)
        if len(months) == 1:
            selected_days = {"{:0>2d}".format(d) for d in range(start_day, end_day + 1)}
            days = self._get_days_for_months_and_years(months, years, selected_days)
        else:
            days = self._get_days_for_months_and_years(months, years)
        times = self._get_times_for_days_months_and_years(days, months, years)
        return [{"year": years, "month": months, "day": days, "time": times}]

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
                    months_slice.append("{:0>2d}".format(m))
                    i += 1
                else:
                    months_years.append({"year": [str(y)], "month": months_slice})
                    months_slice = ["{:0>2d}".format(m)]
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
                if "day" in self.metadata:
                    times = self._get_times_for_days_months_and_years(
                        days, row["month"], row["year"]
                    )
                else:
                    times = self._get_times_for_months_and_years(
                        row["month"], row["year"]
                    )
                record["time"] = times
            slices.append(self._sort_record(record))
        return slices

    def _get_months_for_years(self, years, months=None):
        if not months:
            months = {"{:0>2d}".format(i) for i in range(1, 13)}
        if not self.constraints:
            return months
        current_months = ()
        for year in years:
            constraints = self._get_constraints_for_year(year)
            for constraint in constraints:
                possible_months = months.intersection(set(constraint["month"]))
                if len(possible_months) > len(current_months):
                    current_months = possible_months
        return list(current_months)

    def _get_constraints_for_year(self, year):
        if not self.constraints:
            return [str(m) for m in range(1, 13)]
        constraints = []
        for constraint in self.constraints:
            if year in constraint["year"]:
                constraints.append(constraint)
        return constraints

    def _get_days_for_months_and_years(self, months, years, days=None):
        if not days:
            days = {"{:0>2d}".format(i) for i in range(1, 32)}
        if not self.constraints:
            return days
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
        if not self.constraints:
            return times
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

    def _get_times_for_months_and_years(self, months, years):
        hours = [i for i in range(0, 24)]
        times = {datetime.time(h).strftime("%H:00") for h in hours}
        if not self.constraints:
            return times
        for month in months:
            constraints = self._get_constraints_for_month(month)
            possible_times = []
            for constraint in constraints:
                if len(set(years).intersection(set(constraint["year"]))) == len(
                    years
                ) and len(possible_times) < len(constraint["time"]):
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
            start_date = max(datetime.datetime(year, 1, 1), min_max_dates["min_date"])
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
        if end_month == 12:
            final_date = datetime.datetime(end_year, end_month, 31)
        else:
            final_date = datetime.datetime(
                end_year, end_month + 1, 1
            ) - datetime.timedelta(days=1)
        final_date = min(final_date, min_max_dates["max_date"])
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

    def _get_date_var(self):
        if "startTimeFromAscendingNode" in self.metadata and isinstance(
            self.metadata["startTimeFromAscendingNode"], list
        ):
            return self.metadata["startTimeFromAscendingNode"][0].split("=")[0]
        elif "completionTimeFromAscendingNode" in self.metadata and isinstance(
            self.metadata["completionTimeFromAscendingNode"], list
        ):
            return self.metadata["completionTimeFromAscendingNode"][0].split("=")[0]
        else:
            raise MisconfiguredError(
                "No date variable configured; please check the configuration"
            )

    def _get_min_max_dates(self):
        date_var = self._get_date_var()
        min_date = datetime.datetime(2100, 12, 31)
        max_date = datetime.datetime(1900, 1, 1)
        if not self.constraints:
            return {"min_date": max_date, "max_date": min_date}
        for constraint in self.constraints:
            date_value = constraint[date_var]
            if isinstance(date_value, list):
                for date_str in date_value:
                    dates = _parse_dates_from_string(date_str)
                    min_date = min(dates["start_date"], min_date)
                    max_date = max(dates["end_date"], max_date)
            else:
                dates = _parse_dates_from_string(date_value)
                min_date = min(dates["start_date"], min_date)
                max_date = max(dates["end_date"], max_date)

        return {"min_date": min_date, "max_date": max_date}

    def get_variables_for_product(self, id_extract, params, variables=None):
        """
        returns the variables that are available for a timespan based on the given constraints
        :param id_extract: the part of the id that contains the dates
        :type id_extract: str
        :param params: keys and values of additional parameters where constraints could exist
        :type params: dict
        :param variables: (optional) selected variables, if not given all available variables will be returned
        :type variables: list
        :returns: list of available variables
        :rtype: list
        """
        if "year" not in self.metadata:
            start_date = datetime.datetime.strptime(id_extract[:8], "%Y%m%d")
            end_date = datetime.datetime.strptime(id_extract[9:], "%Y%m%d")
            return self._get_variables_for_timespan_and_params(
                start_date, end_date, params, variables
            )
        else:
            start_year = int(id_extract[:4])
            end_year = int(id_extract.split("_")[1][:4])
            years = [str(y) for y in range(start_year, end_year + 1)]
            if self.split_time_delta["param"] == "month":
                start_month = int(id_extract[4:6])
                end_month = int(id_extract.split("_")[1][4:6])
                months = [str(m) for m in range(start_month, end_month + 1)]
                return self._get_variables_for_months_and_params(
                    years, months, params, variables
                )
            return self._get_variables_for_years_and_params(years, params, variables)

    def get_variables_for_search_params(self, search_params, variables=None):
        """
        returns the variables that are available for the given search parameters based on the given constraints
        :param search_params: keys and values of time parameters and additional parameters where constraints could exist
        :type search_params: dict
        :param variables: (optional) selected variables, if not given all available variables will be returned
        :type variables: list
        :returns: list of available variables
        :rtype: list
        """
        params = copy.deepcopy(search_params)
        if "year" in params:
            years = params.pop("year")
            if self.split_time_delta["param"] == "month":
                months = params.pop("month")
                return self._get_variables_for_months_and_params(
                    years, months, params, variables
                )
            else:
                return self._get_variables_for_years_and_params(
                    years, params, variables
                )
        else:
            start_date = datetime.datetime.strptime(
                params.pop("startTimeFromAscendingNode"), "%Y-%m-%dT%H:%M:%SZ"
            )
            end_date = datetime.datetime.strptime(
                params.pop("completionTimeFromAscendingNode"), "%Y-%m-%dT%H:%M:%SZ"
            )
            return self._get_variables_for_timespan_and_params(
                start_date, end_date, params, variables
            )

    def _get_variables_for_years_and_params(self, years, params, variables=None):
        if not self.constraints:
            return variables
        variable_name = self.config["assets_split_parameter"]
        available_variables = []
        for constraint in self.constraints:
            years_intsersect = set(years).intersection(set(constraint["year"]))
            if len(years_intsersect) == len(years):
                available_variables += _check_constraint_params(
                    params, constraint, variable_name, variables
                )
        return list(set(available_variables))

    def _get_variables_for_months_and_params(
        self, years, months, params, variables=None
    ):
        if not self.constraints:
            return variables
        variable_name = self.config["assets_split_parameter"]
        available_variables = []
        for constraint in self.constraints:
            years_intsersect = set(years).intersection(set(constraint["year"]))
            months_intersect = set(months).intersection(set(constraint["month"]))
            if len(years_intsersect) == len(years) and len(months_intersect) == len(
                months
            ):
                available_variables += _check_constraint_params(
                    params, constraint, variable_name, variables
                )
        return list(set(available_variables))

    def _get_variables_for_timespan_and_params(
        self, start_date, end_date, params, variables=None
    ):
        """
        returns the variables that are available for a timespan based on the given constraints
        :param start_date: start date of the timespan
        :type start_date: datetime
        :param end_date: end date of the timespan
        :type end_date: datetime
        :param params: keys and values of additional parameters where constraints could exist
        :type params: dict
        :param variables: (optional) selected variables, if not given all available variables will be returned
        :type variables: list
        :returns: list of available variables
        :rtype: list
        """
        available_variables = []
        if not self.constraints and variables:
            return variables
        variable_name = self.config["assets_split_parameter"]
        date_var = self._get_date_var()
        for constraint in self.constraints:
            for dates in constraint[date_var]:
                dates_constraint = _parse_dates_from_string(dates)
                if (
                    dates_constraint["start_date"] <= start_date
                    and dates_constraint["end_date"] >= end_date
                ):
                    available_variables += _check_constraint_params(
                        params, constraint, variable_name, variables
                    )
        return list(set(available_variables))
