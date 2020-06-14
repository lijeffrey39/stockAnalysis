import datetime
import math
from .hyperparameters import constants
from .userAnalysis import getStatsPerUser
from .helpers import (calcRatio, findWeight, readPickleObject,
                    readCachedTweets, writeCachedTweets, writePickleObject)


def prediction(dates, stocks, updateObject):
    tweets_all = findAllTweets(dates, stocks, updateObject)
    weightings = {
        'total': 1,
        'return_log': 1,
        'return_s': 1,
        'count_ratio': 1
    }
    for date in dates:
        print(date)
        for symbol in stocks:
            tweets = tweets_all[symbol][date]
            features = stockFeatures(tweets, symbol)
            print(features)



def findAllTweets(dates, stocks, updateObject=False):
    print("Setting up tweets")
    path = 'newPickled/allTweets.pkl'
    result = readPickleObject(path)

    for symbol in stocks:
        print(symbol)
        if (symbol not in result):
            result[symbol] = {}

        # Tweets per symbol cached in files for easy access
        # cachedTweets = readCachedTweets(symbol)
        for date in dates:
            # Check if the date exists in the cached tweets
            # AND If date not stored in current pickle object
            if (date in result[symbol]):
                print(date, len(result[symbol][date]))
                continue

            tweets = findTweets(date, symbol, True)
            result[symbol][date] = tweets
            print(date, len(result[symbol][date]))
            writeCachedTweets(symbol, tweets)

    if (updateObject):
        writePickleObject(path, result)
    return result

# Find all tweets on this given day from database
def findTweets(date, symbol, full=False):
    tweetsDB = constants['stocktweets_client'].get_database('tweets_db')
    db = constants['db_client'].get_database('stocks_data_db').updated_close_open
    dayIncrement = datetime.timedelta(days=1)
    dateEnd = datetime.datetime(date.year, date.month, date.day, 16)
    if (full):
        dateEnd = datetime.datetime(date.year, date.month, date.day, 23, 59)
    dateStart = dateEnd - dayIncrement

    # find dateStart starting at dateEnd
    testDay = db.find_one({'_id': 'AAPL ' + dateStart.strftime("%Y-%m-%d")})
    count = 0
    while (testDay is None and count != 10):
        dateStart -= dayIncrement
        testDay = db.find_one({'_id': 'AAPL ' + dateStart.strftime("%Y-%m-%d")})
        count += 1

    query = {"$and": [{'symbol': symbol},
                      {"$or": [
                            {'isBull': True},
                            {'isBull': False}
                      ]},
                      {'time': {'$gte': dateStart,
                                '$lt': dateEnd}}]}
    tweets = list(tweetsDB.tweets.find(query))
    tweets.sort(key=lambda tweet: tweet['time'], reverse=True)
    return tweets


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
        user_info = getStatsPerUser(username)

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

        print(result)

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
    result['count_ratio'] = calcRatio(result['bull_unique'], result['bear_unique'])
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
    function = '1'
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
