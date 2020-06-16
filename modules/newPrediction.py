import datetime
import statistics
import math
from functools import reduce
from .hyperparameters import constants
from .userAnalysis import getStatsPerUser
from .stockAnalysis import (findDateString, getTopStocksforWeek)
from .stockPriceAPI import (findCloseOpenCached)
from .helpers import (calcRatio, findWeight, readPickleObject, findAllDays,
                    readCachedTweets, writeCachedTweets, writePickleObject,
                    findTradingDays)


# Make prediction by chooosing top n stocks to buy per day
# Features are generated before hand per stock per day
def prediction(start_date, end_date, all_features, num_top_stocks, weightings):
    # cached closeopen prices
    cached_prices = readPickleObject('newPickled/averaged.pkl')
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
        print(date_string, return_today, mapped_stocks)

    total_correct = 0
    total_total = 0
    for s in accuracies:
        total_correct += accuracies[s]['correct']
        total_total += accuracies[s]['total']
        print(s, accuracies[s]['correct'], accuracies[s]['total'])

    print(total_correct/total_total, total_return)
    return (total_return, total_correct/total_total)


# Find features of tweets per day of each stock
def findFeatures(start_date, end_date, num_top_stocks, path, update=False):
    if (update == False):
        return readPickleObject(path)

    dates = findTradingDays(start_date, end_date)
    cached_prices = readPickleObject('newPickled/averaged.pkl')
    all_features = {}

    # Find top stocks given the date (updated per week)
    # Use those stocks to find features based on tweets from those day
    all_stock_tweets = {}
    for date in dates[1:]:
        stocks = getTopStocksforWeek(date, num_top_stocks) # top stocks for the week
        date_str = date.strftime("%Y-%m-%d")
        all_features[date_str] = {}
        for symbol in stocks:
            tweets_per_stock = []
            if (symbol in all_stock_tweets): 
                tweets_per_stock = all_stock_tweets[symbol]
            else:
                stock_path = 'new_stock_files/' + symbol + '.pkl'
                tweets_per_stock = readPickleObject(stock_path)
                all_stock_tweets[symbol] = tweets_per_stock
                # print(tweets_per_stock)

            tweets = findTweets(date, tweets_per_stock, cached_prices, symbol)
            features = stockFeatures(tweets, symbol) # calc features based on tweets/day
            all_features[date_str][symbol] = features
            print(date.strftime("%Y-%m-%d"), symbol, len(tweets))

    writePickleObject(path, all_features)


# Find all tweets on this given day from database
def findTweets(date, tweets_per_stock, cached_prices, symbol):
    # Find start end and end dates for the given date
    day_increment = datetime.timedelta(days=1)
    date_end = datetime.datetime(date.year, date.month, date.day, 16)
    date_start = date_end - day_increment
    dates = [date_end, date_start]
    while (date_start.strftime("%Y-%m-%d") not in cached_prices):
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


# divide by number of predictions per day
# Return feature parameters based on tweets
def stockFeatures(tweets, symbol):
    result = buildStockFeatures()
    function = '1'
    bull_count = 0
    bear_count = 0
    seen_users = set([])

    # Assume tweets sorted from new to old
    for tweet in tweets:
        username = tweet['user']
        # Only look at the most recent prediction by user
        if (username in seen_users):
            continue
        seen_users.add(username)
        isBull = tweet['isBull']
        label = 'bull' if isBull else 'bear'
        w = findWeight(tweet['time'], function)

        user_info = findUserInfo(username)
        if (user_info == None):
            continue

        return_unique = findFeature(user_info, '', ['returnUnique'], function, label)
        return_unique_log = findFeature(user_info, '', ['returnUniqueLog'], function, label)
        return_unique_s = findFeature(user_info, symbol, ['returnUnique'], function, label)
        return_unique_log_s = findFeature(user_info, symbol, ['returnUniqueLog'], function, label)

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
    function = 'log(x)'
    bull_bear = None
    num_tweets = findFeature(user, '', ['numPredictions'], function, bull_bear)
    num_tweets_s = findFeature(user, symbol, ['numPredictions'], function, bull_bear)

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

    accuracy_unique = findFeature(user, '', ['numUnique', 'numPredictions'], function, bull_bear)
    accuracy_unique_s = findFeature(user, symbol, ['numUnique', 'numPredictions'], function, bull_bear)

    return_unique = findFeature(user, '', ['returnUnique'], function, bull_bear)
    return_unique_s = findFeature(user, symbol, ['returnUnique'], function, bull_bear)

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
def findFeature(user, symbol, feature_names, function, bull_bear):
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
            bull_res = feature_info[function][feature_names[0]]['bull']
            bear_res = feature_info[function][feature_names[0]]['bear']
            return bull_res + bear_res
        # looking for a fraction
        else:
            bull_res_n = feature_info[function][feature_names[0]]['bull']
            bear_res_n = feature_info[function][feature_names[0]]['bear']
            bull_res_d = feature_info[function][feature_names[1]]['bull']
            bear_res_d = feature_info[function][feature_names[1]]['bear']
            total_nums = bull_res_d + bear_res_d
            # If never tweeted about this stock
            if (total_nums == 0):
                return findFeature(user, '', feature_names, function, bull_bear)
            return (bull_res_n + bear_res_n) * 1.0 / total_nums
    else:
        # only looking for one value
        if (len(feature_names) == 1):
            res = feature_info[function][feature_names[0]][bull_bear]
            return res
        # looking for a fraction
        else:
            res_n = feature_info[function][feature_names[0]][bull_bear]
            res_d = feature_info[function][feature_names[1]][bull_bear]
            total_nums = res_n + res_d
            # If never tweeted about this stock
            if (total_nums == 0):
                return findFeature(user, '', feature_names, function, bull_bear)
            return res_n * 1.0 / total_nums
