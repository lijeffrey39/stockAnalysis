import datetime
import math
from multiprocessing import current_process

import requests

from .hyperparameters import constants


# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


# Invalid symbols so they aren't check again
invalidSymbols = []
currHistorical = []
currSymbol = ""
currDateTimeStr = ""


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


def averagedOpenClose(symbol, date):
    updatedOpenClose = getUpdatedCloseOpen(symbol, date)
    ogOpenClose = closeToOpen(symbol, date)

    if (updatedOpenClose is None and ogOpenClose is None):
        return None
    elif (updatedOpenClose is None):
        return ogOpenClose
    elif (ogOpenClose is None):
        return updatedOpenClose
    else:
        closePrice = (updatedOpenClose[0] + ogOpenClose[0]) / 2.0
        openPrice = (updatedOpenClose[1] + ogOpenClose[1]) / 2.0
        return (closePrice, openPrice, round(((openPrice - closePrice) / closePrice) * 100, 3))


def updateAllCloseOpen(stocks, dates):
    db = constants['db_client'].get_database('stocks_data_db').updated_close_open
    for symbol in stocks:
        for date in dates:
            dateString = date.strftime("%Y-%m-%d")
            idString = symbol + ' ' + dateString
            found = db.find_one({'_id': idString})
            if (found is None):
                updateCloseOpen(symbol, date, db)


def updateCloseOpen(symbol, date, db):
    dateString = date.strftime("%Y%m%d")
    baseURL = "https://cloud.iexapis.com/stable/stock/" + symbol + "/chart/date/"
    restURL = "?chartByDay=True&token=sk_f993e71175fc4213a0cea1515436270e"
    URL = baseURL + dateString + restURL
    r = requests.get(url=URL)
    data = r.json()
    if (len(data) == 0):
        return
    data = data[0]

    _id = symbol + ' ' + data['date']
    result = {'_id': _id, 'open': data['open'], 'close': data['close']}
    db.insert_one(result)
    print(result)


def getUpdatedCloseOpen(symbol, date):
    db = constants['db_client'].get_database('stocks_data_db').updated_close_open
    days_in_future = datetime.timedelta(days=1)
    future_date = date + days_in_future
    if future_date.weekday() > 4:
        next_weekday = datetime.timedelta(days=7 - future_date.weekday())
        future_date += next_weekday
    start = db.find_one({'_id': symbol + ' ' + date.strftime("%Y-%m-%d")})
    end = db.find_one({'_id': symbol + ' ' + future_date.strftime("%Y-%m-%d")})
    if (end is None) or (start is None) or start == 0 or end == 0:
        return None
    else:
        closePrice = start['close']
        openPrice = end['open']
        return (closePrice, openPrice, round(((openPrice - closePrice) / closePrice) * 100, 3))


def inTradingDay(date):
    market_open = datetime.datetime(date.year, date.month, date.day, 9, 30)
    market_close = datetime.datetime(date.year, date.month, date.day, 16, 0)
    day = date.weekday()

    if (date < market_open or date >= market_close or day == 5 or day == 6):
        return False
    return True


def closeToOpen(ticker, time, days=1):
    days_in_future = datetime.timedelta(days=days) 
    future_date = time+days_in_future
    if future_date.weekday() > 4:
        next_weekday = datetime.timedelta(days=7-future_date.weekday())
        future_date += next_weekday
    start = getPriceAtEndOfDay(ticker, time)
    end = getPriceAtBeginningOfDay(ticker, future_date)
    if (end is None) or (start is None) or start == 0 or end == 0:
        return None
    else:
        return (start, end, round(((end-start)/start) * 100, 3))


def getPrice(ticker, time):
    # time should be in datetime.datetime format
    market_open = datetime.datetime(time.year, time.month, time.day, 9, 35)
    market_close = datetime.datetime(time.year, time.month, time.day, 16, 0)
    if time >= market_open and time <= market_close:
        rounded_minute = 5 * round((float(time.minute) + float(time.second)/60)/5)
        minute_adjustment = datetime.timedelta(minutes=rounded_minute-time.minute)
        adj_time = time + minute_adjustment
        adj_time = adj_time.replace(second=0, microsecond=0)
        query_time_s = adj_time.strftime('%Y-%m-%d %H:%M:%S')

    if time > market_close:
        tomorrow = time + datetime.timedelta(days=1)
        next_opening = tomorrow.replace(hour=9, minute=35, second=0)
        query_time_s = next_opening.strftime('%Y-%m-%d %H:%M:%S')

    if time < market_open:
        query_time_s = market_open.strftime('%Y-%m-%d %H:%M:%S')

    query_id = ticker+query_time_s
    stock_price_db = constants['db_client'].get_database('stocks_data_db').stock_data 
    price_data = stock_price_db.find_one({'_id': query_id})
    if price_data is None:
        # print('Date out of range or stock not tracked')
        return None
    return price_data['price']


def getPriceAtEndOfDay(ticker, time):
    market_close = datetime.datetime(time.year, time.month, time.day, 15, 50)
    return getPrice(ticker, market_close)


def getPriceAtBeginningOfDay(ticker, time):
    market_open = datetime.datetime(time.year, time.month, time.day, 9, 40)
    return getPrice(ticker, market_open)


def historicalFromDict(symbol, dateTime):
    global invalidSymbols
    global currSymbol
    global currHistorical
    global currDateTimeStr
    historial = []
    dateTimeStr = dateTime.strftime("%Y-%m-%d")

    if (symbol is None):
        return []

    if (symbol != currSymbol or dateTimeStr != currDateTimeStr):
        currSymbol = symbol
        currDateTimeStr = dateTimeStr
        try:
            currHistorical = get_historical_intraday(symbol, dateTime, token = "pk_55ae0f09f54547eaaa2bd514cf3badc6")
            return currHistorical
        except:
            print("Invalid ticker")
            currHistorical = []
            return currHistorical
    else:
        return currHistorical


# Find historical stock data given date and ticker
def findHistoricalData(dateTime, symbol, futurePrice):
    historical = []
    originalDateTime = dateTime

    # if it is a saturday or sunday, find friday's time if futurePrice == False
    # Else find monday's time if it's futurePrice
    if (futurePrice):
        historical = historicalFromDict(symbol, dateTime)
        delta = datetime.timedelta(1)
        # keep going until a day is found
        count = 0
        while (len(historical) == 0):
            dateTime = dateTime + delta
            historical = historicalFromDict(symbol, dateTime)
            count += 1
            if (count == 10):
                historical = []
                dateTime = originalDateTime
                break
    else:
        historical = historicalFromDict(symbol, dateTime)

    return (historical, dateTime)


# Price of a stock at a certain time given historical data
def priceAtTime(dateTime, historical):
    foundAvg = ""
    found = False
    for ts in historical:
        if (int(ts.get("minute").replace(":","")) >= int((dateTime.strftime("%X")[:5]).replace(":",""))):
            foundAvg = ts.get('average')
            foundAvg1 = ts.get('marketAverage')
            foundAvg2 = ts.get('marketHigh')
            if (foundAvg != None):
                found = True
                break
            else:
                if (foundAvg1 != None):
                    found = True
                    foundAvg = foundAvg1
                    break
                else:
                    continue

    # Go from end to front
    if (found is False):
        lastPos = len(historical) - 1
        foundAvg = None
        while (foundAvg is None and lastPos > 0):
            last = historical[lastPos]
            foundAvg = last.get('average')
            foundAvg1 = last.get('marketAverage')
            if (foundAvg1 is not None):
                foundAvg = foundAvg1
                break
            lastPos = lastPos - 1

    return foundAvg
