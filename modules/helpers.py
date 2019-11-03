import datetime
import hashlib
import os
from datetime import *

from dateutil.tz import *

import pytz

from .stockPriceAPI import inTradingDay
from .hyperparameters import constants


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


# Returns list of all stocks
def getAllStocks():
    allStocks = constants['db_client'].get_database('stocktwits_db').all_stocks
    cursor = allStocks.find()
    stocks = list(map(lambda document: document['_id'], cursor))
    stocks.sort()
    return stocks


# Returns actual list of all stocks
def getActualAllStocks():
    allStocks = constants['db_client'].get_database('stocktwits_db').actually_all_stocks
    cursor = allStocks.find()
    stocks = list(map(lambda document: document['_id'], cursor))
    restStocks = getAllStocks()
    stocks.extend(restStocks)
    stocks.sort()
    return stocks


# Hash function for creating id in DB
def customHash(string):
    return int(hashlib.sha224(bytearray(string, 'utf8')).hexdigest()[:15], 16)


# Close and quit driver
def endDriver(driver):
    driver.close()
    driver.quit()


# Convert datetime object to EST
def convertToEST(dateTime):
    if (constants['current_timezone'] != 'EDT' and
       constants['current_timezone'] != 'EST' and
       constants['current_timezone'] != 'Eastern Daylight Time'):
        # localize to current time zone
        currTimeZone = pytz.timezone(constants['current_timezone'])
        dateTime = currTimeZone.localize(dateTime)
        dateTime = dateTime.astimezone(constants['eastern_timezone'])
        dateTime = dateTime.replace(tzinfo=None)
        return dateTime
    return dateTime


def inTradingHours(dateTime, symbol):
    day = dateTime.weekday()
    nineAM = datetime.datetime(dateTime.year, dateTime.month, dateTime.day, 9, 30)
    fourPM = datetime.datetime(dateTime.year, dateTime.month, dateTime.day, 16, 0)

    if (dateTime < nineAM or dateTime >= fourPM or day == "0" or day == "6"):
        return False

    historical = historicalFromDict(symbol, dateTime)

    if (len(historical) == 0):
        return False

    strDate = dateTime.strftime("%X")[:5]
    found = False

    for ts in historical:
        if (ts.get('minute') == strDate):
            found = True
    return found


def isTradingDay(date):
    path = date.strftime("stocksResults/%m-%d-%y.csv")
    return (os.path.isfile(path))


# Return list of valid trading days from date on
def findTradingDays(date, upToDate):
    delta = timedelta(1)
    dates = []

    while (date < upToDate):
        # See if it's a valid trading day
        if (inTradingDay(date)):
            dates.append(date)
        date += delta

    return dates


def chunkIt(seq, num):
    avg = len(seq) / float(num)
    out = []
    last = 0.0

    while last < len(seq):
        out.append(seq[int(last):int(last + avg)])
        last += avg

    return out
