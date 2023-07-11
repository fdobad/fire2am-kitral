#!/usr/bin/env python3
from pandas import DataFrame
from scipy import stats

TAG = "firea2m"
STATS_DESCRIBE_NAMES = list(stats.describe([0, 0])._fields)
STATS_BASE_NAMES = ["Name", "Units"] + STATS_DESCRIBE_NAMES
STATS_BASE_DF = DataFrame(STATS_BASE_NAMES, index=STATS_BASE_NAMES, columns=["Attributes"])
GRID_NAMES = ["nsim", "ngrid", "burned"] + STATS_DESCRIBE_NAMES
GRID_EMPTY_DF = DataFrame(columns=GRID_NAMES)

