from selenium import webdriver
from bs4 import BeautifulSoup
import yfinance as yf
from libs.exceptions_lib import exception_handler
from libs.settings import asx_instruments_url, tzinfo
import arrow

options = webdriver.ChromeOptions()

options.add_experimental_option('excludeSwitches', ['enable-logging'])  # removes the USB warning on Windows
options.add_argument(
    "--headless"
)  # headless means that no browser window is opened

industry_mapping = {
    "Energy": "XEJ",
    "Basic Materials": "XMJ",
    "Industrials": "XNJ",
    "Consumer Cyclical": "XDJ",
    "Consumer Defensive": "XSJ",
    "Healthcare": "XHJ",
    "Financial Services": "XIJ",
    "Technology": "XFJ",
    "Communication Services": "XTJ",
    "Utilities": "XUJ",
    "Real Estate": "XPJ"
}

def get_asx_symbols():
    driver = webdriver.Chrome(options=options)
    driver.get(asx_instruments_url)
    content = driver.page_source
    driver.close()

    soup = BeautifulSoup(content, 'html.parser')
    data = []
    table = soup.find('table', attrs={'class': 'mi-table mt-6'})
    table_body = table.find('tbody')

    rows = table_body.find_all('tr')
    for row in rows:
        cols = row.find_all('td')
        cols = [elem.text.strip() for elem in cols]
        data.append(cols)

    stocks = [dict(code=elem[2], name=elem[3], price=float(elem[4].replace('$', ''))) for elem in data]
    print(f"{len(data)} stocks retreived "
          f"({stocks[0]['code']} [{stocks[0]['price']}] - "
          f"{stocks[-1]['code']} [{stocks[-1]['price']}])")

    return stocks


def ohlc_last_day_workaround(df):
    # Need to check whether the last day is today and remove if so
    # Due to YFinance bug - not showing the right data for the current day
    hist_last_day = df["Date"].iloc[-1]
    hist_last_day = arrow.get(hist_last_day)
    hist_last_day = hist_last_day.replace(tzinfo=tzinfo)
    current_date = arrow.now()
    if hist_last_day.format('YYYY-MM-DD') == current_date.format('YYYY-MM-DD'):
        df.drop(df.tail(1).index, inplace=True)
    return df


@exception_handler(handler_type="yfinance")
def get_stock_data(symbol):
    period = '300d'
    interval = '1d'

    asset = yf.Ticker(symbol)
    hist = asset.history(period=period, interval=interval).reset_index(drop=False)

    if hist.empty:
        print(f"Ticker {symbol} not found on Yahoo Finance")
        return None, None

    hist = ohlc_last_day_workaround(hist)
    hist.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'div', 'splits']

    # For compatibility with the TA library
    return hist[['timestamp', 'open', 'high', 'low', 'close']], hist[['timestamp', 'volume']]

def ohlc_daily_to_weekly(df):
    df['week_number'] = df['timestamp'].dt.isocalendar().week
    df['year'] = df['timestamp'].dt.year
    df_weekly = df.groupby(['year', 'week_number']).agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'})
    # rename week to timestamp. even though it is not super correct, it's fine to do that for our purposes
    df_weekly = df_weekly.reset_index()
    df_weekly.columns = ['year', 'timestamp', 'open', 'high', 'low', 'close']
    return df_weekly


def ohlc_daily_to_monthly(df):
    df['month_number'] = df['timestamp'].dt.month
    df['year'] = df['timestamp'].dt.year
    df_monthly = df.groupby(['year', 'month_number']).agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'})
    # rename week to timestamp. even though it is not super correct, it's fine to do that for our purposes
    df_monthly = df_monthly.reset_index()
    df_monthly.columns = ['year', 'timestamp', 'open', 'high', 'low', 'close']
    return df_monthly


@exception_handler(handler_type="yfinance")
def get_industry(code):
    asset = yf.Ticker(code)
    info = asset.info
    industry = info["sector"]
    return industry


def map_industry_code(industry_name):
    return industry_mapping[industry_name]