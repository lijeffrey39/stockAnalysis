import datetime
import math
import pickle
from multiprocessing import current_process
import yfinance as yf
import csv
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


def isTradingDay(time):
    return '%d-%02d-%02d' % (time.year, time.month, time.day) not in constants['not_trading_days']


# Firnd first trading day
def findDateString(time, cached_prices):
    day_increment = datetime.timedelta(days=1)

    # Find first day if tweeted after 4pm
    # If 4:00 on Wed, first day is Thursday
    # If 4:00 on Friday, first day is Monday
    if (time.hour >= 16):
        time += day_increment

    # If saturday, sunday or holiday, find first trading day to start from time
    while (isTradingDay(time) == False):
        time += day_increment

    return '%d-%02d-%02d' % (time.year, time.month, time.day)


def exportCloseOpen():
    path = 'newPickled/averaged_new.pkl'
    result = {}

    with open('cachedCloseOpen/new2.csv') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for row in csv_reader:
            first = row[0].split()
            symbol = first[0]
            date = first[1]
            res = [float(row[1]), float(row[2])]
            if (date not in result):
                result[date] = {}
            result[date][symbol] = res

    with open('cachedCloseOpen/new1.csv') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for row in csv_reader:
            first = row[0].split()
            symbol = first[0]
            date = first[1]
            res = [float(row[1]), float(row[2])]
            
            if (symbol in result[date]):
                prev = result[date][symbol]
                averaged = [(float(row[1]) + prev[0]) / 2, (float(row[2]) + prev[1]) / 2]
                result[date][symbol] = averaged
            else:
                result[date][symbol] = res

    dates = list(result.keys())
    dates.sort()
    for d in dates:
        print(d, len(result[d].keys()))

    f = open(path, 'wb')
    pickle.dump(result, f)
    f.close()


# Find close open from cached files
def findCloseOpenCached(symbol, time, cached_prices):
    day_increment = datetime.timedelta(days=1)

    # Find first day if tweeted after 4pm
    # If 4:00 on Wed, first day is Thursday
    # If 4:00 on Friday, first day is Monday
    if (time.hour >= 16):
        time += day_increment

    # If saturday, sunday or holiday, find first trading day to start from time
    while (isTradingDay(time) == False):
        time += day_increment

    # Find next day based on the picked first day
    end_day = time + day_increment
    while (isTradingDay(end_day) == False):
        end_day += day_increment

    start_str = '%d-%02d-%02d' % (time.year, time.month, time.day)
    end_str = '%d-%02d-%02d' % (end_day.year, end_day.month, end_day.day)
    if (start_str not in cached_prices or end_str not in cached_prices or 
        symbol not in cached_prices[start_str] or 
        symbol not in cached_prices[end_str]):
        return None

    start = cached_prices[start_str][symbol]
    end = cached_prices[end_str][symbol]
    closePrice = start[1]
    openPrice = end[0]
    return (closePrice, openPrice, (openPrice - closePrice) * 100 / closePrice)


# Find close open for date. Anytime before 4pm is
def findCloseOpen(symbol, time):
    db = constants['db_user_client'].get_database('user_data_db').updated_close_open
    dbYF = constants['db_client'].get_database('stocks_data_db').yfin_close_open
    dayIncrement = datetime.timedelta(days=1)
    nextDay = None
    count = 0

    # If saturday, sunday or holiday, find first trading day to start from time
    testDay = db.find_one({'_id': 'AAPL ' + time.strftime("%Y-%m-%d")})
    while (testDay is None and count != 10):
        time = datetime.datetime(time.year, time.month, time.day)
        time += dayIncrement
        testDay = db.find_one({'_id': 'AAPL ' + time.strftime("%Y-%m-%d")})
        count += 1

    # Find first day if tweeted after 4pm
    # If 4:00 on Wed, first day is Thursday
    # If 4:00 on Friday, first day is Monday
    timeDiff = time - datetime.datetime(time.year, time.month, time.day)
    if (timeDiff.total_seconds() >= (16 * 60 * 60)):
        time += dayIncrement
        testDay = db.find_one({'_id': 'AAPL ' + time.strftime("%Y-%m-%d")})
        while (testDay is None and count != 10):
            time += dayIncrement
            testDay = db.find_one({'_id': 'AAPL ' + time.strftime("%Y-%m-%d")})
            count += 1

    # Find next day based on the picked first day
    nextDay = time + dayIncrement
    testDay = db.find_one({'_id': 'AAPL ' + nextDay.strftime("%Y-%m-%d")})
    while (testDay is None and count != 10):
        nextDay += dayIncrement
        testDay = db.find_one({'_id': 'AAPL ' + nextDay.strftime("%Y-%m-%d")})
        count += 1

    if (count >= 10):
        return None

    start = db.find_one({'_id': symbol + ' ' + time.strftime("%Y-%m-%d")})
    end = db.find_one({'_id': symbol + ' ' + nextDay.strftime("%Y-%m-%d")})
    startYF = dbYF.find_one({'_id': symbol + ' ' + time.strftime("%Y-%m-%d")})
    endYF = dbYF.find_one({'_id': symbol + ' ' + nextDay.strftime("%Y-%m-%d")})

    # If either start or end are 0, don't allow it (fixes TTNP)
    if (end is None) or (start is None) or (end['open'] == 0) or (start['close'] == 0):
        if (endYF is None) or (startYF is None) or (endYF['open'] == 0) or (startYF['close'] == 0):
            return None
        else:
            closePrice = startYF['close']
            openPrice = endYF['open']
            return (closePrice, openPrice, round(((openPrice - closePrice) / closePrice) * 100, 3))
    elif (endYF is None) or (startYF is None) or (endYF['open'] == 0) or (startYF['close'] == 0):
        closePrice = start['close']
        openPrice = end['open']
        return (closePrice, openPrice, round(((openPrice - closePrice) / closePrice) * 100, 3))
    else:
        closePrice = (start['close'] + startYF['close'])/2
        openPrice = (end['open'] + endYF['open'])/2
        return (closePrice, openPrice, round(((openPrice - closePrice) / closePrice) * 100, 3))


# Close open averaged between 2 sources
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


def updateAllCloseOpen(stocks, dates, replace=False):
    removal = []
    for symbol in stocks:
        print(symbol)
        for date in dates:
            #replace = True
            dateString = date.strftime("%Y-%m-%d")
            idString = symbol + ' ' + dateString
            db = constants['db_user_client'].get_database('user_data_db').updated_close_open
            found = db.find_one({'_id': idString})
            if (found is None or replace):
                result = updatedCloseOpen(symbol, date)
                if (len(result) == 0):
                    continue
                print(result)
                if (found is not None):
                    db.delete_one({'_id': result['_id']})
                db.insert_one(result)
            else:
                print('found', found)


def updatedCloseOpen(symbol, date):
    dateString = date.strftime("%Y%m%d")
    baseURL = "https://cloud.iexapis.com/stable/stock/" + symbol + "/chart/date/"
    restURL = "?chartByDay=True&token=sk_c38d3babd3c144a886597ce6d014e543"
    URL = baseURL + dateString + restURL
    r = requests.get(url=URL)
    data = r.json()
    if (len(data) == 0):
        return {}
    data = data[0]
    _id = symbol + ' ' + data['date']
    result = {'_id': _id, 'open': data['open'], 'close': data['close']}
    return result

def updateyfinanceCloseOpen(symbol, date):
    dateString = date.strftime("%Y-%m-%d")
    tick = yf.Ticker(symbol)
    try:
        yOpen = tick.history(start=date, end=date)[['Open']].values[0][0].item()
        yClose = tick.history(start=date, end=date)[['Close']].values[0][0].item()  
    except:
        return {}
    if yOpen is None:
        return {}
    elif yClose is None:
        return {}
    _id = symbol + ' ' + dateString
    result = {'_id': _id, 'open': yOpen, 'close': yClose}
    return result

def updateAllCloseOpenYF(stocks, dates, replace=False):
    for symbol in stocks:
        print(symbol)
        for date in dates:
            #replace = True
            dateString = date.strftime("%Y-%m-%d")
            idString = symbol + ' ' + dateString
            db = constants['db_client'].get_database('stocks_data_db').yfin_close_open
            found = db.find_one({'_id': idString})
            if (found is None or replace):
                result = updateyfinanceCloseOpen(symbol, date)
                if (len(result) == 0):
                    continue
                print(result)
                if (found is not None):
                    db.delete_one({'_id': result['_id']})
                db.insert_one(result)
            else:
                print('found', found)

def getCloseOpenInterval(symbol, date, interval):
    db = constants['db_user_client'].get_database('user_data_db').updated_close_open
    nextDay = None
    count = 0

    # If saturday, sunday or holiday, find first trading day to start from time
    testDay = db.find_one({'_id': 'AAPL ' + date.strftime("%Y-%m-%d")})
    while (testDay is None and count != 10):
        date = datetime.datetime(date.year, date.month, date.day)
        date += datetime.timedelta(days=1)
        testDay = db.find_one({'_id': 'AAPL ' + date.strftime("%Y-%m-%d")})
        count += 1

    # Find next day based on the picked first day
    nextDay = date + datetime.timedelta(days=interval)
    testDay = db.find_one({'_id': 'AAPL ' + nextDay.strftime("%Y-%m-%d")})
    while (testDay is None and count != 10):
        print(testDay)
        nextDay += datetime.timedelta(days=1)
        testDay = db.find_one({'_id': 'AAPL ' + nextDay.strftime("%Y-%m-%d")})
        count += 1

    if (count >= 10):
        return None

    start = db.find_one({'_id': symbol + ' ' + date.strftime("%Y-%m-%d")})
    end = db.find_one({'_id': symbol + ' ' + nextDay.strftime("%Y-%m-%d")})
    print(date.strftime("%Y-%m-%d"))
    print(nextDay.strftime("%Y-%m-%d"))
    # If either start or end are 0, don't allow it (fixes TTNP)
    if (end is None) or (start is None) or (end['open'] == 0) or (start['close'] == 0):
        return None
    else:
        firstPrice = start['close']
        secondPrice = end['close']
        return (firstPrice, secondPrice, round(((secondPrice - firstPrice) / firstPrice) * 100, 3))

def getUpdatedCloseOpen(symbol, date):
    exceptions = [datetime.datetime(2019, 11, 27)]
    db = constants['db_user_client'].get_database('user_data_db').updated_close_open
    days_in_future = datetime.timedelta(days=1)
    future_date = date + days_in_future
    if (future_date.weekday() > 4):
        next_weekday = datetime.timedelta(days=7 - future_date.weekday())
        future_date += next_weekday

    # Edge Case
    if (date.day == 27 and date.month == 11):
        future_date = date + datetime.timedelta(days=2)

    if (date.day == 30 and date.month == 8):
        future_date = date + datetime.timedelta(days=4)

    start = db.find_one({'_id': symbol + ' ' + date.strftime("%Y-%m-%d")})
    end = db.find_one({'_id': symbol + ' ' + future_date.strftime("%Y-%m-%d")})

    if (end is None) or (start is None) or start == 0 or end == 0:
        print(start, end)
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
    market_open = datetime.datetime(time.year, time.month, time.day, 9, 30)
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


# Transfer non labeled tweets to new database (about 50% are unlabled)
def transferNonLabeled(stocks):
    unlabledDB = constants['db_user_client'].get_database('tweets').tweets_unlabeled
    tweetsDB = constants['stocktweets_client'].get_database('tweets_db').tweets

    for s in stocks:
        tweets = tweetsDB.find({'$and': [{'symbol': s}, {'isBull': None}]})
        mappedTweets = list(map(lambda doc: doc, tweets))
        mappedTweets.sort(key=lambda x: x['time'], reverse=True)
        count = 0
        realCount = 0
        print(s, len(mappedTweets))
        for t in mappedTweets:
            count += 1
            # print(t)
            try:
                unlabledDB.insert_one(t)
                realCount += 1
            except:
                pass
            tweetsDB.delete_one({'_id': t['_id']})
            if (count % 100 == 0):
                print(s, count, len(mappedTweets))
        print(s, realCount, count)
