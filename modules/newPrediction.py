import datetime
import statistics
import math
import pickle
import os
import csv
import copy
import json
import time
import matplotlib. pyplot as plt
from scipy.optimize import minimize
from functools import reduce
from .hyperparameters import constants
from .userAnalysis import (getStatsPerUser, initializeResult, updateUserFeatures)
from .stockAnalysis import (findDateString, getTopStocksforWeek, findPageStock, parseStockData, getTopStockDailyCached,
                            updateLastMessageTime, updateLastParsedTime, getTopStocksCached)
from .stockPriceAPI import (findCloseOpenCached, isTradingDay)
from .helpers import (calcRatio, findWeight, readPickleObject, findAllDays, insertResults,
                    readCachedTweets, writeCachedTweets, writePickleObject, sigmoidFn,
                    findTradingDays, findAverageTime, convertToEST, getActualAllStocks)


def parseStock(symbol, date, hours):
    date_string = date.strftime("%Y-%m-%d")
    db = constants['stocktweets_client'].get_database('stocks_data_db')
    (soup, errorMsg, timeElapsed) = findPageStock(symbol, hours)

    if (soup == ''):
        stockError = {'date': date_string, 'symbol': symbol,
                        'error': errorMsg, 'timeElapsed': timeElapsed}
        db.stock_tweets_errors.insert_one(stockError)
        return

    try:
        result = parseStockData(symbol, soup)
    except Exception as e:
        stockError = {'date': date_string, 'symbol': symbol,
                        'error': str(e), 'timeElapsed': -1}
        db.stock_tweets_errors.insert_one(stockError)
        print(e)
        return

    if (len(result) == 0):
        stockError = {'date': date_string, 'symbol': symbol,
                        'error': 'Result length is 0??', 'timeElapsed': -1}
        db.stock_tweets_errors.insert_one(stockError)
        print(stockError)
        return

    results = updateLastMessageTime(db, symbol, result)

    # No new messages
    if (len(results) != 0):
        insertResults(results)

    updateLastParsedTime(db, symbol)



def dailyPrediction(date):
    daily_object = readPickleObject('newPickled/daily_stocks_cached.pickle')
    stocks = getTopStockDailyCached(date, 80, daily_object)
    last_parsed = constants['stocktweets_client'].get_database('stocks_data_db').last_parsed

    for symbol in stocks:
        cursor = last_parsed.find_one({'_id': symbol})
        if (cursor == None):
            print(symbol)
            continue
        last_time = cursor['time']
        hours_back = (convertToEST(datetime.datetime.now()) - last_time).total_seconds() / 3600.0
        print(symbol, round(hours_back, 1))
        # if (hours_back > 0.5):
        #     parseStock(symbol, curr_time, hours_back)


    # for symbol in stocks:
    #     writeTweets(date, date, symbol, overwrite=True)


def optimizeFN(params):
    weightings = {
        'bull_w': params[0],
        'bear_w': params[1],
        'bull_w_return': params[2],
        'bear_w_return': params[3],
    }
    start_date = datetime.datetime(2019, 12, 1, 15, 30)
    end_date = datetime.datetime(2020, 7, 1, 9, 30)
    path = 'newPickled/stock_features.pkl'
    num_top_stocks = 25
    all_features = findFeatures(start_date, end_date, num_top_stocks, path, False)
    result = prediction(start_date, end_date, all_features, num_top_stocks, weightings, False)
    param_res = list(map(lambda x: round(x, 2), params))
    print(param_res, result)
    return -result


def optimizeParams():
    params = {
        'bull_w': [1, (0, 5)],
        'bear_w': [1, (0, 5)],
        'bull_w_return': [1, (0, 3)],
        'bear_w_return': [1, (0, 3)],
    }

    initial_values = list(map(lambda key: params[key][0], list(params.keys())))
    bounds = list(map(lambda key: params[key][1], list(params.keys())))
    result = minimize(optimizeFN, initial_values, method='SLSQP', options={'maxiter': 100, 'eps': 0.2}, 
                    bounds=(bounds[0],bounds[1],bounds[2],bounds[3]))
    print(result)


# Find all usernames from folder
def findUserList():
    users = []
    arr = os.listdir('user_tweets_new/')
    for u in arr:
        username = u[:-4]
        users.append(username)
    users.sort()
    return users


# Find all usernames from folder
def findValidUsers():
    users = []
    arr = os.listdir('user_pickle_files_new/')
    for u in arr:
        username = u[:-4]
        users.append(username)
    users.sort()
    return users


# Whether to keep a user based on minimum criteria
def cutoffUser(user_info):
    num_tweets_bull = user_info['num_predictions']['bull']
    num_tweets_bear = user_info['num_predictions']['bear']

    # Filter by number of tweets
    if (max(num_tweets_bull, num_tweets_bear) < 20):
        return False

    if (num_tweets_bull == 0):
        num_tweets_bull = 1
    if (num_tweets_bear == 0):
        num_tweets_bear = 1

    correct_tweets_bull = user_info['correct_predictions']['bull']
    correct_tweets_bear = user_info['correct_predictions']['bear']

    accuracy_bull = correct_tweets_bull / num_tweets_bull
    accuracy_bear = correct_tweets_bear / num_tweets_bear
    if (max(accuracy_bull, accuracy_bear) < 0.5): # Filter by number of accuracy
        return False

    bull_return = user_info['return']['bull']
    bear_return = user_info['return']['bear']
    if (max(bull_return, bear_return) < 1): # Filter by return
        return False

    return True


# Generate features from users historical tweets
# Return stock specific user features and general user features
def pregenerateUserFeatures(username, mode):
    day_increment = datetime.timedelta(days=1)
    cached_tweets = cachedUserTweets(username) # Tweets from user
    if (cached_tweets == None):
        return {'general': {}}

    dates = set([])
    # Extract the unique dates that the user tweeted
    for tweet in cached_tweets:
        time = tweet['time']

        # Find the trading day the tweet corresponds to
        if (mode == 3):
            if (time.hour >= 9 and time.minute >= 30):
                time += day_increment
        else:
            if (time.hour >= 16):
                time += day_increment

        while (isTradingDay(time) == False):
            time += day_increment

        time = datetime.datetime(time.year, time.month, time.day, 16)
        if (mode == 3):
            time = datetime.datetime(time.year, time.month, time.day, 9, 30)
        if (time not in dates):
            dates.add(time)

    # Go from past to present
    dates = sorted(list(dates))
    result_general = {}
    result_perstock = {}
    prev_day = {}

    user_features = initializeUserFeatures() # initialize user features for first time
    user_features['last_updated'] = dates[0] - datetime.timedelta(days=5)

    for date in dates:
        calculateUserFeatures(date, user_features, cached_tweets, mode)
        if (cutoffUser(user_features) == False):
            continue

        copied_res = copy.deepcopy(user_features)
        del copied_res['last_updated'] # Don't check for last updated time in equality
        if (prev_day == copied_res):
            continue
        prev_day = copied_res

        # Store as user features at next trading day
        date += day_increment
        while (isTradingDay(date) == False):
            date += day_increment
        date_string = '%d-%02d-%02d' % (date.year, date.month, date.day)

        per_stock = copied_res['perStock']
        for symbol in per_stock:
            if (symbol not in result_perstock):
                result_perstock[symbol] = {}
                result_perstock[symbol][date_string] = per_stock[symbol]
                continue

            prev_dates = sorted(result_perstock[symbol].keys(), reverse=True)
            last_date = prev_dates[0]
            if (result_perstock[symbol][last_date] != per_stock[symbol]):
                result_perstock[symbol][date_string] = per_stock[symbol]

        del copied_res['perStock']
        result_general[date_string] = copied_res

    return {'general': result_general, 'per_stock': result_perstock}

# Pregenerate all user features based off tweets
# Extract GENERAL and STOCK specific user return, accuracy, tweet count, etc.
def pregenerateAllUserFeatures(update, path, mode=1):
    if (update == False):
        result = readPickleObject(path)
        return result

    users = findUserList() # Based off of users in the user_tweets/ folder
    print(len(users))
    result = {}
    not_found = 0
    cutoff_date = '2019-06-01'
    for i in range(len(users)):
        if (i % 1000 == 0): # Log progress
            print(not_found)
            print(i)

        username = users[i]
        pregenerated = pregenerateUserFeatures(username, mode) # Find user features

        # If no dates/features were found or doesn't meet minimum user requirements
        if (len(pregenerated['general']) == 0):
            not_found += 1
            continue

        # 1. Remove unnecessary data from users before a given date
        prev_dates = sorted(list(pregenerated['general'].keys()))
        last_date_feature = None
        last_date = prev_dates[0]
        for date in prev_dates:
            if (date < cutoff_date): # Temp cutoff for dates not to keep
                last_date_feature = pregenerated['general'][date]
                last_date = date
                del pregenerated['general'][date]

        # If all dates deleted, use the latest date/feature
        if (len(pregenerated['general']) == 0):
            pregenerated['general_dates'] = [last_date]
            pregenerated['general'][last_date] = last_date_feature
        else: # Sorted from most recent to most historical
            all_general_dates = sorted(list(pregenerated['general'].keys()), reverse=True)
            pregenerated['general_dates'] = all_general_dates


        # 2. Remove unnecessary data from stocks based on cutoff date
        for symbol in pregenerated['per_stock']:
            stock_dates = sorted(list(pregenerated['per_stock'][symbol].keys()))
            last_date_feature = None
            last_date = stock_dates[0]
            for date_str in stock_dates:
                if (date_str < cutoff_date):
                    last_date_feature = pregenerated['per_stock'][symbol][date_str]
                    last_date = date
                    del pregenerated['per_stock'][symbol][date_str]

            # If all dates deleted, use the latest date/feature
            if (len(pregenerated['per_stock'][symbol]) == 0):
                pregenerated['per_stock'][symbol][last_date] = last_date_feature

        result[username] = pregenerated

    writePickleObject(path, result)
    return result



# Find average stock count over d trading days back
def findStockCounts(all_features, days_back):
    stock_counts = {}
    all_dates = sorted(list(all_features.keys()))
    for i in range(len(all_dates)):
        date_string = all_dates[i]
        stock_counts[date_string] = {}
        for s in all_features[date_string]:
            total_count = 0
            index = i
            total_bull = 0
            total_bear = 0
            # Add all stock counts d trading days before the current day and find average count
            while (index >= 0 and total_count < days_back):
                new_date_string = all_dates[index]
                if (s in all_features[new_date_string]):
                    total_bull += all_features[new_date_string][s]['bull_count']
                    total_bear += all_features[new_date_string][s]['bear_count']
                    total_count += 1
                index -= 1
            stock_counts[date_string][s] = {
                'bull_count': total_bull / total_count,
                'bear_count': total_bear / total_count
            }
    return stock_counts


# Standardize all features by average stock count for bull/bear
def editFeatures(start_date, end_date, all_features, weights, stock_counts):
    data = []
    data1 = []
    for d in all_features:
        day_res = []
        for s in all_features[d]:
            # standardize all features before using
            result = all_features[d][s]
            bull_count = all_features[d][s]['bull_count']
            bear_count = all_features[d][s]['bear_count']
            # print(d, s, result['bull_w'], result['bear_w'], bull_count, bear_count)
            for f in all_features[d][s]:
                weights['day_weight'] = 1.2
                weights['stock_weight'] = 0.95
                if ('bull' in f):
                    if (stock_counts[d][s]['bull_count'] == 0 or bull_count == 0):
                        continue
                    day_weight = weights['day_weight'] * bull_count
                    stock_weight = weights['stock_weight'] * stock_counts[d][s]['bull_count']
                    result[f] /= ((day_weight + stock_weight) / (weights['day_weight'] + weights['stock_weight']))
                else:
                    if (stock_counts[d][s]['bear_count'] == 0 or bear_count == 0):
                        continue
                    day_weight = weights['day_weight'] * bear_count
                    stock_weight = weights['stock_weight'] * stock_counts[d][s]['bear_count']
                    result[f] /= ((day_weight + stock_weight) / (weights['day_weight'] + weights['stock_weight']))

            # print(s, d, result['bull_w'], result['bear_w'], bull_count, bear_count)
            day_res.append((s, round(result['bull_w'], 2), round(result['bear_w'], 2), bull_count, bear_count))
            # if (s == 'IBIO'):
            #     data.append(result['bull_w'])
            #     data1.append(d)

            # result['count_ratio'] = calcRatio(result['bull'], result['bear'])

            # Make all bear features negative
            for f in all_features[d][s]:
                if ('bear' in f):
                    all_features[d][s][f] = -all_features[d][s][f]
        day_res.sort(key=lambda x: abs(x[1] - (0.9 * x[2])), reverse=True)
        print(d, day_res[:5])
        # day_res.sort(key=lambda x: x[1] - (1.7 * x[2]))
        # print(d, day_res[:5])

    # fig, axs = plt.subplots(2)
    # res_check = []
    # for i in range(30, len(data1)):
    #     res_check.append((round(data[i], 2), data1[i]))
    
    # print(res_check)
    # print(data1[230:])
    # print(data[230:])
    # plt.plot(data[30:])
    # plt.show()
    # print(data1)
    # axs[0].hist(data, density=False, bins=150)
    # axs[1].hist(data1, density=False, bins=150)
    # plt.show()
    return all_features


def calculateReturn(date, daily_features, choose_top_n, accuracies):
    # cached closeopen prices
    cached_prices = constants['cached_prices']

    stock_weightings = list(daily_features.items())
    stock_weightings.sort(key=lambda x: abs(x[1]), reverse=True)
    stock_weightings = stock_weightings[:choose_top_n]
    sum_weights = reduce(lambda a, b: a + b, list(map(lambda x: abs(x[1]), stock_weightings)))
    if (sum_weights == 0):
        return(0, [])

    return_today = 0
    selected_stocks = []
    for stock_obj in stock_weightings:
        symbol = stock_obj[0]
        weighting = stock_obj[1]
        close_open = findCloseOpenCached(symbol, date, cached_prices)
        # Make sure close opens are always updated
        if (close_open == None):
            selected_stocks.append([symbol, round(weighting / sum_weights * 100, 2)])
            continue

        percent_change = close_open[2]
        percent_weight = (weighting / sum_weights)
        return_today += (percent_weight * percent_change)

        selected_stocks.append([symbol, round(weighting / sum_weights * 100, 2), round(percent_change, 2)])

        if (symbol not in accuracies):
            accuracies[symbol] = {}
            accuracies[symbol]['correct'] = 0
            accuracies[symbol]['total'] = 0
        
        if ((close_open[2] < 0 and stock_obj[1] < 0) or (stock_obj[1] > 0 and close_open[2] > 0)):
            accuracies[symbol]['correct'] += 1
        accuracies[symbol]['total'] += 1

    return (return_today, selected_stocks)



# Make prediction by chooosing top n stocks to buy per day
# Features are generated before hand per stock per day
def prediction(start_date, end_date, all_features, num_top_stocks, weightings, print_info):

    # Find counts of bear/bull per stock averaged over last n number of trading days
    stock_counts = findStockCounts(all_features, 5)

    # Standardize all features by their historical counts
    all_features = editFeatures(start_date, end_date, all_features, weightings, stock_counts)

    # trading days 
    dates = findTradingDays(start_date, end_date)
    accuracies = {}
    total_return = 0
    strong_return = 0
    strong_correct = 0
    strong_total = 0
    negative_correct = 0
    negative_total = 0
    negative_return = 0
    positive_correct = 0
    positive_total = 0
    positive_return = 0
    positive_days = 0
    cash = 1000

    # Find top n stock features for each day 
    for date in dates:
        daily_features = {}
        date_string = date.strftime("%Y-%m-%d")

        # Find features for each stock
        for symbol in all_features[date_string]:
            stock_features = all_features[date_string][symbol]
            stock_count = stock_counts[date_string][symbol]['bull_count'] + stock_counts[date_string][symbol]['bear_count'] + 90
            stock_count_weight = math.log10(stock_count)

            # Weight each feature based on weight param
            result_weight = 0
            total_weight = 0
            for w in weightings:
                if (w == 'day_weight' or w == 'stock_weight'):
                    continue
                result_weight += (stock_count_weight * weightings[w] * stock_features[w])
                total_weight += weightings[w]
            daily_features[symbol] = result_weight / total_weight

        # Find percent of each stock to buy (pick top x)
        choose_top_n = 3
        (return_today, selected_stocks) = calculateReturn(date, daily_features, choose_top_n, accuracies)
        total_return += return_today
        cash *= (1 + (return_today / 100))

        if (return_today > 0):
            positive_days += 1

        # Print stocks that are picked
        if (print_info):
            if (return_today == 0):
                print(date, selected_stocks)
                continue
            print(date_string, cash, return_today, selected_stocks)
            # for s in selected_stocks:
            #     if (s[1] < 0):
            #         if (s[2] < 0):
            #             negative_correct += 1
            #             negative_return += abs(s[2])
            #         else:
            #             negative_return -= abs(s[2])
            #         negative_total += 1
            #     if (s[1] > 0):
            #         if (s[2] > 0):
            #             positive_correct += 1
            #             positive_return += abs(s[2])
            #         else:
            #             positive_return -= abs(s[2])
            #         positive_total += 1
            # if (abs(selected_stocks[0][1]) > 80):
            #     print(selected_stocks)
            #     val = -1 if selected_stocks[0][1] < 0 else 1
            #     ret = val * selected_stocks[0][2]
            #     if (ret >= 0):
            #         strong_correct += 1
            #     strong_total += 1
            #     strong_return += ret

    total_correct = 0
    total_total = 0
    for s in accuracies:
        total_correct += accuracies[s]['correct']
        total_total += accuracies[s]['total']
        if (print_info):
            print(s, accuracies[s]['correct'], accuracies[s]['total'])

    if (print_info):
        if (total_total > 0):
            print(strong_correct, strong_total, strong_return, ' ', negative_correct, negative_total, negative_return, ' ', positive_correct, positive_total, positive_return)
            print(total_correct/total_total, total_return, cash, positive_days / len(dates))
    print(round(total_correct/total_total, 2), round(positive_days / len(dates), 2), total_correct, total_total, total_return)
    return total_return
    return total_correct/total_total



# Find features of tweets per day of each stock
# INVARIANT: user feature are built up as time increases (TIME MUST ALWAYS INCREASE)
# ^^ Done to reduce calls to close open / unecessary calculations
def findFeatures(start_date, end_date, num_top_stocks, path, update=False):
    if (update == False):
        return readPickleObject(path)

    dates = findTradingDays(start_date, end_date)
    all_stock_tweets = {} # store tweets locally for each stock
    all_user_features = readPickleObject('newPickled/user_features.pickle')
    cached_stockcounts = readPickleObject('newPickled/stock_counts_14.pkl')
    feature_stats = {} # Avg/Std for features perstock
    result = {}
    preprocessed_user_features = {}

    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        result[date_str] = {}
        found = 0
        stocks = getTopStocksCached(date, num_top_stocks, cached_stockcounts) # top stocks for the week
        for symbol in stocks:
            tweets_per_stock = {}
            if (symbol not in all_stock_tweets):
                stock_path = 'stock_files/' + symbol + '.pkl'
                tweets_per_stock = readPickleObject(stock_path)
                all_stock_tweets[symbol] = tweets_per_stock
            else:
                tweets_per_stock = all_stock_tweets[symbol]
            tweets = findTweets(date, tweets_per_stock, symbol) # Find tweets used for predicting for this date

            # ignore all stock with less than 200 tweets
            if (len(tweets) < 100):
                continue
            found += 1
            features = stockFeatures(tweets, date_str, symbol, all_user_features, feature_stats, preprocessed_user_features) # calc features based on tweets/day
            result[date_str][symbol] = features
        print(date_str, found)

    writePickleObject('newPickled/preprocessed_user_features.pickle', preprocessed_user_features)
    writePickleObject(path, result)
    return result


# Find top stocks given the date (updated per week)
# Use those stocks to find features based on tweets from those day
# date_str_1 = datetime.datetime(2020, 6, 24, 9, 30).strftime("%Y-%m-%d")
# date_str_2 = datetime.datetime(2020, 6, 25, 9, 30).strftime("%Y-%m-%d")
# del all_features[date_str_1]
# del all_features[date_str_2]

def modifyTweets():
    stocks = []
    stocks = os.listdir('stock_files/')
    for symbol_path in stocks:
        print(symbol_path)
        if (symbol_path[-3:] != 'pkl'):
            continue
        path = 'stock_files/' + symbol_path
        tweets_per_stock = readPickleObject(path)
        for date in tweets_per_stock:
            tweets = tweets_per_stock[date]
            new_tweets = list(map(lambda t: {'user': t['user'], 'time': t['time'], 'w': findWeight(t['time'], 'log(x)'), 'isBull': t['isBull']}, tweets))
            new_tweets.sort(key=lambda tweet: tweet['time'], reverse=True)
            tweets_per_stock[date] = new_tweets
        writePickleObject(path, tweets_per_stock)


# Find all tweets on this given day from database
def findTweets(date, tweets_per_stock, symbol, mode=1):
    # Find start end and end dates for the given date
    day_increment = datetime.timedelta(days=1)
    date_end = datetime.datetime(date.year, date.month, date.day, 16)
    if (mode == 3):
        date_end = datetime.datetime(date.year, date.month, date.day, 9, 30)
    date_start = date_end - day_increment
    dates = [date_end, date_start]
    while (isTradingDay(date_start) == False):
        date_start -= day_increment
        dates.append(date_start)

    tweets = []
    for date in dates:
        date_string = date.strftime("%Y-%m-%d")
        # Why would this happen ??
        if (date_string not in tweets_per_stock):
            print(date_string, symbol, "fetching tweets")
            path = 'stock_files/' + symbol + '.pkl'
            tweets_per_stock = readPickleObject(path)

            # Find all tweets for the given day
            date_start = datetime.datetime(date.year, date.month, date.day, 0, 0)
            date_end = datetime.datetime(date.year, date.month, date.day) + day_increment
            fetched_tweets = fetchTweets(date_start, date_end, symbol)
            tweets_per_stock[date_string] = fetched_tweets
            tweets.extend(fetched_tweets)

            # Write to the stock pickled object
            writePickleObject(path, tweets_per_stock)
            continue
        found_tweets = tweets_per_stock[date_string]
        tweets.extend(found_tweets)

    start_index = len(tweets) - 1
    end_index = 0
    found_start = False
    found_end = False
    for i in range(len(tweets)):
        tweet_time = tweets[i]['time']
        if (found_end == False and tweet_time <= date_end):
            end_index = i
            found_end = True

        if (found_start == False and tweet_time <= date_start):
            start_index = i
            found_start = True

    return tweets[end_index:start_index]


# Averages and std for features per stock
def findAverageStd(start_date, end_date, all_features):
    # Setup result to have list of features per stock
    # Loop through each date and find feature per stock
    per_stock_features = {}
    for date_str in all_features:
        for symbol in all_features[date_str]:
            if (symbol not in per_stock_features):
                per_stock_features[symbol] = {}
                for f in all_features[date_str][symbol]:
                    per_stock_features[symbol][f] = []
            for f in all_features[date_str][symbol]:
                stock_feature = all_features[date_str][symbol][f]
                per_stock_features[symbol][f].append(stock_feature)

    # Find avg/std for all stocks
    result = {}
    for symbol in per_stock_features:
        features = per_stock_features[symbol]
        result[symbol] = {}
        for f in features:
            # Edge case 1
            if (len(features[f]) == 1):
                res = {
                    'std': 1,
                    'avg': statistics.mean(features[f])
                }
                result[symbol][f] = res
                continue
            # Edge case 2
            if (statistics.mean(features[f]) == 0):
                res = {
                    'std': 1,
                    'avg': 0
                }
                result[symbol][f] = res
                continue
            res = {
                'std': statistics.stdev(features[f]),
                'avg': statistics.mean(features[f])
            }
            result[symbol][f] = res

    return result


# Save user tweets locally (only save symbol, time, isBull)
def saveUserTweets():
    print("Saving all user tweets")
    analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
    time = datetime.datetime(2020, 6, 1)
    query = {"$and": [{'error': ''}, 
                      {'last_updated': {'$exists': True}},
                      {'last_updated': {'$gte': time}}]}
    cursor = analyzedUsers.find(query)
    users = list(map(lambda document: document['_id'], cursor))
    print(len(users))
    count = 0

    for username in users:
        count += 1
        if (count % 1000 == 0): # log progress
            print(count)
        path = 'user_tweets_new/' + username + '.csv'
        if (os.path.exists(path)):
            continue

        tweets_collection = constants['stocktweets_client'].get_database('tweets_db').tweets
        query = {'$and': [{'user': username}, { "$or": [{'isBull': True}, {'isBull': False}] }]}
        tweets = list(tweets_collection.find(query).sort('time', -1))
        tweets = list(map(lambda t: [t['time'], t['symbol'], t['isBull']], tweets))
        if (len(tweets) < 20):
            continue

        with open(path, "a") as user_file:
            csvWriter = csv.writer(user_file, delimiter=',')
            csvWriter.writerows(tweets)


def editCachedTweets(username):
    path = 'user_tweets/' + username + '.csv'
    if (os.path.exists(path) == False):
        return None

    with open(path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        result = []
        for row in csv_reader:
            if (len(row) == 0):
                continue
            date_string = row[0][:19]
            (year, month, day) = (int(date_string[:4]), int(date_string[5:7]), int(date_string[8:10]))
            (hour, minute, second) = (int(date_string[11:13]), int(date_string[14:16]), int(date_string[17:19]))
            date_parsed = datetime.datetime(year, month, day, hour, minute, second)
            is_bull = True if (row[2] == 'True') else False
            tweet = {'time': date_parsed, 
                    'isBull': is_bull,
                    'symbol': row[1]}
            result.append(tweet)
    
        tweets = list(map(lambda t: [t['time'], t['symbol'], t['isBull']], result))
        with open(path, "w") as user_file:
            csvWriter = csv.writer(user_file, delimiter=',')
            csvWriter.writerows(tweets)


# Fetch user tweets from local disk
def cachedUserTweets(username):
    path = 'user_tweets_new/' + username + '.csv'
    if (os.path.exists(path) == False):
        return None

    with open(path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        result = []
        for row in csv_reader:
            date_string = row[0][:19]
            (year, month, day) = (int(date_string[:4]), int(date_string[5:7]), int(date_string[8:10]))
            (hour, minute, second) = (int(date_string[11:13]), int(date_string[14:16]), int(date_string[17:19]))
            date_parsed = datetime.datetime(year, month, day, hour, minute, second)
            is_bull = True if (row[2] == 'True') else False
            tweet = {'time': date_parsed, 
                    'isBull': is_bull,
                    'symbol': row[1]}
            result.append(tweet)
    return result


# Initialize user features 
def initializeUserFeatures():
    result = {}
    features = ['correct_predictions', 'num_predictions', 'return', 'return_log', 'return_w']
    for f in features:
        result[f] = {}
        result[f]['bull'] = 0
        result[f]['bear'] = 0

    result['perStock'] = {}
    return result


# Calculate user's features based on tweets before this date
# Loop through all tweets made by user and feature extract per user
def calculateUserFeatures(date, user_features, tweets, mode):
    unique_stocks = {} # Keep track of unique tweets per day/stock
    last_updated = user_features['last_updated'] # last time that was parsed
    for tweet in tweets: # Filter by tweets before the current date and after last updated date
        if (tweet['time'] >= last_updated and tweet['time'] < date and tweet['symbol'] in constants['good_stocks']):
            updateUserFeatures(user_features, tweet, unique_stocks, mode)

    # Update unique predictions per day features
    for time_string in unique_stocks:
        w = unique_stocks[time_string]['w'] # weighted based on time of tweet
        symbol = unique_stocks[time_string]['symbol']

        # Find whether tweet was bull or bear based on last tweet prediction
        label = 'bull' if unique_stocks[time_string]['last_prediction'] else 'bear'

        percent_change = unique_stocks[time_string]['percent_change']
        correct_prediction = (label == 'bull' and percent_change >= 0) or (label == 'bear' and percent_change <= 0)
        correct_prediction_num = 1 if correct_prediction else 0
        percent_return = abs(percent_change) if correct_prediction else -abs(percent_change)

        # return unique (log) Weighted by number of times posted that day
        total_weight = unique_stocks[time_string]['total_weight']
        return_log = percent_return * (math.log10(total_weight) + 1)

        # Update general
        user_features['correct_predictions'][label] += correct_prediction_num
        user_features['num_predictions'][label] += 1
        user_features['return'][label] += percent_return
        user_features['return_w'][label] += (w * percent_return)
        user_features['return_log'][label] += return_log

        # Update per stock
        user_features['perStock'][symbol]['correct_predictions'][label] += correct_prediction_num
        user_features['perStock'][symbol]['num_predictions'][label] += 1
        user_features['perStock'][symbol]['return'][label] += percent_return
        user_features['perStock'][symbol]['return_w'][label] += (w * percent_return)
        user_features['perStock'][symbol]['return_log'][label] += return_log

    user_features['last_updated'] = date # update time it was parsed so dont have to reparse


# Finds tweets for the given date range and stores them locally to be cached
def writeTweets(start_date, end_date, symbol, overwrite=False):
    # print("Setting up tweets")
    day_increment = datetime.timedelta(days=1)
    all_dates = findAllDays(start_date, end_date)
    path = 'stock_files/' + symbol + '.pkl'
    tweets_per_stock = readPickleObject(path)
    new_tweets = False

    # Find stocks to parse per day
    for date in all_dates:
        date_string = date.strftime("%Y-%m-%d")
        if (overwrite == False and date_string in tweets_per_stock):
            print(symbol, date_string, len(tweets_per_stock[date_string]), "EXISTS")
            continue

        # Find all tweets for the given day
        date_start = datetime.datetime(date.year, date.month, date.day, 0, 0)
        date_end = datetime.datetime(date.year, date.month, date.day) + day_increment
        tweets = fetchTweets(date_start, date_end, symbol)
        tweets_per_stock[date_string] = tweets
        new_tweets = True

        print(symbol, date_string, len(tweets_per_stock[date_string]))

    # Write to the stock pickled object
    # Only write if it is updated
    if (new_tweets):
        writePickleObject(path, tweets_per_stock)

# Fetch tweets from mongodb tweets collection
def fetchTweets(date_start, date_end, symbol):
    tweets_collection = constants['stocktweets_client'].get_database('tweets_db').tweets
    query = {"$and": [{'symbol': symbol},
                        {"$or": [
                                {'isBull': True},
                                {'isBull': False}
                        ]},
                        {'time': {'$gte': date_start,
                                    '$lt': date_end}}]}
    tweets = list(tweets_collection.find(query))
    tweets = list(map(lambda t: {'user': t['user'], 'time': t['time'], 'w': findWeight(t['time'], 'log(x)'), 'isBull': t['isBull']}, tweets))
    tweets.sort(key=lambda tweet: tweet['time'], reverse=True)
    return tweets


def buildStockFeatures():
    result = {}
    labels = ['bull', 'bear', 'bull_w', 'bear_w']
    features = ['return', 'return_w1', 'return_log', 'return_s', 'return_w1_s', 'return_log_s']
    for l in labels:
        result[l] = 0
        for f in features:
            result[l + '_' + f] = 0
    return result



# Retrieve cached pregenerated user features
def newCalculateUserFeatures(symbol, date, features):
    result = {} # Find general stats
    general_features = features['general']
    general_dates = features['general_dates']
    curr_date_str = '%d-%02d-%02d' % (date.year, date.month, date.day)
    for date_str in general_dates: # Find first date feature that is less than the current date
        if (date_str <= curr_date_str):
            result = general_features[date_str]
            break

    # If no user info found up till this date, return None
    if (len(result.keys()) == 0):
        return None

    # Find stock specific stats
    stock_features = features['per_stock']
    result[symbol] = {}
    if (symbol not in stock_features): # First time tweeting about stock so no data yet
        return result

    stock_dates = sorted(stock_features[symbol].keys(), reverse=True)
    for date_str in stock_dates:
        # if not found, also first time tweeting about stock so no data yet
        if (date_str <= curr_date_str):
            result[symbol] = stock_features[symbol][date_str]
            break

    return result


def officialCutOff(user_info, symbol, label):
    accuracy_unique = findFeature(user_info, '', 'accuracy', label)
    accuracy_unique_s = findFeature(user_info, symbol, 'accuracy', None)

    # Filter by accuracy
    if (accuracy_unique < 0.5 or accuracy_unique_s < 0.5):
        return None

    num_tweets_unique = user_info['unique_num_predictions']['bull'] + user_info['unique_num_predictions']['bear']
    num_tweets_s_unique = findFeature(user_info, symbol, 'unique_num_predictions', None)

    # Filter by number of tweets
    if (num_tweets_unique <= 20 or num_tweets_s_unique < 10):
        return None

    return_unique = (user_info['unique_return']['bear'] + user_info['unique_return']['bull']) / 2
    return_unique_s = findFeature(user_info, symbol, 'unique_return', None) / 2
    return_unique -= return_unique_s # Ignore the current stock's return

    # Filter by return
    if (return_unique < 15 or return_unique_s < 5):
        return None

    return copy.deepcopy(user_info)



# Return feature parameters based on tweets for a given trading day/s
# Builds user features as more information is seen about that user
def stockFeatures(tweets, date_str, symbol, all_user_features, feature_stats, preprocessed_user_features):
    seen_users = {}

    # STEP 1 : Find all last predictions and counts
    # Assume tweets sorted from new to old
    for tweet in tweets:
        username = tweet['user']
        if (username not in all_user_features): # Don't analyze if not an expert user
            continue
        isBull = tweet['isBull']
        tweeted_date = tweet['time']
        if (username in seen_users): # Only look at the most recent prediction by user
            # If previous prediction was the same as last prediction, add to weighting
            prev_prediction = seen_users[username]['isBull']
            if (isBull == prev_prediction):
                seen_users[username]['times'].append(tweeted_date)
            continue
        seen_users[username] = {
            'time': tweeted_date,
            'times': [tweeted_date],
            'isBull': isBull
        }


    # STEP 2 : Look at all unique predictions and their counts
    for username in seen_users:
        tweeted_date = seen_users[username]['time']

        # Find user features (return, accuracy, etc.) before tweeted date
        user_features = all_user_features[username]
        user_info = newCalculateUserFeatures(symbol, tweeted_date, user_features)
        if (user_info == None):
            continue

        # Append all user features to list
        user_info['prediction'] = seen_users[username]['isBull']
        user_info['times'] = seen_users[username]['times']
        preprocessed_user_features[symbol][date_str][username] = user_info



##
# All per stocks featuers are weighted by (x(1 + tweets per stock))
##

# unique accuracy (0 - 1) x return per stock (0 - 1) x number of tweets = if - - make negative
# unique accuracy x return x number of tweets = if - - make negative

# unique return per stock = -150 - 150 -> -1 - 1
# unique return = -150 - 150 -> -1 - 1

# accuracy per stock with # tweets = accuracy * # min number of tweets per stock 
# accuracy in general with # tweets =  accuracy * # min number of tweets 

# unique accuracy per stock = 0 - 1 -> -1 - 1
# unique accuracy in general = 0 - 1 -> -1 - 1

# min number of tweets per stock (0) = log(# tweets) -> 1 - 100 -> 0 - 2 -> 0 - 1 
# min number of tweets (bull/bear) in general (75) = log(# tweets) -> 75 - 600 -> 2 - 4 -> 0 - 1

# negative weight for below accuracy

# Return a number based on how reliable the users prediction is (0 - 1)
# TODO: Ideally use features such as join date, follower following ratio etc
# TODO: instead of log, use distribution of the data
# TODO: use return_uniquelog instead of returnUnique

def weightedUserPrediction(user_values, feature_avg_std):
    num_tweets = user_values['num_tweets']
    num_tweets_s = user_values['num_tweets_s']

    # (1) Scale Tweet Number
    max_value = feature_avg_std['num_tweets']['avg'] + (3 * feature_avg_std['num_tweets']['std'])
    scaled_num_tweets = (num_tweets) / math.log10(max_value)
    scaled_num_tweets = (scaled_num_tweets / 1.5) + 0.33

    scaled_num_tweets_s = math.log10(num_tweets_s) / math.log10(200) # Should be based off of stocks user distribution
    if (scaled_num_tweets > 1):
        scaled_num_tweets = 1
    if (scaled_num_tweets_s > 1):
        scaled_num_tweets_s = 1


    # (2) Scale user returns
    return_unique = user_values['return_unique']
    return_unique_s = user_values['return_unique_s']

    max_value = feature_avg_std['return_unique']['avg'] + (3 * feature_avg_std['return_unique']['std'])
    scaled_return_unique = (math.log10(return_unique - 4)) / math.log10(max_value)
    scaled_return_unique = (scaled_return_unique / 1.5) + 0.33

    max_value = feature_avg_std['return_unique_s']['avg'] + (3 * feature_avg_std['return_unique_s']['std'])
    scaled_return_unique_s = (math.log10(return_unique_s - 4)) / math.log10(max_value)
    scaled_return_unique_s = (scaled_return_unique_s / 1.5) + 0.33

    if (scaled_return_unique > 1):
        scaled_return_unique = 1
    if (scaled_return_unique_s > 1):
        scaled_return_unique_s = 1

    # (3) all features combined (scale accuracy from 0.5 - 1 to between 0.7 - 1.2)
    accuracy_unique = user_values['accuracy_unique'] + 0.2
    accuracy_unique_s = user_values['accuracy_unique_s'] + 0.2

    all_features = accuracy_unique * scaled_num_tweets * scaled_return_unique
    all_features_s = 2 * accuracy_unique_s * scaled_num_tweets_s * scaled_return_unique_s

    # return (scaled_num_tweets + scaled_num_tweets_s + scaled_return_unique +
    #         scaled_return_unique_s + all_features + all_features_s) / 8
    return (scaled_return_unique + scaled_num_tweets + scaled_return_unique_s + (2 * all_features)) / 5


# Find feature for given user based on symbol and feature name
def findFeature(feature_info, symbol, feature_name, bull_bear):
    # If finding stock specific feature, check if data exists, else just use general data
    if (symbol in feature_info):
        if (len(feature_info[symbol]) == 0): # If first time tweeting about stock
            return 0
        feature_info = feature_info[symbol]

    # Not bull or bear specific feature
    if (bull_bear == None):
        if (feature_name == 'accuracy'): # looking for a fraction
            bull_res_n = feature_info['unique_correct_predictions']['bull']
            bear_res_n = feature_info['unique_correct_predictions']['bear']
            bull_res_d = feature_info['unique_num_predictions']['bull']
            bear_res_d = feature_info['unique_num_predictions']['bear']
            total_nums = bull_res_d + bear_res_d
            # If never tweeted about this stock
            if (total_nums == 0):
                return 0
            return (bull_res_n + bear_res_n) / total_nums
        else: # only looking for one value
            bull_res = feature_info[feature_name]['bull']
            bear_res = feature_info[feature_name]['bear']
            return bull_res + bear_res
    else:
        if (feature_name == 'accuracy'): # looking for a fraction
            correct = feature_info['unique_correct_predictions'][bull_bear]
            total_nums = feature_info['unique_num_predictions'][bull_bear]
            if (total_nums == 0): # If never tweeted about this stock
                return 0
            spec_acc = correct / total_nums # bull/bear specific accuracy

            # General accuracy
            bull_res_n = feature_info['unique_correct_predictions']['bull']
            bear_res_n = feature_info['unique_correct_predictions']['bear']
            bull_res_d = feature_info['unique_num_predictions']['bull']
            bear_res_d = feature_info['unique_num_predictions']['bear']
            total_nums = bull_res_d + bear_res_d
            general_acc = (bull_res_n + bear_res_n) / total_nums
            return (general_acc + spec_acc) / 2
        else: # only looking for one value
            res = feature_info[feature_name][bull_bear]
            return res
