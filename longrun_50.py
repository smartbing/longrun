#%matplotlib inline
import os
import datetime
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import util
from pandas_datareader import data, wb  # Testing of datareader package
matplotlib.style.use('ggplot')

# Initial Data Setup
data_path = 'C:/Users/Bing/Projects/longrun/data'
vxv_file = os.path.join(data_path, 'vxv.csv')
vxmt_file = os.path.join(data_path, 'vxmt.csv')
xiv_file = os.path.join(data_path, 'xiv.csv')
vxx_file = os.path.join(data_path, 'vxx.csv')
dateparse = lambda x: pd.datetime.strptime(x, '%d/%m/%Y')
vxv_df = pd.read_csv(vxv_file, index_col=0, parse_dates=[0], date_parser=dateparse)
vxmt_df = pd.read_csv(vxmt_file, index_col=0, parse_dates=[0], date_parser=dateparse)
vxx_df = pd.read_csv(vxx_file, index_col=0, parse_dates=[0], date_parser=dateparse)
xiv_df = pd.read_csv(xiv_file, index_col=0, parse_dates=[0], date_parser=dateparse)
xiv = xiv_df[['Adj Close']]
vxx = vxx_df[['Adj Close']]

data = pd.merge(vxv_df, vxmt_df, how='left', left_index=True, right_index=True)
data = data.fillna(method='ffill')
data = data.fillna(value=0)

# Derived signals below
ratio = data['VXV'].divide(data['VXMT'])
ratio.sort_index(axis='index', inplace=True)
ratio.name = 'ratio'
ma_60 = pd.Series.rolling(ratio, window=60).mean()
ma_150 = pd.Series.rolling(ratio, window=150).mean()
ma_60.name = 'ma_60'
ma_150.name = 'ma_150'

strat_df = pd.concat([ratio, ma_60, ma_150],  axis=1)
etf = pd.merge(xiv, vxx, how='left', left_index=True, right_index=True)
etf.columns = ['xiv', 'vxx']

# First strat df with all etf data and ratio
longrun = pd.merge(etf, strat_df , how='left', left_index=True, right_index=True)
# 100% Long signal
longrun['signal'] = np.where((longrun['ma_60']<1) & (longrun['ma_150']<1) & (longrun['ratio'] < longrun['ma_60']) & (longrun['ratio'] < longrun['ma_150']), 1, 0)

# 50% long signal
longrun['signal_50'] = np.where((longrun['ma_60']<1) & (longrun['ma_150']<1) & (longrun['ratio'] > longrun['ma_60']) & (longrun['ratio'] < longrun['ma_150']), 1, 0)


# Get enter/out signal
idx = np.where(longrun.signal[1:].values != longrun.signal[:-1].values)[0] + 1
idx_50 = np.where(longrun.signal_50[1:].values != longrun.signal_50[:-1].values)[0] + 1

# Get buy/sell cells for 100% Long
if longrun.signal[0] == 0:
    buy_idx = idx[::2]
    sell_idx = idx[1::2]
else:
    buy_idx = idx[1::2]
    sell_idx = idx[::2]

longrun['bs'] = ''
longrun.bs[buy_idx] = 'buy'
longrun.bs[sell_idx] = 'sell'

# Get buy/sell cells for 50% Long
if longrun.signal_50[0] == 0:
    buy_50_idx = idx_50[::2]
    sell_50_idx = idx_50[1::2]
else:
    buy_50_idx = idx_50[1::2]
    sell_50_idx = idx_50[::2]

longrun['bs_50'] = ''
longrun.bs_50[buy_50_idx] = 'buy'
longrun.bs_50[sell_50_idx] = 'sell'

# Start to build the strategy portfolio
capital = 0
n_shares = 0
cash = 100
capital_prev = capital
n_prev = n_shares
cash_prev = cash
port_value = capital + cash
port = []

# Record strat info
n_stock = [n_shares]
cap_list = [capital]
cash_list = [cash]

# Now shift the underlying price (XIV) backward 1 day to avoid look ahead bias
longrun.xiv = longrun.xiv.shift(-1)
longrun.xiv.fillna(method='ffill', inplace=True)


# TODO: Update following trading logic to include scenarios for bs_50 signals
# Compare with jupyter notebook table for logic
for i in np.arange(1, len(longrun.index)):
    price = longrun.xiv[i]
    signal = longrun.signal[i]
    signal_50 = longrun.signal_50[i]
    bs = longrun.bs[i]
    bs_50 = longrun.bs_50[i]
    # update today's share and capital from yesterday
    n = n_prev
    capital = capital_prev
    cash = cash_prev

    # enter 50% vix from all cash
    if signal_50 == 1 and bs_50 == 'buy' and bs == '':
        n = cash * 0.5 / price
        capital = n * price
        cash = cash * 0.5

    # Enter 50% into 100% (invest rest of cash into xiv)
    if signal == 1 and bs == 'buy' and signal_50 == 0 and bs_50 == 'sell':
        n = n + cash / price
        capital = n * price
        cash = 0

    # Enter 100% into xiv from all cash
    if signal == 1 and bs == 'buy' and bs_50 == '':
        n = cash / price
        capital = n * price
        cash = 0

    # Unload 50% xiv from 100%
    if signal == 0 and bs == 'sell' and bs_50 == 'buy':
        n = n * 0.5
        capital = n * price
        cash = capital

    # Sell all from 50% position or 100%
    if signal_50 == 0 and bs_50 == 'sell' and bs == '':
        cash = capital + cash
        n = 0
        capital = 0

    # Sell all from 100%
    if signal == 0 and bs == 'sell' and bs_50 == '':
        cash = capital
        n = 0
        capital = 0

    # Hold long position
    if (signal == 1 and bs == '') or (signal_50 == 1 and bs_50 == ''):
        capital = n * price

    n_prev = n
    capital_prev = capital
    cash_prev = cash
    port_value = cash + capital
    port.append(port_value)
    n_stock.append(n)
    cap_list.append(capital)
    cash_list.append(cash)


port = [0] + port
port_df = longrun[['xiv']]
port_df['strat'] = port
port_df['n'] = n_stock
port_df['capital'] = cap_list
port_df['cash'] = cash_list

n_xiv = 100/longrun.xiv[0]
port_xiv = n_xiv * longrun.xiv

port_df['hold_xiv'] = port_xiv

max_drawdown = util.calc_port_drawdown(port_df.strat, 252)

# Below line to keep for debugging above lines
port_df.head()