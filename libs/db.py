from peewee import *
import peewee
import datetime
import arrow
from peewee import DoesNotExist

from libs.read_settings import read_config
config = read_config()

db = SqliteDatabase("stocks.db")


class BaseModel(Model):
    class Meta:
        database = db


class Stock(BaseModel):
    code = CharField()
    name = CharField()
    price = FloatField(null=True)
    volume = FloatField(null=True)
    exchange = CharField()
    type = CharField(null=True)
    date = DateTimeField(default=datetime.datetime.now)

class Price(BaseModel):
    stock = CharField()
    date = DateTimeField()
    open = FloatField()
    high = FloatField()
    low = FloatField()
    close = FloatField()

    class Meta:
        indexes = (
            (('stock', 'date'), True),  # Unique index
        )

def create_price_table():
    Price.create_table()


def create_stock_table():
    Stock.create_table()


def check_earliest_price_date():
    try:
        earliest_price = Price.select(fn.MIN(Price.date)).scalar()
        if earliest_price:
            return earliest_price.date()  # Return just the date part
        return None
    except Price.DoesNotExist:
        return None
    except peewee.OperationalError:
        print("Price table does not exist. Creating it now.")
        create_price_table()
        return None

def get_price_from_db(stock, date, look_backwards=True):
    """
    Retrieves price data for a given stock and date from the database.

    Args:
    stock (str): The stock symbol.
    date (datetime): The date for which to retrieve the price.
    look_backwards (bool, optional): If True, looks for the most recent price data on or before the given date.
                                     If False, looks for the earliest price data on or after the given date.
                                     Defaults to True.

    Returns:
    dict: A dictionary containing price data (open, high, low, close, date) if found, None otherwise.

    Raises:
    SystemExit: If look_backwards is False and no future price data is found.
    """
    try:
        if look_backwards:
            price_data = Price.select().where(
                (Price.stock == stock) & (Price.date <= date)
            ).order_by(Price.date.desc()).first()
        else:
            price_data = Price.select().where(
                (Price.stock == stock) & (Price.date >= date)
            ).order_by(Price.date.asc()).first()

        if price_data:
            if price_data.date.date() != date.date():
                direction = "from" if look_backwards else "for"
                print(f"(i) using price data {direction} {price_data.date.date()} for {stock}")
            return {
                'open': price_data.open,
                'high': price_data.high,
                'low': price_data.low,
                'close': price_data.close,
                'date': price_data.date
            }
        else:
            direction = "on or before" if look_backwards else "on or after"
            print(f"(!) no price data found for {stock} {direction} {date}")
            if not look_backwards:
                print("Terminating due to lack of future price data.")
                sys.exit(1)
            return None
    except DoesNotExist:
        print(f"(!) no price data found for {stock}")
        return None

def delete_all_prices():
    Price.delete().execute()

def bulk_add_prices(prices_list):
    with db.atomic():
        for batch in chunked(prices_list, 100):
            Price.insert_many(batch).execute()

def delete_all_stocks(exchange):
    query = Stock.delete().where(Stock.exchange == exchange)
    query.execute()


def bulk_add_stocks(stocks_list_of_dict):
    list_length = 100
    # Workaround, see https://github.com/coleifer/peewee/issues/948
    chunks = [
        stocks_list_of_dict[x : x + list_length]
        for x in range(0, len(stocks_list_of_dict), list_length)
    ]
    for chunk in chunks:
        with db.atomic():
            Stock.insert_many(chunk).execute()


def get_stocks(exchange=None, price_min=None, price_max=None, min_volume=None, codes=None):
    price_min = 0 if price_min is None else price_min
    price_max = 10e9 if price_max is None else price_max
    min_volume = 0 if min_volume is None else min_volume

    try:
        if codes is not None:
            # If a list of stock codes is provided
            if isinstance(codes, str):
                codes = codes.split(',')
            stocks = Stock.select().where(Stock.code.in_(codes))
            return stocks

        if config["filters"]["stocks_only"]:
            print("Excluding funds and ETF per settings")
            stocks = Stock.select().where(
                (Stock.price >= price_min)
                & (Stock.price < price_max)
                & (Stock.volume > min_volume)
                & (Stock.exchange == exchange)
                & (Stock.type == 'Common Stock')
            )
        else:
            stocks = Stock.select().where(
                (Stock.price >= price_min)
                & (Stock.price < price_max)
                & (Stock.volume > min_volume)
                & (Stock.exchange == exchange)
            )
        if len(stocks) == 0:
            print("Warning: no stocks in the database")

    except peewee.OperationalError:
        print("Error: table not found. Update the stocks list first.")
        exit(0)

    return stocks


def get_update_date(exchange):
    try:
        record = Stock.select().where(Stock.exchange == exchange).first()
        record = arrow.get(record.date)
        record = record.replace(tzinfo="Australia/Sydney")
        return record
    except peewee.OperationalError:
        print("Error: table not found. Update the stocks list first.")
        exit(0)
