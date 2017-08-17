# Utility functions
import pandas as pd
import numpy as np


def calc_port_drawdown(data, window):
    roll_max = pd.rolling_max(data, window, min_periods=1)
    daily_drawdown = data/roll_max - 1.0

    max_daily_drawdown = pd.rolling_min(daily_drawdown, window, min_periods=1)
    max_drawdown_idx = max_daily_drawdown.idxmin()
    return max_drawdown_idx, max_daily_drawdown.min()

def get_port_summary(data):
    daily_ret = data.pct_change(1)[1:]
    daily_std = np.nanstd(daily_ret)
    annual_std = daily_std * np.sqrt(252)
    total_return = data[-1]/data[0] - 1
    sharpe_ratio = np.sqrt(252) * np.average(daily_ret) / daily_std

    ndays = data.index[-1] - data.index[0]
    nyears = ndays/252
    year_return = np.power(1 + total_return, 1/nyears) - 1
    return {'total_return': total_return, 'yearly_return': year_return, 'yearly_std': annual_std, 'sharpe_ratio': sharpe_ratio}




