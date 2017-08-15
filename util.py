# Utility functions
import pandas as pd
import numpy as np


def calc_port_drawdown(data, window):
    roll_max = pd.rolling_max(data, window, min_periods=1)
    daily_drawdown = data/roll_max - 1.0

    max_daily_drawdown = pd.rolling_min(daily_drawdown, window, min_periods=1)

    return max_daily_drawdown.min()

