import ast
import csv
import datetime
import math
import os
import pickle
import statistics
import time
from functools import reduce

from dateutil.parser import parse

from .helpers import (readPickleObject,
                      writePickleObject,
                      recurse,
                      calcRatio,
                      writeCachedTweets,
                      readCachedTweets,
                      readCachedCloseOpen,
                      writeCachedCloseOpen)
from .hyperparameters import constants
from .messageExtract import *
from .stockPriceAPI import (getUpdatedCloseOpen,
                            updateAllCloseOpen)


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


# Build result for sentiment of tweets
def buildResult():
    result = {'totalLabeledTweets': 0}
    for start in ['', 'U']:
        for ending in ['Return', 'ReturnUnique']:
            for second in ['user', 'stock']:
                for label in ['Bull', 'Bear']:
                    result[start + second + label + ending] = 0.0
    for label in ['bull', 'bear']:
        for start in ['', 'U']:
            result[start + label + 'Count'] = 0
    for start in ['', 'U']:
        for ending in ['Return', 'ReturnUnique']:
            for second in ['user', 'stock']:
                result[start + second + ending + 'Ratio'] = 0.0
    return result


# Calculate features based on list of tweets
def newCalculateSentiment(tweets, symbol, userAccDict):
    usersTweeted = {'bull': set([]), 'bear': set([])}
    result = buildResult()

    for tweet in tweets:
        username = tweet['user']
        isBull = tweet['isBull']
        result['totalLabeledTweets'] += 1
        if (username not in userAccDict or symbol not in userAccDict[username]['perStock']):
            continue

        lWord = 'bull'
        uWord = 'Bull'
        if (isBull is False):
            lWord = 'bear'
            uWord = 'Bear'

        userInfo = userAccDict[username]
        stockInfo = userInfo['perStock'][symbol]
        if (stockInfo[lWord + 'ReturnCloseOpen'] > 0):
            result['user' + uWord + 'Return'] += userInfo[lWord + 'ReturnCloseOpen']
            result['user' + uWord + 'ReturnUnique'] += userInfo[lWord + 'ReturnUnique']
            result['stock' + uWord + 'Return'] += stockInfo[lWord + 'ReturnCloseOpen']
            result['stock' + uWord + 'ReturnUnique'] += stockInfo[lWord + 'ReturnUnique']
            result[lWord + 'Count'] += 1
            if (username not in usersTweeted[lWord]):
                usersTweeted[lWord].add(username)
                result['Uuser' + uWord + 'Return'] += userInfo[lWord + 'ReturnCloseOpen']
                result['Uuser' + uWord + 'ReturnUnique'] += userInfo[lWord + 'ReturnUnique']
                result['Ustock' + uWord + 'Return'] += stockInfo[lWord + 'ReturnCloseOpen']
                result['Ustock' + uWord + 'ReturnUnique'] += stockInfo[lWord + 'ReturnUnique']
                result['U' + lWord + 'Count'] += 1

    for start in ['', 'U']:
        for ending in ['Return', 'ReturnUnique']:
            for second in ['user', 'stock']:
                result[start + second + ending + 'Ratio'] = calcRatio(result[second + 'Bull' + ending],
                          result[second + 'Bear' + ending])

    result['countRatio'] = calcRatio(result['bullCount'], result['bearCount'])
    result['UCountRatio'] = calcRatio(result['UbullCount'], result['UbearCount'])
    result['totalLabeledTweetsUsed'] = result['bullCount'] + result['bearCount']
    result['UtotalLabeledTweetsUsed'] = result['UbullCount'] + result['UbearCount']
    return result


# Calculate features based on list of tweets
def calculateSentiment(tweets, symbol, userAccDict):
    usersTweeted = {'bull': set([]), 'bear': set([])}
    result = buildResult()

    for tweet in tweets:
        username = tweet['user']
        isBull = tweet['isBull']
        result['totalLabeledTweets'] += 1
        if (username not in userAccDict or symbol not in userAccDict[username]['perStock']):
            continue

        lWord = 'bull'
        uWord = 'Bull'
        if (isBull is False):
            lWord = 'bear'
            uWord = 'Bear'

        userInfo = userAccDict[username]
        stockInfo = userInfo['perStock'][symbol]
        if (stockInfo[lWord + 'ReturnCloseOpen'] > 0):
            result['user' + uWord + 'Return'] += userInfo[lWord + 'ReturnCloseOpen']
            result['user' + uWord + 'ReturnUnique'] += userInfo[lWord + 'ReturnUnique']
            result['stock' + uWord + 'Return'] += stockInfo[lWord + 'ReturnCloseOpen']
            result['stock' + uWord + 'ReturnUnique'] += stockInfo[lWord + 'ReturnUnique']
            result[lWord + 'Count'] += 1
            if (username not in usersTweeted[lWord]):
                usersTweeted[lWord].add(username)
                result['Uuser' + uWord + 'Return'] += userInfo[lWord + 'ReturnCloseOpen']
                result['Uuser' + uWord + 'ReturnUnique'] += userInfo[lWord + 'ReturnUnique']
                result['Ustock' + uWord + 'Return'] += stockInfo[lWord + 'ReturnCloseOpen']
                result['Ustock' + uWord + 'ReturnUnique'] += stockInfo[lWord + 'ReturnUnique']
                result['U' + lWord + 'Count'] += 1

    for start in ['', 'U']:
        for ending in ['Return', 'ReturnUnique']:
            for second in ['user', 'stock']:
                result[start + second + ending + 'Ratio'] = calcRatio(result[second + 'Bull' + ending],
                          result[second + 'Bear' + ending])

    result['countRatio'] = calcRatio(result['bullCount'], result['bearCount'])
    result['UCountRatio'] = calcRatio(result['UbullCount'], result['UbearCount'])
    result['totalLabeledTweetsUsed'] = result['bullCount'] + result['bearCount']
    result['UtotalLabeledTweetsUsed'] = result['UbullCount'] + result['UbearCount']
    return result


# Close opens from saved file
def setupCloseOpen(dates, stocks, updateObject=False):
    print("Setup Close Open Info")
    path = 'pickledObjects/closeOpen.pkl'
    result = readPickleObject(path)
    if (updateObject is False):
        return result
    else:
        updateAllCloseOpen(stocks, dates)

    result = {}
    for symbol in stocks:
        if (symbol not in result):
            result[symbol] = {}

        cachedCloseOpen = readCachedCloseOpen(symbol)
        for date in dates:
            if (date not in result[symbol]):
                # Check if the date exists in the cached closeOpens
                if (date in cachedCloseOpen):
                    result[symbol][date] = cachedCloseOpen[date]
                    continue

                res = getUpdatedCloseOpen(symbol, date)
                if (res is None):
                    print(date, symbol)
                    continue

                writeCachedCloseOpen(symbol, date, res)
                result[symbol][date] = res

    writePickleObject(path, result)
    return result


# User Infos from saved file
def setupUserInfos(stocks, updateObject=False):
    print("Setup User Info")
    path = 'pickledObjects/userInfos.pkl'
    result = readPickleObject(path)
    if (updateObject is False):
        return result

    result = {}
    for symbol in stocks:
        accuracy = constants['db_user_client'].get_database('user_data_db').new_user_accuracy
        allUsersAccs = accuracy.find({'perStock.' + symbol: {'$exists': True}})
        for user in allUsersAccs:
            if (user['_id'] not in result):
                result[user['_id']] = user

    writePickleObject(path, result)
    return result


# Stock Infos from saved file
def setupStockInfos(stocks, updateObject=False):
    print("Setup Stock Info")
    path = 'pickledObjects/stockInfos.pkl'
    result = readPickleObject(path)
    if (updateObject is False):
        return result

    basicStockInfo = constants['stocktweets_client'].get_database('stocks_data_db').training_stock_info_1216
    result = {}
    for symbol in stocks:
        symbolInfo = basicStockInfo.find_one({'_id': symbol})
        result[symbol] = symbolInfo
    writePickleObject(path, result)
    return result


def setupResults(dates, keys):
    results = {}
    for date in dates:
        results[date] = {}
        results[date]['closeOpen'] = {}
        results[date]['params'] = buildResult()
        for k in results[date]['params']:
            results[date]['params'][k] = {}
        for k in keys:
            results[date]['params'][k] = {}
    return results


def findAllTweets(stocks, dates, updateObject=False, dayPrediction=False):
    print("Setup Tweets")
    path = 'pickledObjects/allTweets.pkl'
    result = readPickleObject(path)
    if (updateObject is False and dayPrediction is False):
        return result

    if (dayPrediction):
        result = {}

    tweetsDB = constants['stocktweets_client'].get_database('tweets_db')
    for symbol in stocks:
        print(symbol)
        if (symbol not in result):
            result[symbol] = {}

        cachedTweets = readCachedTweets(symbol)
        for date in dates:
            d = date.strftime('%m/%d/%Y')
            if (d not in result[symbol]):
                # Check if the date exists in the cached tweets
                if (d in cachedTweets):
                    result[symbol][d] = cachedTweets[d]
                    continue
                result[symbol][d] = []
                dateStart = datetime.datetime(date.year,
                                              date.month, date.day, 9, 30)
                dateEnd = datetime.datetime(date.year,
                                            date.month, date.day, 16, 0)
                query = {"$and": [{'symbol': symbol},
                                  {"$or": [
                                        {'isBull': True},
                                        {'isBull': False}
                                  ]},
                                  {'time': {'$gte': dateStart,
                                            '$lt': dateEnd}}]}
                tweets = list(tweetsDB.tweets.find(query))
                for tweet in tweets:
                    result[symbol][d].append(tweet)

                if (dayPrediction is False):
                    writeCachedTweets(symbol, tweets)

    if (updateObject and dayPrediction is False):
        writePickleObject(path, result)
    return result


def simpleWeightPrediction(date, features, closeOpenInfo, paramWeightings):
    summedDict = {}
    for param in paramWeightings:
        paramWeight = paramWeightings[param]
        if (param == 'numStocks'):
            continue

        for stock in features:
            resultsForDay = features[stock][date][param]
            if (stock not in summedDict):
                summedDict[stock] = 0
            summedDict[stock] += (resultsForDay * paramWeight)

    resPerParam = list(summedDict.items())
    resPerParam.sort(key=lambda x: abs(x[1]), reverse=True)
    resPerParam = resPerParam[:paramWeightings['numStocks']]
    sumDiffs = reduce(lambda a, b: a + b,
                      list(map(lambda x: abs(x[1]), resPerParam)))

    returnToday = 0
    for stockObj in resPerParam:
        stock = stockObj[0]
        stdDev = stockObj[1]
        try:
            closeOpen = closeOpenInfo[stock][date][2]
            returnToday += ((stdDev / sumDiffs) * closeOpen)
        except Exception:
            continue

    try:
        mappedResult = list(map(lambda x: [x[0], 
                            round(x[1] / sumDiffs * 100, 2),
                            closeOpenInfo[x[0]][date][2]],
                            resPerParam))
    except Exception:
        mappedResult = list(map(lambda x: [x[0],
                            round(x[1] / sumDiffs * 100, 2)],
                            resPerParam))
    return (returnToday, mappedResult)


# Basic prediction algo
def basicPrediction(dates, stocks, updateObject=False, dayPrediction=False):
    userInfo = setupUserInfos(stocks)
    stockInfo = setupStockInfos(stocks, True)
    closeOpenInfo = setupCloseOpen(dates, stocks, updateObject)
    allTweets = findAllTweets(stocks, dates, updateObject, dayPrediction)
    features = generateFeatures(dates, stocks, allTweets,
                                stockInfo, userInfo,
                                True, dayPrediction=True)
    symbolReturns = {}
    symbolCounts = {}
    combinedResult = 0
    for date in dates:
        # params = ['numStocks']
        # allPossibilities = []
        # recurse([0] * 1, 0, 6, set([]), allPossibilities)
        # for combo in allPossibilities:
        #     paramWeightings = {'stockReturnUniqueRatio': 1,
        #                        'stockReturnRatio': 2,
        #                        'UCountRatio': 5,
        #                        'UuserReturnRatio': 1,
        #                        'userReturnRatio': 1,
        #                        'UstockReturnRatio': 2,
        #                        'UstockBullReturnUnique': 5,
        #                        'userReturnUniqueRatio': 1,
        #                        'countRatio': 3}
        #     for i in range(len(params)):
        #         paramWeightings[params[i]] = combo[i]

        #     try:
        #         returns = simpleWeightPredictionReturns(date, results, paramWeightings)
        #     except:
        #         continue
        #     if (tuple(paramWeightings.items()) not in combinedResults):
        #         combinedResults[tuple(paramWeightings.items())] = [returns]
        #     else:
        #         combinedResults[tuple(paramWeightings.items())].append(returns)

        paramWeightings = {'stockReturnUniqueRatio': 1,
                            'stockReturnRatio': 2,
                            'UCountRatio': 5,
                            'UuserReturnRatio': 1,
                            'userReturnRatio': 1,
                            'UstockReturnRatio': 2,
                            'UstockBullReturnUnique': 5,
                            'userReturnUniqueRatio': 1,
                            'countRatio': 3,
                            'numStocks': 6}
        returns, listReturns = simpleWeightPrediction(date, features,
                                                      closeOpenInfo,
                                                      paramWeightings)
        print(date, round(returns, 3), listReturns)
        for s in listReturns:
            if (len(s) == 2):
                continue
            symbol = s[0]
            val = 0
            if ((s[1] < 0 and s[2] < 0) or (s[1] > 0 and s[2] > 0)):
                val = abs(s[2])
            else:
                val = -abs(s[2])
            if (symbol not in symbolReturns):
                symbolReturns[symbol] = 0
                symbolCounts[symbol] = {}
                symbolCounts[symbol]['y'] = 0
                symbolCounts[symbol]['x'] = 0

            symbolReturns[symbol] += val
            symbolCounts[symbol]['y'] += 1
            if (val > 0):
                symbolCounts[symbol]['x'] += 1
        combinedResult += returns
    print(combinedResult)

    bestParams = list(symbolReturns.items())
    bestParams.sort(key=lambda x: x[1], reverse=True)
    for x in bestParams:
        print(x)

    otherBest = list(symbolCounts.items())
    otherBest.sort(key=lambda x: x[1]['x'] / x[1]['y'], reverse=True)
    for x in otherBest:
        print(x)

    # bestParams = list(combinedResults.items())
    # bestParams.sort(key=lambda x: sum(x[1]), reverse=True)
    # for x in bestParams[:50]:
    #     print(x[0], sum(x[1]))


def generateFeatures(dates, stocks, allTweets, stockInfo,
                     userInfo, updateObject=False, dayPrediction=False):
    print("Generating Features")
    path = 'pickledObjects/features.pkl'
    if (updateObject is False and dayPrediction is False):
        features = readPickleObject(path)
        return features

    features = {}
    for symbol in stocks:
        print(symbol)
        features[symbol] = {}
        for date in dates:
            if (date.strftime('%m/%d/%Y') not in allTweets[symbol]):
                continue
            features[symbol][date] = {}
            tweets = allTweets[symbol][date.strftime('%m/%d/%Y')]
            print(len(tweets))
            sentiment = calculateSentiment(tweets, symbol, userInfo)
            for param in sentiment:
                paramVal = sentiment[param]
                # print(stockInfo[symbol])
                paramMean = stockInfo[symbol][param]['mean']
                paramStd = stockInfo[symbol][param]['stdev']
                if (stockInfo[symbol][param]['stdev'] == 0.0):
                    features[symbol][date][param] = 0
                    print(param)
                    continue

                stdDev = round((paramVal - paramMean) / paramStd, 2)
                features[symbol][date][param] = stdDev

    if (updateObject):
        writePickleObject(path, features)
    return features


# Updates stock mean and standard deviation
def updateBasicStockInfo(dates, stocks, allTweets):
    basicStockInfo = constants['stocktweets_client'].get_database('stocks_data_db').training_stock_info_1216

    for symbol in stocks:
        accuracy = constants['db_user_client'].get_database('user_data_db').user_accuracy
        allUsersAccs = accuracy.find({'perStock.' + symbol: {'$exists': True}})
        userAccDict = {}
        print(symbol, allUsersAccs.count())
        for user in allUsersAccs:
            userAccDict[user['_id']] = user

        symbolInfo = {'_id': symbol}
        found = basicStockInfo.find_one({'_id': symbol})
        if (found is not None):
            continue

        print(symbol)
        for date in dates:
            if (date.strftime('%m/%d/%Y') not in allTweets[symbol]):
                continue
            tweets = allTweets[symbol][date.strftime('%m/%d/%Y')]
            sentiment = calculateSentiment(tweets, symbol, userAccDict)
            if ('countRatio' not in symbolInfo):
                for k in sentiment:
                    symbolInfo[k] = [sentiment[k]]
            else:
                for k in sentiment:
                    symbolInfo[k].append(sentiment[k])

        for k in symbolInfo:
            if (k != '_id'):
                vals = symbolInfo[k]
                symbolInfo[k] = {}
                symbolInfo[k]['mean'] = statistics.mean(vals)
                symbolInfo[k]['stdev'] = statistics.stdev(vals)
        basicStockInfo.insert_one(symbolInfo)


# Ideal when enough user information collected

# Current weightings for predictions
# 1. Number of stocks to pick from (higher means lower risk)
# 2. Accuracy for that user overall
# 3. Accuracy for that user for that specific stock
# 4. How many predictions this user has made relative to everyone else
# 5. How many predictions this user has made relative to people predicting this stock

# Other weights to add
# 6. Number of likes/comments for a prediction
# 7. Number of followers (If in thousands, remove k and multiply by 1,000)
# 8. How old of a member he/she is

# TODO
# 8. Find weight of a particular sector/industry
