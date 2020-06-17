import datetime
import statistics
import math
import os
import csv
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
        'count_ratio': params[0],
        'return_log_ratio': params[1],
        'total': params[2],
        'return_log_s_ratio': params[3],
        'return_s_ratio': params[4]
    }
    start_date = datetime.datetime(2020, 1, 9, 15, 30)
    end_date = datetime.datetime(2020, 6, 9, 9, 30)
    path = 'newPickled/features_new_sqrtx.pkl'
    num_top_stocks = 20
    all_features = findFeatures(start_date, end_date, num_top_stocks, path, False)
    result = prediction(start_date, end_date, all_features, num_top_stocks, weightings)
    param_res = list(map(lambda x: round(x, 2), params))
    print(param_res, result)
    return -result


# result['total'] = result['bull'] - result['bear']
# result['return'] = result['bull_return'] - result['bear_return']
# result['return_log'] = result['bull_return_log'] - result['bear_return_log']
# result['return_s'] = result['bull_return_s'] - result['bear_return_s']
# result['return_log_s'] = result['bull_return_log_s'] - result['bear_return_log_s']

# # Need to look at historical ratios to determine if this is sig diff 
# # negative means more bear than bull
# # ratio of the "sentiment" for the day
# result['count_ratio'] = calcRatio(result['bull'], result['bear'])
# result['return_ratio'] = calcRatio(result['bull_return'], result['bear_return'])
# result['return_log_ratio'] = calcRatio(result['bull_return_log'], result['bear_return_log'])
# result['return_s_ratio'] = calcRatio(result['bull_return_s'], result['bear_return_s'])
# result['return_log_s_ratio'] = calcRatio(result['bull_return_log_s'], result['bear_return_log_s'])

# BAD
# bull_return_s
# return_log
# bull_return_log
# bull_return_log_s


def optimizeParams():
    params = {
        'count_ratio': [9, (8, 11)],
        'return_log_ratio': [0.7, (0.5, 2)],
        'total': [0.3, (0, 2)],
        'return_log_s_ratio': [0.1, (0, 1)],
        'return_s_ratio': [0.1, (0, 1)],
    }

    initial_values = list(map(lambda key: params[key][0], list(params.keys())))
    bounds = list(map(lambda key: params[key][1], list(params.keys())))
    result = minimize(optimizeFN, initial_values, method='SLSQP', options={'maxiter': 20, 'eps': 0.1}, 
                    bounds=(bounds[0],bounds[1],bounds[2],bounds[3],bounds[4]))
    print(result)



# Make prediction by chooosing top n stocks to buy per day
# Features are generated before hand per stock per day
def prediction(start_date, end_date, all_features, num_top_stocks, weightings):
    # cached closeopen prices
    cached_prices = constants['cached_prices']
    # find avg/std for each feature per stock
    avg_std = findAverageStd(start_date, end_date, all_features)
    # trading days 
    dates = findTradingDays(start_date, end_date)
    total_return = 0
    accuracies = {}

    # Find top n stock features for each day 
    for date in dates[1:]:
        all_features_day = {}
        date_string = date.strftime("%Y-%m-%d")
        stocks = getTopStocksforWeek(date, num_top_stocks) # top stocks for the week
        # Find features for each stock
        for symbol in stocks:
            # Relative to historical avg/std
            stock_avgstd = avg_std[symbol]
            stock_features = all_features[date_string][symbol]
            stock_features_calibrated = {}
            for f in stock_features:
                stdDev = (stock_features[f] - stock_avgstd[f]['avg']) / stock_avgstd[f]['std']
                stock_features_calibrated[f] = stdDev

            # Weight each feature based on weight param
            result_weight = 0
            total_weight = 0
            for w in weightings:
                result_weight += (weightings[w] * stock_features_calibrated[w])
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
        # print(date_string, return_today, mapped_stocks)

    total_correct = 0
    total_total = 0
    for s in accuracies:
        total_correct += accuracies[s]['correct']
        total_total += accuracies[s]['total']
        # print(s, accuracies[s]['correct'], accuracies[s]['total'])

    # print(total_correct/total_total, total_return)
    return total_return


# Find features of tweets per day of each stock
# INVARIANT: user feature are built up as time increases (TIME MUST ALWAYS INCREASE)
# ^^ Done to reduce calls to close open / unecessary calculations
def findFeatures(start_date, end_date, num_top_stocks, path, update=False):
    if (update == False):
        return readPickleObject(path)

    dates = findTradingDays(start_date, end_date)
    cached_prices = readPickleObject('newPickled/averaged.pkl')
    all_features = {}
    all_stock_tweets = {} # store tweets locally for each stock
    user_features = {} # user features temp stored and built up on
    all_user_tweets = {}

    # Find top stocks given the date (updated per week)
    # Use those stocks to find features based on tweets from those day
    for date in dates[1:]:
        stocks = getTopStocksforWeek(date, num_top_stocks) # top stocks for the week
        date_str = date.strftime("%Y-%m-%d")
        all_features[date_str] = {}
        print(date.strftime("%Y-%m-%d"))
        for symbol in stocks:
            tweets_per_stock = []
            if (symbol in all_stock_tweets): 
                tweets_per_stock = all_stock_tweets[symbol]
            else:
                stock_path = 'new_stock_files/' + symbol + '.pkl'
                tweets_per_stock = readPickleObject(stock_path)
                all_stock_tweets[symbol] = tweets_per_stock

            tweets = findTweets(date, tweets_per_stock, cached_prices, symbol)
            features = stockFeatures(tweets, symbol, cached_prices, user_features, all_user_tweets) # calc features based on tweets/day
            all_features[date_str][symbol] = features

    writePickleObject(path, all_features)
    return all_features


# Find all tweets on this given day from database
def findTweets(date, tweets_per_stock, cached_prices, symbol):
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
            print(date_string, symbol, "HOWHOWHOWHOW")
            path = 'new_stock_files/' + symbol + '.pkl'
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
            'unique_return', 'unique_return_log']

    for k in keys:
        result[k] = {}
        result[k]['bull'] = 0
        result[k]['bear'] = 0

    result['perStock'] = {}
    return result


# Calculate user's features based on tweets before this date
def calculateUserFeatures(username, date, cached_prices, all_user_features, tweets):
    date = date - datetime.timedelta(days=1) # Find all tweet/predictions before this date
    unique_stocks = {} # Keep track of unique tweets per day/stock

    result = initializeUserFeatures(username)
    if (username in all_user_features):
        # Filter by tweets before the current date and after last updated date
        result = all_user_features[username]
        last_updated = result['last_updated']
        tweets = filter(lambda tweet: tweet['time'] >= last_updated and tweet['time'] < date, tweets)
    else:
        # Only filter by all tweets before current date
        tweets = filter(lambda tweet: tweet['time'] < date, tweets)
    result['last_updated'] = date

    # Loop through all tweets made by user and feature extract per user
    for tweet in tweets:
        updateUserFeatures(result, tweet, unique_stocks, cached_prices)

    # Update unique predictions per day features
    for time_string in unique_stocks:
        symbol = unique_stocks[time_string]['symbol']
        # times = unique_stocks[time_string]['times']
        # average_time = findAverageTime(times)

        # Find whether tweet was bull or bear based on majority
        label = 'bull'
        if (unique_stocks[time_string]['bear'] > unique_stocks[time_string]['bull']):
            label = 'bear'
        if (unique_stocks[time_string]['bear'] == unique_stocks[time_string]['bull']):
            label = 'bull' if unique_stocks[time_string]['last_prediction'] else 'bear'

        percent_change = unique_stocks[time_string]['percent_change']
        correct_prediction = (label == 'bull' and percent_change >= 0) or (label == 'bear' and percent_change <= 0)
        correct_prediction_num = 1 if correct_prediction else 0
        percent_return = abs(percent_change) if correct_prediction else -abs(percent_change)

        result['unique_correct_predictions'][label] += correct_prediction_num
        result['perStock'][symbol]['unique_correct_predictions'][label] += correct_prediction_num
        result['unique_num_predictions'][label] += 1
        result['perStock'][symbol]['unique_num_predictions'][label] += 1
        result['unique_return'][label] += percent_return
        result['perStock'][symbol]['unique_return'][label] += percent_return

        # return unique (log) Weighted by number of times posted that day
        num_labels = unique_stocks[time_string][label]
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

# Calculate features based on list of tweets
# Each tweet is multiplied by the weights
# number tweets
# number unique tweets
# bull count / ratio
# unique bull / ratio
# bear count / ratio
# unique bull / ratio
# unique return

def buildStockFeatures():
    result = {}
    labels = ['bull', 'bear']
    features = ['return', 'return_log', 'return_s', 'return_log_s']
    for l in labels:
        result[l] = 0
        for f in features:
            result[l + '_' + f] = 0
    return result


# Return feature parameters based on tweets for a given trading day/s
# Builds user features as more information is seen about that user
def stockFeatures(tweets, symbol, cached_prices, all_user_features, all_user_tweets):
    result = buildStockFeatures()
    bull_count = 0
    bear_count = 0
    seen_users = set([])

    # Assume tweets sorted from new to old
    for tweet in tweets:
        username = tweet['user']
        # Only look at the most recent prediction by user
        # Use other tweets for weighting?
        if (username in seen_users):
            continue
        seen_users.add(username)
        isBull = tweet['isBull']
        tweeted_date = tweet['time']
        label = 'bull' if isBull else 'bear'
        w = findWeight(tweeted_date, 'sqrt(x)') # weighted based on time of tweet

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
        user_info = calculateUserFeatures(username, tweeted_date, cached_prices, all_user_features, user_tweets)

        return_unique = findFeature(user_info, '', ['unique_return'], label)
        return_unique_log = findFeature(user_info, '', ['unique_return_log'], label)
        return_unique_s = findFeature(user_info, symbol, ['unique_return'], label)
        return_unique_log_s = findFeature(user_info, symbol, ['unique_return_log'], label)

        user_weight = weightedUserPrediction(user_info, symbol)
        tweet_value = user_weight * w
        if (isBull):
            bull_count += 1
        else:
            bear_count += 1

        result[label] += tweet_value
        result[label + '_return'] += tweet_value * return_unique
        result[label + '_return_log'] += tweet_value * return_unique_log
        result[label + '_return_s'] += tweet_value * return_unique_s
        result[label + '_return_log_s'] += tweet_value * return_unique_log_s

    # Standardize by number of tweets
    try:
        for f in result:
            if ('bull' in f):
                result[f] /= bull_count
    except:
        pass
    
    try:
        for f in result:
            if ('bear' in f):
                result[f] /= bull_count
    except:
        pass

    # Average should be 0?
    # Should be standardized between stocks since divided by total count ?
    # "sentiment" of the stock for the day
    result['total'] = result['bull'] - result['bear']
    result['return'] = result['bull_return'] - result['bear_return']
    result['return_log'] = result['bull_return_log'] - result['bear_return_log']
    result['return_s'] = result['bull_return_s'] - result['bear_return_s']
    result['return_log_s'] = result['bull_return_log_s'] - result['bear_return_log_s']

    # Need to look at historical ratios to determine if this is sig diff 
    # negative means more bear than bull
    # ratio of the "sentiment" for the day
    result['count_ratio'] = calcRatio(result['bull'], result['bear'])
    result['return_ratio'] = calcRatio(result['bull_return'], result['bear_return'])
    result['return_log_ratio'] = calcRatio(result['bull_return_log'], result['bear_return_log'])
    result['return_s_ratio'] = calcRatio(result['bull_return_s'], result['bear_return_s'])
    result['return_log_s_ratio'] = calcRatio(result['bull_return_log_s'], result['bear_return_log_s'])
    return result


# Find the weight of a stock based on list of features (range is from -1 to 1)
def calcStockWeight(features, weights):
    result = 0
    total_weights = 0
    for f in weights:
        w = weights[f]
        total_weights += w
        result += (w * features[f])

    return result / total_weights


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
    # function = 'log(x)'
    bull_bear = None
    num_tweets = findFeature(user, '', ['num_predictions'], bull_bear)
    num_tweets_s = findFeature(user, symbol, ['num_predictions'], bull_bear)

    # Don't consider anyone below 60 predictions
    if (num_tweets < 70):
        return 0

    # (1) scale between 70-700 (general) and 1-100 (per stock)
    scaled_num_tweets = (math.sqrt(num_tweets) - math.sqrt(70)) / (math.sqrt(700) - math.sqrt(70))
    scaled_num_tweets_s = math.sqrt(num_tweets_s) / math.sqrt(50)
    if (scaled_num_tweets > 1):
        scaled_num_tweets = 1
    if (scaled_num_tweets_s > 1):
        scaled_num_tweets_s = 1

    accuracy_unique = findFeature(user, '', ['unique_correct_predictions', 'unique_num_predictions'], bull_bear)
    accuracy_unique_s = findFeature(user, symbol, ['unique_correct_predictions', 'unique_num_predictions'], bull_bear)

    return_unique = findFeature(user, '', ['unique_return'], bull_bear)
    return_unique_s = findFeature(user, symbol, ['unique_return'], bull_bear)

    # (2) scale between -100 and 100 / -100 and 100
    scaled_return_unique = (100 + return_unique) / 200
    scaled_return_unique_s = (100 + return_unique_s) / 200
    if (scaled_return_unique > 1):
        scaled_return_unique = 1
    if (scaled_return_unique_s > 1):
        scaled_return_unique_s = 1

    accuracy_x_tweets = accuracy_unique * scaled_num_tweets
    accuracy_x_tweets_s = accuracy_unique_s * scaled_num_tweets_s

    # (3)
    all_features = accuracy_x_tweets * scaled_return_unique
    all_features_s = 2 * accuracy_x_tweets_s * scaled_return_unique_s

    # print(scaled_num_tweets)
    # print(scaled_num_tweets_s)
    # print(scaled_return_unique)
    # print(scaled_return_unique_s)
    # print(all_features)
    # print(all_features_s)

    return (scaled_num_tweets + scaled_num_tweets_s + scaled_return_unique +
            scaled_return_unique_s + all_features + all_features_s) / 6


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
            res_n = feature_info[feature_names[0]][bull_bear]
            res_d = feature_info[feature_names[1]][bull_bear]
            total_nums = res_n + res_d
            # If never tweeted about this stock
            if (total_nums == 0):
                return findFeature(user, '', feature_names, bull_bear)
            return res_n * 1.0 / total_nums
