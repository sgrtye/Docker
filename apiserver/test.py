import pandas
import numpy
import yfinance as yf

tickers = yf.Tickers("AAPL GOOG MSFT")

info = tickers.tickers["AAPL"].history(period="5d", interval="60m")

latest_time: pandas.Timestamp = info.index.max()
close_value = info.at[latest_time, "Close"]
assert isinstance(close_value, (numpy.floating, numpy.integer))
print(type(close_value), close_value)