import copy
import csv
import datetime
import hashlib
import os
import pickle
import ast
from datetime import *

from dateutil.parser import parse
from dateutil.tz import *

import pytz

from .hyperparameters import constants
from .stockPriceAPI import (getUpdatedCloseOpen, inTradingDay,
                            updateAllCloseOpen)


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


# Insert list of tweets into tweets database
def insertResults(results):
    collection = constants['stocktweets_client'].get_database('tweets_db').tweets
    count = 0
    total = 0
    for r in results:
        total += 1
        try:
            collection.insert_one(r)
            count += 1
        except Exception:
            continue
    print(count, total)


# Calculate ratio between two values
def calcRatio(bullNum, bearNum):
    maxVal = max(bullNum, bearNum)
    minVal = min(bullNum, bearNum)
    ratio = 0.0
    if (minVal == 0 or minVal == 0.0):
        ratio = maxVal
    else:
        ratio = maxVal * 1.0 / minVal

    if (bullNum < bearNum):
        ratio = -ratio
    return ratio


# Return a pickled object from path
def readPickleObject(path):
    if (os.path.exists(path) is False):
        return {}
    f = open(path, 'rb')
    result = pickle.load(f)
    f.close()
    return result


# Write pickled object to path
def writePickleObject(path, result):
    f = open(path, 'wb')
    pickle.dump(result, f)
    f.close()
    return


# Write open close to file if doesn't exist
def writeCachedCloseOpen(symbol, date, result):
    path = './cachedCloseOpen/' + symbol + '.csv'
    with open(path, "a") as symbolFile:
        csvWriter = csv.writer(symbolFile, delimiter=',')
        csvWriter.writerows([[date, result[0], result[1], result[2]]])
    return


# Extracts close open from CSVs
def readCachedCloseOpen(symbol):
    path = './cachedCloseOpen/' + symbol + '.csv'
    if (os.path.exists(path) is False):
        return {}
    with open(path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        result = {}
        for row in csv_reader:
            cDate = parse(row[0])
            res = (float(row[1]), float(row[2]), float(row[3]))
            result[cDate] = res
        return result


# Extracts tweets from cached tweets from CSVs
def readCachedTweets(symbol):
    with open('./cachedTweets/' + symbol + '.csv') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        result = {}
        for row in csv_reader:
            cDate = parse(row[0])
            d = datetime(cDate.year, cDate.month, cDate.day).strftime('%m/%d/%Y')
            if (d not in result):
                result[d] = []
            tweet = {'time': cDate, 'likeCount': int(row[3]),
                    'commentCount': int(row[2]), 'isBull': ast.literal_eval(row[1]),
                    'user': row[4]}
            result[d].append(tweet)
        return result


# Write tweets to cached CSVs
def writeCachedTweets(symbol, tweets):
    tweets = list(map(lambda x: [x['time'], x['isBull'], x['commentCount'],
                                 x['likeCount'], x['user']], tweets))

    with open('./cachedTweets/' + symbol + '.csv', "a") as f:
        csvWriter = csv.writer(f, delimiter=',')
        csvWriter.writerows(tweets)
    return


# Generate all combinations
def recurse(l, i, m, check, result):
    if (i >= len(l)):
        return

    if (l[i] == m):
        return
    new = copy.deepcopy(l)
    newStr = str(new).strip('[]')
    if (newStr not in check):
        check.add(newStr)
        result.append(new)
    new[i] += 1
    recurse(new, i, m, check, result)
    new1 = copy.deepcopy(l)
    newStr = str(new1).strip('[]')
    if (newStr not in check):
        check.add(newStr)
        result.append(new1)
    recurse(new1, i + 1, m, check, result)


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


# Return list of valid trading days from date on
def findTradingDays(date, upToDate):
    delta = timedelta(1)
    dates = []

    while (date < upToDate):
        # See if it's a valid trading day
        if ((date.day == 2 and date.month == 9) or
            date.day == 28 and date.month == 11):
            date += delta
            continue
        if (inTradingDay(date)):
            dates.append(date)
        date += delta

    return dates
