#%matplotlib inline
import os
import datetime
#import json
import numpy as np
import pandas as pd
#import matplotlib.pyplot as plt
#import matplotlib
import util
#from pandas_datareader import data, wb  # Testing of datareader package
#matplotlib.style.use('ggplot')


# Initial Data Setup
start_date = '2015-05-01'
start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')

data_path = 'H:/data'
vxv_file = os.path.join(data_path, 'vxv.csv')
vxmt_file = os.path.join(data_path, 'vxmt.csv')
xiv_file = os.path.join(data_path, 'xiv.csv')
vxx_file = os.path.join(data_path, 'vxx.csv')
svxy_file = os.path.join(data_path, 'svxy.csv')
hvi_file = os.path.join(data_path, 'svxy.csv')
dateparse = lambda x: pd.datetime.strptime(x, '%d/%m/%Y')
vxv_df = pd.read_csv(vxv_file, index_col=0, parse_dates=[0], date_parser=dateparse)
vxmt_df = pd.read_csv(vxmt_file, index_col=0, parse_dates=[0], date_parser=dateparse)
vxx_df = pd.read_csv(vxx_file, index_col=0, parse_dates=[0], date_parser=dateparse)
xiv_df = pd.read_csv(xiv_file, index_col=0, parse_dates=[0], date_parser=dateparse)
svxy_df = pd.read_csv(svxy_file, index_col=0, parse_dates=[0], date_parser=dateparse)
hvi_df = pd.read_csv(hvi_file, index_col=0, parse_dates=[0], date_parser=dateparse)
xiv = xiv_df[['Adj Close']]
vxx = vxx_df[['Adj Close']]
svxy = svxy_df[['Adj Close']]
hvi = hvi_df[['Adj Close']]

# calc ratios and signals
data = pd.merge(vxv_df, vxmt_df, how='left', left_index=True, right_index=True)
data = data.fillna(method='ffill')
data = data.fillna(value=0)

# Derived vix futures ratio and moving averages below
ratio = data['VXV'].divide(data['VXMT'])
ratio.sort_index(axis='index', inplace=True)
ratio.name = 'ratio'
ma_60 = pd.Series.rolling(ratio, window=60).mean()
ma_150 = pd.Series.rolling(ratio, window=150).mean()
ma_60.name = 'ma_60'
ma_150.name = 'ma_150'

strat_df = pd.concat([ratio, ma_60, ma_150],  axis=1)
idx = strat_df.isnull().any(axis=1)
strat_df = strat_df[~idx]
strat_df = strat_df[strat_df.index >= start_date]

etf = pd.merge(xiv, vxx, how='left', left_index=True, right_index=True)
etf = pd.merge(etf, svxy, how='left', left_index=True, right_index=True)
etf = pd.merge(etf, hvi, how='left', left_index=True, right_index=True)
etf.columns = ['xiv', 'vxx', 'svxy', 'hvi']

# First strat df with all etf data and ratio
#longrun = pd.merge(etf, strat_df , how='left', left_index=True, right_index=True)

# Strategy signals can be calculated independent of underlying data first, merge signals with price data later
# 100% Long signal
strat_df['signal'] = np.where((strat_df['ma_60']<1) & (strat_df['ma_150']<1) & (strat_df['ratio'] < strat_df['ma_60']) & (strat_df['ratio'] < strat_df['ma_150']), 1, 0)

# 50% long signal
strat_df['signal_50'] = np.where((strat_df['ma_60']<1) & (strat_df['ma_150']<1) & (strat_df['ratio'] > strat_df['ma_60']) & (strat_df['ratio'] < strat_df['ma_150']), 1, 0)


# Get enter/out signal
idx = np.where(strat_df.signal[1:].values != strat_df.signal[:-1].values)[0] + 1
idx_50 = np.where(strat_df.signal_50[1:].values != strat_df.signal_50[:-1].values)[0] + 1

# Get buy/sell cells for 100% Long
if strat_df.signal[0] == 0:
    buy_idx = idx[::2]
    sell_idx = idx[1::2]
else:
    buy_idx = np.insert(idx[1::2], 0, 0)
    sell_idx = idx[::2]

strat_df['bs'] = ''
strat_df.bs[buy_idx] = 'buy'
strat_df.bs[sell_idx] = 'sell'

# Get buy/sell cells for 50% Long
if strat_df.signal_50[0] == 0:
    buy_50_idx = idx_50[::2]
    sell_50_idx = idx_50[1::2]
else:
    buy_50_idx = np.insert(idx_50[1::2], 0, 0)
    sell_50_idx = idx_50[::2]

strat_df['bs_50'] = ''
strat_df.bs_50[buy_50_idx] = 'buy'
strat_df.bs_50[sell_50_idx] = 'sell'

# Output strat_df to csv
strat_df.to_csv(os.path.join(data_path, 'strat_signal.csv'))

# Start to build the longrun strat portfolio with underlying stock/etf
# First merge stock with strat_df
all_data = pd.merge(etf, strat_df , how='left', left_index=True, right_index=True)
longrun = all_data[all_data.index >= start_date]
etf_name = 'hvi'
#etf_name = 'svxy'

# Predefined portfolio variables
capital = 0
n_shares = 0
cash = 100
capital_prev = capital
n_prev = n_shares
cash_prev = cash
port_value = capital + cash
port = []

# Record rebalance variables info
n_stock = []
cap_list = []
cash_list = []

# Now shift the underlying price (XIV) backward 1 day to avoid look ahead bias
longrun[etf_name] = longrun[etf_name].shift(-1)
longrun[etf_name].fillna(method='ffill', inplace=True)

# Below are the trade/rebalance logics for the portfolio strating from trade day
for i in np.arange(0, len(longrun.index)):
    price = longrun[etf_name].iloc[i]
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

#port = [0] + port
port_df = longrun[[etf_name]]
port_df['strat'] = port
port_df['n'] = n_stock
port_df['capital'] = cap_list
port_df['cash'] = cash_list

# Buy and hold strategy for underlying stock/etf
n_etf = 100/longrun[etf_name].iloc[0]
port_etf = n_etf * longrun[etf_name]

port_df['hold_etf'] = port_etf

max_drawdown = util.calc_port_drawdown(port_df.strat, 252)
port_summary = util.get_port_summary(port_df.strat)
# Below line to keep for debugging above lines
port_df.head()