#%matplotlib inline  
import os
import datetime
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.style.use('ggplot')

# Initial Data Setup
data_path = 'H:/data'
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


# Get enter/out signal
idx = np.where(longrun.signal[1:] != longrun.signal[:-1])[0] + 1

# Get buy/sell cells
if longrun.signal[0] == 0:
    buy_idx = idx[::2]
    sell_idx = idx[1::2]
else:
    buy_idx = idx[1::2]
    sell_idx = idx[::2]

longrun['bs'] = ''
longrun.bs[buy_idx] = 'buy'
longrun.bs[sell_idx] = 'sell'

# Start to build the strategy portfolio
capital = 100
n_shares = 0
capital_prev = capital
n_prev = n_shares

port = []

for i in np.arange(1, len(longrun.index)):
    price = longrun.xiv[i]
    signal = longrun.signal[i]
    bs = longrun.bs[i]
    # update today's share and capital from yesterday
    n = n_prev
    capital = capital_prev
    # if today is hold
    if signal == 1 and bs == 'buy':
        n = capital/price
    elif signal == 1 and bs == '':
        capital = n * price
    elif signal == 0 and bs == 'sell':
        capital = n * price
        n = 0

    n_prev = n
    capital_prev = capital
    port.append(capital)

port = [0] + port
port_df = longrun[['xiv']]
port_df['strat'] = port

n_xiv = 100/longrun.xiv[0]
port_xiv = n_xiv * longrun.xiv

port_df['hold_xiv'] = port_xiv

