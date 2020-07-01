import ast
import copy
import csv
import datetime
import hashlib
import math
import os
import pickle
import holidays

import pytz
from dateutil.parser import parse
from dateutil.tz import *

from .hyperparameters import constants
from .stockPriceAPI import (inTradingDay, isTradingDay)

# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


# Find average time
def findAverageTime(times):
    times.sort()
    mid = len(times) // 2
    if (len(times) % 2 == 0):
        delta = (times[mid] - times[mid - 1]) / 2
        return times[mid - 1] + delta
    else:
        return times[mid]


# Insert list of tweets into tweets database
def insertResults(results):
    collection = constants['stocktweets_client'].get_database('tweets_db').tweets
    count = 0
    count1 = 0
    total = 0
    bullbearcount = 0
    for r in results:
        total += 1
        query = copy.deepcopy(r)
        if (((query['isBull'] is True) or (query['isBull'] is False)) and (query['time'] > (datetime.datetime.now()-datetime.timedelta(days=21)))):
                bullbearcount+=1
        del query['_id']
        del query['likeCount']
        del query['commentCount']
        date = r['time']
        dateStart = datetime.datetime(date.year, date.month, date.day, 0)
        dateEnd = datetime.datetime(date.year, date.month, date.day, 23, 59)
        query['time'] = {'$gte': dateStart, '$lt': dateEnd}
        tweet = list(collection.find(query))
        if (len(tweet) != 0):
            count1 += 1
            continue
        try:
            collection.insert_one(r)
            count += 1
        except Exception:
            continue
    usercollection = constants['db_user_client'].get_database('user_data_db').users
    print(bullbearcount)
    usercollection.update_one({'_id': results[0]['user']}, {'$set': {'bbcount': bullbearcount}})          
    print(count, count1, total)


# Calculate ratio between two values
# Alway < 0 or > 0
def calcRatio(bullNum, bearNum):
    maxVal = max(bullNum, bearNum)
    minVal = min(bullNum, bearNum)
    ratio = 0.0
    if (minVal == 0 or minVal == 0.0):
        ratio = maxVal
    else:
        ratio = maxVal * 1.0 / minVal
        ratio -= 1 # offset by 1
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
    path = './cachedTweets/' + symbol + '.csv'
    if (os.path.exists(path) is False):
        with open('./cachedTweets/' + symbol + '.csv', "a") as f:
            csvWriter = csv.writer(f, delimiter=',')
            csvWriter.writerows([])
        return []

    with open(path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        result = []
        for row in csv_reader:
            cDate = parse(row[0])
            # d = datetime.datetime(cDate.year, cDate.month, cDate.day).strftime('%m/%d/%Y')
            tweet = {'time': cDate, 
                    'likeCount': int(row[3]),
                    'commentCount': int(row[2]),
                    'isBull': ast.literal_eval(row[1]),
                    'user': row[4]}
            result.append(tweet)
        return result

def convertTweetToString(tweet):
    result = ""
    result += tweet['time'].strftime("%m/%d/%Y, %H:%M:%S")
    result += tweet['user']
    result += str(tweet['isBull'])
    result += (str(tweet['likeCount']) + str(tweet['commentCount']))
    return result

# Write tweets to cached CSVs
def writeCachedTweets(symbol, tweets):
    curr_tweets = readCachedTweets(symbol)
    mapped_curr_tweets = set(list(map(convertTweetToString, curr_tweets)))
    new_tweets = list(filter(lambda t: convertTweetToString(t) not in mapped_curr_tweets, tweets))
    new_tweets = list(map(lambda x: [x['time'], x['isBull'], x['commentCount'],
                                 x['likeCount'], x['user']], new_tweets))
    with open('./cachedTweets/' + symbol + '.csv', 'a') as f:
        csvWriter = csv.writer(f, delimiter=',')
        csvWriter.writerows(new_tweets)
    return




# Returns list of all stocks
def getAllStocks():
    allStocks = constants['db_client'].get_database('stocktwits_db').all_stocks
    cursor = allStocks.find()
    stocks = list(map(lambda document: document['_id'], cursor))
    stocks.sort()
    stocks.remove('YRIV') # delisted
    # stocks.remove('NAKD') # fixed
    # stocks.remove('CEI') # fixed
    # stocks.remove('SLS') # fixed
    # stocks.remove('SES') # fixed ?
    # stocks.remove('AKER') # fixed
    # stocks.remove('ASNA') # fixed
    # stocks.remove('TRXC') # fixed
    # stocks.remove('TVIX') # fixed
    # stocks.remove('GUSH') # fixed
    # stocks.remove('PLX') # fixed
    # stocks.remove('AMRH') # fixed
    # stocks.remove('LODE') # fixed
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


def findAllDays(date, upToDate):
    delta = datetime.timedelta(1)
    dates = []
    while (date <= upToDate):
        dates.append(date)
        date += delta
    return dates


# Return list of valid trading days from date on
def findTradingDays(date, upToDate):
    delta = datetime.timedelta(1)
    trading_days = constants['trading_days']
    dates = []
    while (date <= upToDate):
        if (date.strftime("%Y-%m-%d") in trading_days):
            dates.append(date)
        date += delta
    return dates


# Find weight between 0-1 based on function
def findWeight(date, function):
    day_increment = datetime.timedelta(days=1)
    start_date = date
    end_date = start_date - day_increment

    # 4pm cutoff
    cutoff = datetime.datetime(date.year, date.month, date.day, 16)
    if (start_date > cutoff or isTradingDay(start_date) == False):
        end_date = start_date
        start_date += day_increment
        while (isTradingDay(start_date) == False):
            start_date += day_increment

    while (isTradingDay(end_date) == False):
        end_date -= day_increment

    start_date = datetime.datetime(start_date.year, start_date.month, start_date.day, 16)
    end_date = datetime.datetime(end_date.year, end_date.month, end_date.day, 16)
    difference = (date - end_date).total_seconds()
    total_seconds = (start_date - end_date).total_seconds()
    x = difference / total_seconds

    if (function == '1'):
        return 1
    elif (function == 'sqrt(x)'):
        return math.sqrt(x)
    elif (function == 'x'):
        return x
    elif (function == 'x^2'):
        return x * x
    elif (function == 'x^4'):
        return x * x * x * x
    elif (function == 'log(x)'):
        x = (x * 3) + 0.05
        y = math.log(x) + 3
        yMax = math.log(3.05) + 3
        return y / yMax
    else:
        return 0


# Return number of days since join date
def findJoinDate(dateString):
    dateTime = parse(dateString)
    currTime = convertToEST(datetime.datetime.now())
    days = (currTime - dateTime).days
    return days
