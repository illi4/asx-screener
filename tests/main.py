import os, sys
import string

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # to access the parent dir

from libs.stocktools import get_stock_data

ohlc_daily, volume_daily = get_stock_data("XLE")
print(ohlc_daily)