import datetime
import statistics
import math
import os
import csv
import matplotlib. pyplot as plt
from scipy.optimize import minimize
from functools import reduce
from .hyperparameters import constants
from .userAnalysis import (getStatsPerUser, initializeResult, updateUserFeatures)
from .stockAnalysis import (findDateString, getTopStocksforWeek)
from .stockPriceAPI import (findCloseOpenCached, isTradingDay)
from .helpers import (calcRatio, findWeight, readPickleObject, findAllDays,
                    readCachedTweets, writeCachedTweets, writePickleObject,
                    findTradingDays, findAverageTime)


def optimizeFN(params):
    weightings = {
        'return_w': params[0],
        'bull_w': params[1],
        'bull_return_log_s': params[2],
        # 'bull_w_return': params[2],
        # 'return_ratio_w': params[3],
        # 'return_s_ratio_w': params[3],
        # 'bear_w_return': params[4],
        # 'bull_w_return': params[5],
        # 'return_w1_ratio': params[6],
        # 'bear_return_s': params[7],
        # 'bear': params[8],
        # 'bear_return': params[9],
        # 'count_ratio': params[10],
    }
    start_date = datetime.datetime(2020, 1, 9, 15, 30)
    end_date = datetime.datetime(2020, 6, 19, 9, 30)
    path = 'newPickled/features_new_sqrtx_21_test_aapl.pkl'
    num_top_stocks = 20
    all_features = findFeatures(start_date, end_date, num_top_stocks, path, False)
    result = prediction(start_date, end_date, all_features, num_top_stocks, weightings)
    param_res = list(map(lambda x: round(x, 2), params))
    print(param_res, result)
    return -result


# bull_w_return_w1 OK
# bull_return_log_s OK
# count_ratio_w useless

def optimizeParams():
    params = {
        'return_w': [0.8, (0, 30)],
        'bull_w': [2.6, (0, 30)],
        'bull_return_log_s': [0.3, (0, 30)],
        # 'bull_w_return': [1, (0, 30)],
        # 'return_ratio_w': [1, (0, 30)],
        # 'return_s_ratio_w': [2, (0, 30)],
        # 'bear_w_return': [1.09, (0, 30)],
        # 'bull_w_return': [2.74, (0, 30)],
        # 'return_w1_ratio': [1.9, (0, 30)],
        # 'bear_return_s': [2.8, (0, 30)],
        # 'bear': [7.7, (0, 30)],
        # 'bear_return': [4.1, (0, 30)],
        # 'count_ratio': [1, (0, 30)],
    }

    initial_values = list(map(lambda key: params[key][0], list(params.keys())))
    bounds = list(map(lambda key: params[key][1], list(params.keys())))
    result = minimize(optimizeFN, initial_values, method='SLSQP', options={'maxiter': 30, 'eps': 0.4}, 
                    bounds=(bounds[0],bounds[1],bounds[2]))
    print(result)


# Standardize all features by average stock count for bull/bear
def editFeatures(start_date, end_date, all_features, weights):
    # Find counts of bear/bull per stock
    stock_counts = {}
    for d in all_features:
        for s in all_features[d]:
            if (s not in stock_counts):
                stock_counts[s] = {'bull_count': 0, 
                                'bear_count': 0,
                                'total': 0}
            # print(all_features[d][s])
            bull_count = all_features[d][s]['bull_count']
            bear_count = all_features[d][s]['bear_count']
            stock_counts[s]['bull_count'] += bull_count
            stock_counts[s]['bear_count'] += bear_count
            stock_counts[s]['total'] += 1

    # Take average for each stock
    for s in stock_counts:
        stock_counts[s]['bull_count'] /= stock_counts[s]['total']
        stock_counts[s]['bear_count'] /= stock_counts[s]['total']
        # print(s, stock_counts[s]['bull_count'], stock_counts[s]['bear_count'])

    data = []
    data1 = []
    for d in all_features:
        for s in all_features[d]:
            # standardize all features before using
            result = all_features[d][s]
            for f in all_features[d][s]:
                if ('bull' in f):
                    result[f] /= stock_counts[s]['bull_count']
                else:
                    result[f] /= stock_counts[s]['bear_count']

            result['total'] = result['bull'] - result['bear']
            result['total_w'] = result['bull_w'] - result['bear_w']
            result['return'] = result['bull_return'] - result['bear_return']
            result['return_w'] = result['bull_w_return'] - result['bear_w_return']
            result['return_log'] = result['bull_return_log'] - result['bear_return_log']
            result['return_log_w'] = result['bull_w_return_log'] - result['bear_w_return_log']
            result['return_s'] = result['bull_return_s'] - result['bear_return_s']
            result['return_s_w'] = result['bull_w_return_s'] - result['bear_w_return_s']
            result['return_log_s'] = result['bull_return_log_s'] - result['bear_return_log_s']
            result['return_log_s_w'] = result['bull_w_return_log_s'] - result['bear_w_return_log_s']
            result['return_w1'] = result['bull_w_return_w1'] - result['bear_w_return_w1']
            result['return_w1_s'] = result['bull_w_return_w1_s'] - result['bear_w_return_w1_s']

            result['count_ratio'] = calcRatio(result['bull'], result['bear'])
            result['count_ratio_w'] = calcRatio(result['bull_w'], result['bear_w'])
            result['return_ratio'] = calcRatio(result['bull_return'], result['bear_return'])
            result['return_ratio_w'] = calcRatio(result['bull_w_return'], result['bear_w_return'])
            result['return_log_ratio'] = calcRatio(result['bull_return_log'], result['bear_return_log'])
            result['return_log_ratio_w'] = calcRatio(result['bull_w_return_log'], result['bear_w_return_log'])
            result['return_s_ratio'] = calcRatio(result['bull_return_s'], result['bear_return_s'])
            result['return_s_ratio_w'] = calcRatio(result['bull_w_return_s'], result['bear_w_return_s'])
            result['return_log_s_ratio'] = calcRatio(result['bull_return_log_s'], result['bear_return_log_s'])
            result['return_log_s_ratio_w'] = calcRatio(result['bull_w_return_log_s'], result['bear_w_return_log_s'])
            result['return_w1_ratio'] = calcRatio(result['bull_w_return_w1'], result['bear_w_return_w1'])
            result['return_w1_s_ratio'] = calcRatio(result['bull_w_return_w1_s'], result['bear_w_return_w1_s'])
            
            # Make all bear features negative
            for f in all_features[d][s]:
                if ('bear' in f):
                    all_features[d][s][f] = -all_features[d][s][f]

    # find avg/std for each feature per stock for standardization
    avg_std = findAverageStd(start_date, end_date, all_features)
    for d in all_features:
        for s in all_features[d]:
            # Relative to historical avg/std
            stock_avgstd = avg_std[s]
            stock_features = all_features[d][s]
            # if (s == 'SPY'):
            # for f in stock_features:
            #     stdDev = (stock_features[f] - stock_avgstd[f]['avg']) / stock_avgstd[f]['std']
            #     stock_features[f] = stdDev

            # data.append(stock_features['bull'])
            # data1.append(stock_features['bear'])


    # fig, axs = plt.subplots(2)
    # print(data)
    # print(data1)
    # axs[0].hist(data, density=False, bins=150)
    # axs[1].hist(data1, density=False, bins=150)
    # plt.show()
    return all_features


# Make prediction by chooosing top n stocks to buy per day
# Features are generated before hand per stock per day
def prediction(start_date, end_date, all_features, num_top_stocks, weightings):

    # Standardize all features by their historical counts
    all_features = editFeatures(start_date, end_date, all_features, weightings)

    # cached closeopen prices
    cached_prices = constants['cached_prices']

    # trading days 
    dates = findTradingDays(start_date, end_date)
    total_return = 0
    accuracies = {}
    strong_return = 0
    strong_correct = 0
    strong_total = 0

    # Find top n stock features for each day 
    for date in dates[1:]:
        all_features_day = {}
        date_string = date.strftime("%Y-%m-%d")
        stocks = getTopStocksforWeek(date, num_top_stocks) # top stocks for the week

        # Find features for each stock
        for symbol in stocks:
            stock_features = all_features[date_string][symbol]

            # Weight each feature based on weight param
            result_weight = 0
            total_weight = 0
            for w in weightings:
                result_weight += (weightings[w] * stock_features[w])
                total_weight += weightings[w]
            all_features_day[symbol] = result_weight / total_weight

        # Find percent of each stock to buy (pick top x)
        choose_top_n = 3
        stock_weightings = list(all_features_day.items())
        stock_weightings.sort(key=lambda x: abs(x[1]), reverse=True)
        stock_weightings = stock_weightings[:choose_top_n]
        sum_weights = reduce(lambda a, b: a + b, list(map(lambda x: abs(x[1]), stock_weightings)))

        return_today = 0
        new_res_param = []
        for stock_obj in stock_weightings:
            symbol = stock_obj[0]
            weighting = stock_obj[1]
            close_open = findCloseOpenCached(symbol, date, cached_prices)
            percent_today = (weighting / sum_weights)
            # Make sure close opens are always updated
            if (close_open == None):
                continue
            new_res_param.append([stock_obj[0], stock_obj[1], close_open[2]])
            return_today += (percent_today * close_open[2])

            if (symbol not in accuracies):
                accuracies[symbol] = {}
                accuracies[symbol]['correct'] = 0
                accuracies[symbol]['total'] = 0
            
            if ((close_open[2] < 0 and stock_obj[1] < 0) or (stock_obj[1] > 0 and close_open[2] > 0)):
                accuracies[symbol]['correct'] += 1
            accuracies[symbol]['total'] += 1

        total_return += return_today
        mapped_stocks = list(map(lambda x: [x[0], round(x[1] / sum_weights * 100, 2), x[2]], new_res_param))
        if (len(mapped_stocks) == 0):
            print(date, stock_weightings)
            continue
        print(date_string, return_today, mapped_stocks)
        if (abs(mapped_stocks[0][1]) > 60):
            val = -1 if mapped_stocks[0][1] < 0 else 1
            ret = val * mapped_stocks[0][2]
            if (ret >= 0):
                strong_correct += 1
            strong_total += 1
            strong_return += ret


    total_correct = 0
    total_total = 0
    for s in accuracies:
        total_correct += accuracies[s]['correct']
        total_total += accuracies[s]['total']
        print(s, accuracies[s]['correct'], accuracies[s]['total'])

    print(strong_correct/strong_total, strong_correct, strong_total, strong_return)
    print(total_correct/total_total, total_return)
    return total_return


# Find features of tweets per day of each stock
# INVARIANT: user feature are built up as time increases (TIME MUST ALWAYS INCREASE)
# ^^ Done to reduce calls to close open / unecessary calculations
def findFeatures(start_date, end_date, num_top_stocks, path, update=False):
    if (update == False):
        return readPickleObject(path)

    dates = findTradingDays(start_date, end_date)
    all_features = {}
    all_stock_tweets = {} # store tweets locally for each stock
    user_features = {} # user features temp stored and built up on
    all_user_tweets = {}
    # all_features = readPickleObject(path)

    # Find top stocks given the date (updated per week)
    # Use those stocks to find features based on tweets from those day
    # date_str_1 = datetime.datetime(2020, 6, 24, 9, 30).strftime("%Y-%m-%d")
    # date_str_2 = datetime.datetime(2020, 6, 25, 9, 30).strftime("%Y-%m-%d")
    # del all_features[date_str_1]
    # del all_features[date_str_2]

    bucket = []
    for date in dates[1:]:
        stocks = getTopStocksforWeek(date, num_top_stocks) # top stocks for the week
        date_str = date.strftime("%Y-%m-%d")
        print(date_str)
        if (date_str in all_features):
            continue
        all_features[date_str] = {}
        for symbol in stocks:
            tweets_per_stock = []
            # store all tweets for stock in memory
            if (symbol in all_stock_tweets): 
                tweets_per_stock = all_stock_tweets[symbol]
            else:
                stock_path = 'old_stock_files/' + symbol + '.pkl'
                tweets_per_stock = readPickleObject(stock_path)
                all_stock_tweets[symbol] = tweets_per_stock

            # Find tweets used for predicting for this date
            tweets = findTweets(date, tweets_per_stock, symbol)
            print(date_str,symbol, len(tweets))
            features = stockFeatures(tweets, symbol, user_features, all_user_tweets) # calc features based on tweets/day
            all_features[date_str][symbol] = features

    writePickleObject(path, all_features)
    return all_features


# Find all tweets on this given day from database
def findTweets(date, tweets_per_stock, symbol):
    # Find start end and end dates for the given date
    day_increment = datetime.timedelta(days=1)
    date_end = datetime.datetime(date.year, date.month, date.day, 16)
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
            path = 'old_stock_files/' + symbol + '.pkl'
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

    tweets = list(filter(lambda tweet: tweet['time'] > date_start and tweet['time'] < date_end, tweets))
    tweets.sort(key=lambda tweet: tweet['time'], reverse=True)
    return tweets


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

    for username in users:
        path = 'user_tweets/' + username + '.csv'
        if (os.path.exists(path)):
            continue

        print(username)
        tweets_collection = constants['stocktweets_client'].get_database('tweets_db').tweets
        query = {'$and': [{'user': username}, { "$or": [{'isBull': True}, {'isBull': False}] }]}
        tweets = list(tweets_collection.find(query).sort('time', -1))
        tweets = list(map(lambda t: [t['time'], t['symbol'], t['isBull']], tweets))

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
    path = 'user_tweets/' + username + '.csv'
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
def initializeUserFeatures(user):
    result = {}
    result['_id'] = user
    keys = ['correct_predictions', 'num_predictions',
            'unique_correct_predictions', 'unique_num_predictions', 
            'unique_return', 'unique_return_log', 'unique_return_w1']

    for k in keys:
        result[k] = {}
        result[k]['bull'] = 0
        result[k]['bear'] = 0

    result['perStock'] = {}
    return result


# Calculate user's features based on tweets before this date
# Loop through all tweets made by user and feature extract per user
def calculateUserFeatures(username, date, all_user_features, tweets):
    date = date - datetime.timedelta(days=3) # Find all tweet/predictions before this date
    unique_stocks = {} # Keep track of unique tweets per day/stock
    result = {} # Resulting user features

    if (username in all_user_features):
        result = all_user_features[username]
        last_updated = result['last_updated'] # last time that was parsed

        # Filter by tweets before the current date and after last updated date
        for tweet in tweets:
            # if (tweet['time'] >= last_updated and tweet['time'] < date and tweet['symbol'] in constants['top_stocks']):
            if (tweet['time'] >= last_updated and tweet['time'] < date):
                updateUserFeatures(result, tweet, unique_stocks)
    else:
        result = initializeUserFeatures(username) # initialize user features for first time
        # Only filter by all tweets before current date
        for tweet in tweets:
            # if (tweet['time'] < date and tweet['symbol'] in constants['top_stocks']):
            if (tweet['time'] < date):
                updateUserFeatures(result, tweet, unique_stocks)

    result['last_updated'] = date # update time it was parsed so dont have to reparse

    # Update unique predictions per day features
    for time_string in unique_stocks:
        tweeted_date = unique_stocks[time_string]['time']
        w = findWeight(tweeted_date, 'log(x)') # weighted based on time of tweet
        symbol = unique_stocks[time_string]['symbol']

        # Find whether tweet was bull or bear based on last tweet prediction
        label = 'bull' if unique_stocks[time_string]['last_prediction'] else 'bear'

        percent_change = unique_stocks[time_string]['percent_change']
        correct_prediction = (label == 'bull' and percent_change >= 0) or (label == 'bear' and percent_change <= 0)
        correct_prediction_num = 1 if correct_prediction else 0
        percent_return = abs(percent_change) if correct_prediction else -abs(percent_change)

        result['unique_return_w1'][label] += w * percent_return
        result['unique_correct_predictions'][label] += correct_prediction_num
        result['unique_num_predictions'][label] += 1
        result['unique_return'][label] += percent_return

        result['perStock'][symbol]['unique_return_w1'][label] += w * percent_return
        result['perStock'][symbol]['unique_correct_predictions'][label] += correct_prediction_num
        result['perStock'][symbol]['unique_num_predictions'][label] += 1
        result['perStock'][symbol]['unique_return'][label] += percent_return

        # return unique (log) Weighted by number of times posted that day
        num_labels = unique_stocks[time_string]['count']
        val = percent_return * (math.log10(num_labels) + 1)
        result['unique_return_log'][label] += val
        result['perStock'][symbol]['unique_return_log'][label] += val

    all_user_features[username] = result
    return result


def updateAllUsers():
    print("Setup User Info")
    allUsers = constants['db_user_client'].get_database('user_data_db').user_accuracy_actual
    users = allUsers.find({})
    print(users.count())
    count = 0
    for u in users:
        if (count % 1000 == 0):
            print(count)
        count += 1

        username = u['_id']
        path = 'user_files/' + username + '.pkl'
        found_user = readPickleObject(path)
        if (len(list(found_user.keys())) != 0):
            continue

        writePickleObject(path, u)
    

# Finds tweets for the given date range and stores them locally to be cached
def writeTweets(start_date, end_date, num_top_stocks):
    print("Setting up tweets")
    day_increment = datetime.timedelta(days=1)
    all_dates = findAllDays(start_date, end_date)
    
    # Find stocks to parse per day
    for date in all_dates:
        date_string = date.strftime("%Y-%m-%d")
        stocks = getTopStocksforWeek(date, num_top_stocks) # top stocks for the week
        for symbol in stocks:
            path = 'new_stock_files/' + symbol + '.pkl'
            tweets_per_stock = readPickleObject(path)
            if (date_string in tweets_per_stock):
                print(symbol, date_string, len(tweets_per_stock[date_string]), "EXISTS")
                continue

            # Find all tweets for the given day
            date_start = datetime.datetime(date.year, date.month, date.day, 0, 0)
            date_end = datetime.datetime(date.year, date.month, date.day) + day_increment
            tweets = fetchTweets(date_start, date_end, symbol)
            tweets_per_stock[date_string] = tweets

            # Write to the stock pickled object
            writePickleObject(path, tweets_per_stock)
            print(symbol, date_string, len(tweets_per_stock[date_string]))


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
    tweets = list(map(lambda t: {'user': t['user'], 'time': t['time'], 'isBull': t['isBull']}, tweets))
    return tweets


def findUserInfo(username):
    path = 'user_files/' + username + '.pkl'
    found_user = readPickleObject(path)
    if (len(list(found_user.keys())) == 0):
        return None
    return found_user


def buildStockFeatures():
    result = {}
    labels = ['bull', 'bear', 'bull_w', 'bear_w']
    features = ['return_w1', 'return_w1_s', 'return', 'return_log', 'return_s', 'return_log_s']
    for l in labels:
        result[l] = 0
        for f in features:
            result[l + '_' + f] = 0
    return result


# Return feature parameters based on tweets for a given trading day/s
# Builds user features as more information is seen about that user
def stockFeatures(tweets, symbol, all_user_features, all_user_tweets):
    result = buildStockFeatures()
    bull_count = 0
    bear_count = 0
    seen_users = {}

    # Assume tweets sorted from new to old
    # Find all last predictions and counts
    for tweet in tweets:
        username = tweet['user']
        isBull = tweet['isBull']
        tweeted_date = tweet['time']
        w = findWeight(tweeted_date, 'log(x)')
        # Only look at the most recent prediction by user
        if (username in seen_users):
            # If previous prediction was the same as last prediction, add to weighting
            prev_prediction = seen_users[username]['isBull']
            if (isBull == prev_prediction):
                seen_users[username]['count'] += w
            continue
        seen_users[username] = {
            'user': tweet['user'],
            'isBull': isBull,
            'count': w,
            'time': tweet['time']
        }

    # Look at all unique predictions and their counts
    for user in seen_users:
        username = seen_users[user]['user']
        tweeted_date = seen_users[user]['time']
        label = 'bull' if seen_users[user]['isBull'] else 'bear'
        w = findWeight(tweeted_date, 'log(x)') # weighted based on time of tweet

        # Get user tweets from file or locally
        user_tweets = []
        if (username in all_user_tweets):
            user_tweets = all_user_tweets[username]
            if (user_tweets == None):
                continue
        else:
            user_tweets = cachedUserTweets(username)
            all_user_tweets[username] = user_tweets
            if (user_tweets == None):
                continue

        # Find user features (return, accuracy, etc.) before tweeted date
        user_info = calculateUserFeatures(username, tweeted_date, all_user_features, user_tweets)

        num_tweets = findFeature(user_info, '', ['num_predictions'], None)
        num_tweets_unique = findFeature(user_info, '', ['unique_num_predictions'], None)
        num_tweets_s = findFeature(user_info, symbol, ['num_predictions'], None)
        num_tweets_s_unique = findFeature(user_info, symbol, ['unique_num_predictions'], None)

        # Filter by number of tweets
        if (num_tweets <= 40 or num_tweets_s <= 10 or num_tweets_unique <= 5 or num_tweets_s_unique <= 5):
            continue

        accuracy_unique = findFeature(user_info, '', ['unique_correct_predictions', 'unique_num_predictions'], None)
        accuracy_unique_s = findFeature(user_info, symbol, ['unique_correct_predictions', 'unique_num_predictions'], None)
        return_unique = findFeature(user_info, '', ['unique_return'], None)
        return_unique_s = findFeature(user_info, symbol, ['unique_return'], None)
        return_unique_log = findFeature(user_info, '', ['unique_return_log'], None)
        return_unique_log_s = findFeature(user_info, symbol, ['unique_return_log'], None)
        return_unique_w1 = findFeature(user_info, '', ['unique_return_w1'], None)
        return_unique_w1_s = findFeature(user_info, symbol, ['unique_return_w1'], None)

        # Filter by accuracy
        if (accuracy_unique < 0.4 or accuracy_unique_s < 0.4):
            continue

        # Filter by return
        if (return_unique < 1 or return_unique_s < 1 or return_unique_log < 1 or
            return_unique_log_s < 1 or return_unique_w1 < 1 or return_unique_w1_s < 1):
            continue

        if (seen_users[user]['isBull']):
            bull_count += 1
        else:
            bear_count += 1

        return_unique = math.log10(return_unique) + 1
        return_unique_s = math.log10(return_unique_s) + 1
        return_unique_log = math.log10(return_unique_log) + 1
        return_unique_log_s = math.log10(return_unique_log_s) + 1
        return_unique_w1 = math.log10(return_unique_w1) + 1
        return_unique_w1_s = math.log10(return_unique_w1_s) + 1

        # Give user a weight between 0 and 1 and apply to all features
        user_weight = weightedUserPrediction(user_info, symbol)
        tweet_value = user_weight * w

        result[label] += tweet_value
        result[label + '_return_w1'] += tweet_value * return_unique_w1
        result[label + '_return_w1_s'] += tweet_value * return_unique_w1_s
        result[label + '_return'] += tweet_value * return_unique
        result[label + '_return_log'] += tweet_value * return_unique_log
        result[label + '_return_s'] += tweet_value * return_unique_s
        result[label + '_return_log_s'] += tweet_value * return_unique_log_s

        # return unique (log) Weighted by number of times posted that day
        num_prediction_log = math.log10(seen_users[user]['count']) + 1
        result[label + '_w'] += tweet_value * num_prediction_log
        result[label + '_w_return_w1'] += tweet_value * return_unique_w1 * num_prediction_log
        result[label + '_w_return_w1_s'] += tweet_value * return_unique_w1_s * num_prediction_log
        result[label + '_w_return'] += tweet_value * return_unique * num_prediction_log
        result[label + '_w_return_log'] += tweet_value * return_unique_log * num_prediction_log
        result[label + '_w_return_s'] += tweet_value * return_unique_s * num_prediction_log
        result[label + '_w_return_log_s'] += tweet_value * return_unique_log_s * num_prediction_log
        # bucket.append([num_tweets, num_tweets_unique, num_tweets_s, num_tweets_s_unique, accuracy_unique, accuracy_unique_s, return_unique, return_unique_s])

    result['bull_count'] = bull_count
    result['bear_count'] = bear_count
    print(result['bull_count'], result['bear_count'])
    return result



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

def weightedUserPrediction(user, symbol):
    num_tweets = findFeature(user, '', ['num_predictions'], None)
    num_tweets_s = findFeature(user, symbol, ['num_predictions'], None)

    # Scale between 800 / 400
    scaled_num_tweets = math.sqrt(num_tweets) / math.sqrt(800)
    scaled_num_tweets_s = math.sqrt(num_tweets_s) / math.sqrt(400)
    if (scaled_num_tweets > 1):
        scaled_num_tweets = 1
    if (scaled_num_tweets_s > 1):
        scaled_num_tweets_s = 1

    return_unique = findFeature(user, '', ['unique_return'], None)
    return_unique_s = findFeature(user, symbol, ['unique_return'], None)


    # (2) scale between 0 and 1
    scaled_return_unique = math.sqrt(return_unique) / math.sqrt(300)
    scaled_return_unique_s = math.sqrt(return_unique_s) / math.sqrt(150)
    if (scaled_return_unique > 1):
        scaled_return_unique = 1
    if (scaled_return_unique_s > 1):
        scaled_return_unique_s = 1


    # (3) all features combined (scale accuracy from 0.5 - 1 to between 0.7 - 1.2)
    accuracy_unique = findFeature(user, '', ['unique_correct_predictions', 'unique_num_predictions'], None) + 0.2
    accuracy_unique_s = findFeature(user, symbol, ['unique_correct_predictions', 'unique_num_predictions'], None) + 0.2

    all_features = 2 * accuracy_unique * scaled_num_tweets * scaled_return_unique
    all_features_s = 2 * accuracy_unique_s * scaled_num_tweets_s * scaled_return_unique_s

    return (scaled_num_tweets + scaled_num_tweets_s + scaled_return_unique +
            scaled_return_unique_s + all_features + all_features_s) / 8


# Find feature for given user based on symbol and feature name
def findFeature(user, symbol, feature_names, bull_bear):
    feature_info = user
    # If finding general feature
    if (symbol != ''):
        # why would this happen??
        if (symbol in user['perStock']):
            feature_info = user['perStock'][symbol]

    # Not bull or bear specific feature
    if (bull_bear == None):
        # only looking for one value
        if (len(feature_names) == 1):
            bull_res = feature_info[feature_names[0]]['bull']
            bear_res = feature_info[feature_names[0]]['bear']
            return bull_res + bear_res
        # looking for a fraction
        else:
            bull_res_n = feature_info[feature_names[0]]['bull']
            bear_res_n = feature_info[feature_names[0]]['bear']
            bull_res_d = feature_info[feature_names[1]]['bull']
            bear_res_d = feature_info[feature_names[1]]['bear']
            total_nums = bull_res_d + bear_res_d
            # If never tweeted about this stock
            if (total_nums == 0):
                return findFeature(user, '', feature_names, bull_bear)
            return (bull_res_n + bear_res_n) * 1.0 / total_nums
    else:
        # only looking for one value
        if (len(feature_names) == 1):
            res = feature_info[feature_names[0]][bull_bear]
            return res
        # looking for a fraction
        else:
            correct = feature_info[feature_names[0]][bull_bear]
            total_nums = feature_info[feature_names[1]][bull_bear]
            # If never tweeted about this stock
            if (total_nums == 0):
                return findFeature(user, '', feature_names, bull_bear)
            return correct * 1.0 / total_nums
