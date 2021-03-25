from libs.settings import overextended_threshold_percent
from libs.techanalysis import MA
from libs.helpers import format_bool
import numpy as np


def met_conditions_bullish(
    ohlc_with_indicators_daily,
    volume_daily,
    ohlc_with_indicators_weekly,
    consider_volume_spike=True,
    output=True,
    stock_name=''
):
    # Checks if price action meets conditions
    # Rules: MAs trending up, fast above slow, bullish TD count, volume spike
    daily_condition_close_higher = (  # closes higher
        ohlc_with_indicators_daily["close"].iloc[-1]
        > ohlc_with_indicators_daily["close"].iloc[-2]
    )
    daily_condition_td = (  # bullish TD count
        ohlc_with_indicators_daily["td_direction"].iloc[-1] == "green"
    )
    weekly_condition_td = (  # bullish TD count
        ohlc_with_indicators_weekly["td_direction"].iloc[-1] == "green"
    )

    # MA check
    ma10 = MA(ohlc_with_indicators_daily, 10)
    ma20 = MA(ohlc_with_indicators_daily, 20)
    ma30 = MA(ohlc_with_indicators_daily, 30)

    # MA30 may be None for too new stocks
    ma30_nan = np.isnan(ma30["ma30"].iloc[-1])

    if not ma30_nan:
        ma_consensio = (
            ma10["ma10"].iloc[-1] > ma20["ma20"].iloc[-1] > ma30["ma30"].iloc[-1]
        )
    else:
        ma_consensio = False
        print("-- note: MA30 is NaN, the stock is too new")

    # Volume MA and volume spike over the considered day
    if consider_volume_spike:
        volume_ma_20 = MA(volume_daily, 20, colname="volume")
        mergedDf = volume_daily.merge(volume_ma_20, left_index=True, right_index=True)
        mergedDf.dropna(inplace=True, how="any")
        mergedDf["volume_above_average"] = mergedDf["volume"].ge(
            mergedDf["ma20"]
        )  # GE is greater or equal
        volume_condition = bool(mergedDf["volume_above_average"].iloc[-1])
    else:
        volume_condition = True

    # All MAs are rising
    ma_rising = (
        (ma10["ma10"].iloc[-1] >= ma10["ma10"].iloc[-3])
        and (ma20["ma20"].iloc[-1] >= ma20["ma20"].iloc[-3])
        and (ma30["ma30"].iloc[-1] >= ma30["ma30"].iloc[-3])
    )

    # Close for the last week is not more than X% from the 4 weeks ago
    not_overextended = (
        ohlc_with_indicators_weekly["close"].iloc[-1]
        < (1 + overextended_threshold_percent / 100)
        * ohlc_with_indicators_weekly["close"].iloc[-4]
    )

    # Last candle should actually be green (close above open)
    last_candle_is_green = (
        ohlc_with_indicators_daily["close"].iloc[-1]
        > ohlc_with_indicators_daily["open"].iloc[-1]
    )

    # Most recent close should be above the bodies of 10 candles prior
    ohlc_with_indicators_daily["candle_body_upper"] = ohlc_with_indicators_daily[
        ["open", "close"]
    ].max(axis=1)
    close_most_recent = float(ohlc_with_indicators_daily["close"].iloc[-1])
    ohlc_with_indicators_daily["lower_than_recent"] = ohlc_with_indicators_daily[
        "candle_body_upper"
    ].lt(
        close_most_recent
    )  # LT is lower than
    # Do not include the most recent itself in the calculation. Take 10 previous before that.
    previous_n_lower_than_recent = ohlc_with_indicators_daily["lower_than_recent"][
        -11:-1
    ].tolist()
    upper_condition = not (False in previous_n_lower_than_recent)

    if output:
        print(
            f"- {stock_name} MRI: D [{format_bool(daily_condition_td)}] / W [{format_bool(weekly_condition_td)}] | "
            f"Consensio: [{format_bool(ma_consensio)}] | MA rising: [{format_bool(ma_rising)}] | "
            f"Not overextended: [{format_bool(not_overextended)}] \n"
            f"- {stock_name} Higher close: [{format_bool(daily_condition_close_higher)}] | "
            f"Volume condition: [{format_bool(volume_condition)}] | Upper condition: [{format_bool(upper_condition)}] | "
            f"Last candle is green: [{format_bool(last_candle_is_green)}]"
        )

    confirmation = [
        daily_condition_td,
        weekly_condition_td,
        ma_consensio,
        ma_rising,
        not_overextended,
        daily_condition_close_higher,
        volume_condition,
        upper_condition,
        last_candle_is_green,
    ]
    numerical_score = round(
        5 * sum(confirmation) / len(confirmation), 1
    )  # score X (of 5)
    result = False not in confirmation

    return result, numerical_score
