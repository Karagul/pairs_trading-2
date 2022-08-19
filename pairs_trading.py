import os
from datetime import datetime
from datetime import timedelta
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf
from numpy import log
from statsmodels.compat import scipy
from tabulate import tabulate
from scipy import stats
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller

s_and_p_file = 's_and_p_sector_components/sp_stocks.csv'
s_and_p_data = 's_and_p_data'
start_date_str = '2007-01-03'
start_date: datetime = datetime.fromisoformat(start_date_str)

trading_days = 252


def convert_date(some_date):
    if type(some_date) == str:
        some_date = datetime.fromisoformat(some_date)
    elif type(some_date) == np.datetime64:
        ts = (some_date - np.datetime64('1970-01-01T00:00')) / np.timedelta64(1, 's')
        some_date = datetime.utcfromtimestamp(ts)
    return some_date


def read_stock_data(path: str) -> pd.DataFrame:
    s_and_p_stocks = pd.DataFrame()
    if os.access(path, os.R_OK):
        # s_and_p_socks columns are Symbol, Name and Sector
        s_and_p_stocks = pd.read_csv(s_and_p_file, index_col=0)
        new_names = [sym.replace('.', '-') for sym in s_and_p_stocks['Symbol']]
        s_and_p_stocks['Symbol'] = new_names
    else:
        print(f'Could not read file {s_and_p_file}')
    return s_and_p_stocks


def extract_sectors(stocks_df: pd.DataFrame) -> dict:
    """
    Columns in the DataFrame are Symbol,Name,Sector
    :param stocks_df:
    :return:
    """
    sector: str = ''
    sector_l: list = list()
    stock_sectors = dict()
    for t, stock_info in stocks_df.iterrows():
        if sector != stock_info['Sector']:
            if len(sector_l) > 0:
                stock_sectors[sector] = sector_l
                sector_l = list()
            sector = stock_info['Sector']
        sector_l.append(stock_info['Symbol'])
    stock_sectors[sector] = sector_l
    return stock_sectors


def calc_pair_counts(sector_info: dict) -> pd.DataFrame:
    column_label = ['num stocks', 'num pairs']
    sectors = list(sector_info.keys())
    counts_l: list = list()
    n_l: list = list()
    for sector in sectors:
        n = len(sector_info[sector])
        n_l.append(n)
        count = ((n ** 2.0) - n) / 2.0
        counts_l.append(count)
    num_stocks = sum(n_l)
    info_df = pd.DataFrame(n_l)
    info_df = pd.concat([info_df, pd.DataFrame(counts_l)], axis=1)
    info_df.columns = column_label
    sum_pairs = sum(counts_l)
    num_stocks_df = pd.DataFrame([num_stocks])
    sum_df = pd.DataFrame([sum_pairs])
    row_df = pd.concat([num_stocks_df, sum_df], axis=1)
    row_df.columns = column_label
    info_df = pd.concat([info_df, row_df], axis=0)
    sectors.append('Sum')
    info_df.index = sectors
    return info_df


class MarketData:
    """
    This class supports retrieving and storing stock market close data from Yahoo.
    """

    def __init__(self, start_date: datetime, path: str):
        self.start_date = start_date
        self.path = path
        self.end_date: datetime = datetime.today() - timedelta(days=1)

    def get_market_data(self,
                        symbol: str,
                        start_date: datetime,
                        end_date: datetime) -> pd.DataFrame:
        data_col = 'Close'
        if type(symbol) == str:
            t = list()
            t.append(symbol)
            symbols = t
        panel_data = yf.download(tickers=symbol, start=start_date, end=end_date, progress=False)
        if panel_data.shape[0] > 0:
            close_data: pd.DataFrame = panel_data[data_col]
        else:
            close_data = pd.DataFrame()
        close_data = close_data.round(2)
        close_data_df = pd.DataFrame(close_data)
        return close_data_df

    def symbol_file_path(self, symbol: str) -> str:
        path: str = self.path + os.path.sep + symbol.upper() + '.csv'
        return path

    def read_data(self, symbol: str) -> pd.DataFrame:
        file_path = self.symbol_file_path(symbol)
        if os.access(file_path, os.R_OK):
            symbol_df = pd.read_csv(file_path, index_col='Date')
            last_row = symbol_df.tail(1)
            last_date = convert_date(last_row.index[0])
            if last_date.date() < self.end_date.date():
                sym_start_date = last_date + timedelta(days=1)
                new_data_df = self.get_market_data(symbol, sym_start_date, datetime.today())
                if new_data_df.shape[0] > 0:
                    symbol_df = pd.concat([symbol_df, new_data_df], axis=0)
                    ix = symbol_df.index
                    ix = pd.to_datetime(ix)
                    symbol_df.index = ix
                    symbol_df.to_csv(file_path)
        else:
            symbol_df = self.get_market_data(symbol, self.start_date, self.end_date)
            if symbol_df.shape[0] > 0:
                if not os.access(self.path, os.R_OK):
                    os.mkdir(self.path)
                symbol_df.to_csv(file_path)
                if type(symbol_df) != pd.DataFrame:
                    symbol_df = pd.DataFrame(symbol_df)
        if symbol_df.shape[0] > 0:
            symbol_df.columns = [symbol]
        return symbol_df

    def get_close_data(self, stock_list: list) -> pd.DataFrame:
        close_df = pd.DataFrame()
        for stock in stock_list:
            stock_df = self.read_data(stock)
            if stock_df.shape[0] > 0:
                stock_start_date = convert_date(stock_df.head(1).index[0])
                # filter out stocks with a start date that is later than self.start_date
                if stock_start_date.date() == self.start_date.date():
                    close_df = pd.concat([close_df, stock_df], axis=1)
        return close_df


stock_info_df = read_stock_data(s_and_p_file)
market_data = MarketData(start_date, s_and_p_data)
stock_l: list = list(set(stock_info_df['Symbol']))
stock_l.sort()
# t = market_data.parallel_close_data(stock_l)
close_prices_df = market_data.get_close_data(stock_l)
final_stock_list = list(close_prices_df.columns)
mask = stock_info_df['Symbol'].isin(final_stock_list)
final_stock_info_df = stock_info_df[mask]

sectors = extract_sectors(final_stock_info_df)
pairs_info_df = calc_pair_counts(sectors)

print(tabulate(pairs_info_df, headers=[*pairs_info_df.columns], tablefmt='fancy_grid'))


def get_pairs(sector_info: dict) -> List[Tuple]:
    """
    Return all of the stock pairs, where the pairs are selected from the S&P 500 sector.

    :param sector_info: A dictionary containing the sector info. For example:
                        energies': ['APA', 'BKR', 'COP', ...]
                       Here 'energies' is the dictionary key for the list of S&P 500 stocks in that sector.
    :return: A list of Tuples, where each tuple contains the symbols for the stock pair and the sector.
            For example:
              [('AAPL', 'ACN', 'information-technology'),
               ('AAPL', 'ADBE', 'information-technology'),
               ('AAPL', 'ADI', 'information-technology'),
               ('AAPL', 'ADP', 'information-technology'),
               ('AAPL', 'ADSK', 'information-technology')]
    """
    pairs_list = list()
    sectors = list(sector_info.keys())
    for sector in sectors:
        stocks = sector_info[sector]
        num_stocks = len(stocks)
        for i in range(num_stocks):
            stock_a = stocks[i]
            for j in range(i + 1, num_stocks):
                stock_b = stocks[j]
                pairs_list.append((stock_a, stock_b, sector))
    return pairs_list


def calc_pairs_correlation(stock_close_df: pd.DataFrame, pair: Tuple, window: int) -> np.array:
    """
    Calculate the windowed correlations for a stock pair over the entire data set.
    :param stock_close_df: A data frame containing the stock close prices
    :param pair: the stock pair
    :param window: The data window
    :return: a numpy array of windowed correlations for the pair over the entire time period.
    """
    cor_v = np.zeros(0)
    stock_a = pair[0]
    stock_b = pair[1]
    a_close = stock_close_df[stock_a]
    b_close = stock_close_df[stock_b]
    a_log_close = log(a_close)
    b_log_close = log(b_close)

    assert len(a_log_close) == len(b_log_close)
    for i in range(0, len(a_log_close), window):
        sec_a = a_log_close[i:i + window]
        sec_b = b_log_close[i:i + window]
        c = np.corrcoef(sec_a, sec_b)
        cor_v = np.append(cor_v, c[0, 1])
    return cor_v


def calc_yearly_correlation(stock_close_df: pd.DataFrame, pairs_list: List[Tuple]) -> np.array:
    """
    Calculate the yearly pairs correlation over the entire time period
    :param stock_close_df: A data frame containing the stock close prices. The columns are the stock tickers.
    :param pairs_list: A list of the pairs formed from the S&P 500 sectors.
    :return: A numpy array with the correlcations.
    """
    all_cor_v = np.zeros(0)
    for pair in pairs_list:
        cor_v: np.array = calc_pairs_correlation(stock_close_df, pair, trading_days)
        all_cor_v = np.append(all_cor_v, cor_v)
    return all_cor_v


def display_histogram(data_v: np.array, x_label: str, y_label: str) -> None:
    num_bins = int(np.sqrt(data_v.shape[0])) * 4
    fix, ax = plt.subplots(figsize=(10, 8))
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.grid(True)
    ax.hist(data_v, bins=num_bins, facecolor='b')
    ax.axvline(x=np.mean(data_v), color='black')
    plt.show()


pairs_list = get_pairs(sectors)


# yearly_cor_a = calc_yearly_correlation(close_prices_df, pairs_list)


# display_histogram(yearly_cor_a, 'Correlation between pairs', 'Count')

class PairStats:

    def __init__(self, stock_a: str,
                 stock_b: str,
                 slope: float,
                 intercept: float,
                 residuals: pd.Series,
                 adf_stat: float,
                 p_value: float,
                 one_percent: float,
                 five_percent: float):
        self.stock_a = stock_a
        self.stock_b = stock_b
        self.slope = slope
        self.intercept = intercept
        self.residuals = residuals
        self.adf_stat = adf_stat
        self.p_value = p_value
        self.one_percent = one_percent
        self.five_percent = five_percent

    def __str__(self):
        s: str = f'({self.stock_a},{self.stock_b}) slope: {self.slope} intercept: {self.intercept} \nadf: {self.adf_stat} p-value: {self.p_value} 5%: {self.five_percent} 1%: {self.one_percent}'
        return s


class PairsSelection:
    decimals = 4

    def __init__(self,
                 close_prices: pd.DataFrame,
                 correlation_cutoff: float):
        self.correlation_cutoff = correlation_cutoff
        self.close_prices = close_prices

    def pairs_correlation(self,
                          start_ix: int,
                          end_ix: int,
                          pairs_list: List[Tuple]) -> List[Tuple]:

        """
        Find the pairs with a log(price) correlation greater than or equal to cutoff within a close price window
        from start_ix to end_ix
        :param stock_close_df: the stock close prices for the entire backtest period
        :param start_ix: the start index in stock_close_df
        :param end_ix: the end index in stock_close_df
        :param pairs_list: a list of pairs
        :param cutoff: the cutoff for pairs selection
        :return: A list of tuples consisting of tuple[stock_a, stock_b, sector, correlation]
        """
        selected_pairs_l = list()
        for pair in pairs_list:
            stock_a: str = pair[0]
            stock_b: str = pair[1]
            log_close_a = log(close_prices[stock_a][start_ix:end_ix + 1])
            log_close_b = log(close_prices[stock_b][start_ix:end_ix + 1])
            c = np.corrcoef(log_close_a, log_close_b)
            cor_v = round(c[0, 1], 2)
            if cor_v >= self.correlation_cutoff:
                sector = pair[2]
                selected_pairs_l.append((stock_a, stock_b, sector, cor_v))
        return selected_pairs_l

    def stationary_analysis(self, start_ix: int, end_ix: int, pair: Tuple) -> PairStats:
        stock_a: str = pair[0]
        stock_b: str = pair[1]
        log_close_a = log(close_prices[stock_a][start_ix:end_ix])
        log_close_b = log(close_prices[stock_b][start_ix:end_ix])
        log_close_b_const = sm.add_constant(log_close_b)
        result_ab = sm.OLS(log_close_a, log_close_b_const).fit()
        log_close_a_const = sm.add_constant(log_close_a)
        result_ba = sm.OLS(log_close_b, log_close_a_const).fit()
        slope_ab = result_ab.params[stock_b]
        slope_ba = result_ba.params[stock_a]
        result = result_ab
        slope = slope_ab
        if slope_ab < slope_ba:
            result = result_ba
            slope = slope_ba
        intercept = round(result.params['const'], self.decimals)
        slope = round(slope, self.decimals)
        residuals = result.resid
        # References
        # https://machinelearningmastery.com/time-series-data-stationary-python/
        # https://www.quantstart.com/articles/Basics-of-Statistical-Mean-Reversion-Testing-Part-II/
        # p-value <= 0.05 stationary mean reverting TS
        # ADF more negative means a stronger mean reverting process
        adf_result = adfuller(residuals)
        adf_stat = round(adf_result[0], self.decimals)
        p_value = round(adf_result[1], self.decimals)
        d = adf_result[4]
        one_percent = round(d['1%'], self.decimals)
        five_percent = round(d['5%'], self.decimals)
        pair_stats = PairStats(stock_a=stock_a,
                               stock_b=stock_b,
                               slope=slope,
                               intercept=intercept,
                               residuals=residuals,
                               adf_stat=adf_stat,
                               p_value=p_value,
                               one_percent=one_percent,
                               five_percent=five_percent)
        return pair_stats

    def find_pairs(self, start_ix: int, end_ix: int, pairs_list=pairs_list ) -> List[PairStats]:
        selected_pairs = self.pairs_correlation(close_prices=close_prices, start_ix=start_ix, end_ix=end_ix, pairs_list=pairs_list)
        pair_stat_l: List[PairStats] = list()
        for pair in selected_pairs:
            stats = self.stationary_analysis(close_prices=close_prices, start_ix=start_ix, end_ix=end_ix, pair=pair)
            pair_stat_l.append(stats)
        return pair_stat_l


correlation_cutoff = 0.75
pairs_selection = PairsSelection(close_prices=close_prices_df, correlation_cutoff=correlation_cutoff)
stats_l = pairs_selection.find_pairs(cstart_ix=0, end_ix=trading_days, pairs_list=pairs_list)

pass
