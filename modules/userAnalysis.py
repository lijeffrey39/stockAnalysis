import datetime
import time
import math
from random import shuffle

import requests
from dateutil import parser
from selenium import webdriver

from bs4 import BeautifulSoup

from . import scroll
# from .fileIO import *
from .helpers import (convertToEST,
                      customHash,
                      endDriver,
                      getActualAllStocks,
                      findWeight,
                      findJoinDate,
                      getAllStocks,
                      readPickleObject)
from .hyperparameters import constants
from .messageExtract import *
from .stockPriceAPI import (findCloseOpen,
                            inTradingDay,
                            getUpdatedCloseOpen,
                            findDateString,
                            findCloseOpenCached)
from .stockAnalysis import (getTopStocks)


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


# Handles inserting coreInfo into mongodb
# if reanlyze, assumes user is already in db so need to update coreinfo
def insertUpdateError(coreInfo, reAnalyze, updateUser):
    analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
    result = analyzedUsers.find_one({'_id': coreInfo['_id']})
    if (result):
        updateQuery = {'_id': coreInfo['_id']}
        newCoreInfo = {'$set': coreInfo}
        analyzedUsers.update_one(updateQuery, newCoreInfo)
    else:
        analyzedUsers.insert_one(coreInfo)


# Checks whether to parse user
# Can parse/analyze users if it is set to true
def shouldParseUser(username, reAnalyze, updateUser):
    analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
    if (reAnalyze is False and updateUser is False and
        analyzedUsers.count_documents({'_id': username}) != 0):
        return None

    if (updateUser):
        query = {'_id': username}
        result = analyzedUsers.find_one(query)
        if (result):
            result['last_updated'] = convertToEST(datetime.datetime.now())
            return result
            # Already updated recently
            # if (lastUpdated > dateStart):
            #     return None

    if (updateUser):
        print("should not get here")
    (coreInfo, error) = findUserInfo(username)
    currTime = convertToEST(datetime.datetime.now())

    # If API is down/user doesnt exist
    if (not coreInfo):
        errorMsg = "User doesn't exist / API down"
        userInfoError = {'_id': username,
                         'error': errorMsg,
                         'last_updated': currTime}
        insertUpdateError(userInfoError, reAnalyze, updateUser)
        return None

    # If exceed the 200 limited API calls
    if (coreInfo['ideas'] == -1):
        (coreInfo, errorMsg) = findUserInfoDriver(username)
        if (not coreInfo):
            userInfoError = {'_id': username,
                             'error': errorMsg,
                             'last_updated': currTime}
            insertUpdateError(userInfoError, reAnalyze, updateUser)
            return None

    coreInfo['last_updated'] = currTime
    coreInfo['_id'] = username

    # If number of ideas are < the curren min threshold
    if (coreInfo['ideas'] < constants['min_idea_threshold']):
        coreInfo['error'] = 'Not enough ideas'
        insertUpdateError(coreInfo, reAnalyze, updateUser)
        return None

    coreInfo['error'] = ""
    return coreInfo


# Returns list of all users to analyze
def findUsers(reAnalyze, findNewUsers, updateUser):
    # Find new users to analyze from all tweets
    # if (findNewUsers):
    #     updateUserNotAnalyzed()
    #     return


    analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
    # res = analyzedUsers.aggregate([{'$group' : { '_id' : '$error', 'count' : {'$sum' : 1}}}, { "$sort": { "count": 1 } },])
    # for i in res:
    #     print(i)
    # return
    cursor = None
    # Find all tweets this user posted again up till last time
    if (updateUser):
        dateStart = convertToEST(datetime.datetime.now()) - datetime.timedelta(days=14)
        query = {'last_updated': {'$lte': dateStart}, 'error': ''}
        cursor = analyzedUsers.find(query)
    elif (reAnalyze):
        query = {"$or": [
            # {'error': 'Not enough ideas'},
                        # fix these too
                        # Message: session not created: This version of ChromeDriver only supports Chrome version 78
                        # ,
                        #   {'error': {'$ne': "User doesn't exist"}},
                          {'error': {'$ne': ""}},
                        #   {'error': {'$ne': "User doesn't exist / API down"}},
                        #   {'error': 'User has no tweets'}
                        #   {'error': {'$ne': "Empty result list"}}
                          ]}
        cursor = analyzedUsers.find(query)
    else:
        cursor = analyzedUsers.find()
        users = list(map(lambda document: document['_id'], cursor))
        setUsers = set(users)

        allUsers = constants['db_client'].get_database('stocktwits_db').users_not_analyzed
        cursor = allUsers.find()
        allNewUsers = list(map(lambda document: document['_id'], cursor))
        setAllUsers = set(allNewUsers)

        toBeFound = setAllUsers - setUsers
        newL = sorted(list(toBeFound))
        print(len(newL))
        shuffle(newL)

        dateStart = convertToEST(datetime.datetime.now()) - datetime.timedelta(days=30)
        query = {"$or": [{'error': "Len of messages was 0 ???"},
                          {'error': "Message: session not created: This version of ChromeDriver only supports Chrome version 79\n"},
                          {'error': 'Message: script timeout\n  (Session info: headless chrome=83.0.4103.97)\n',},
                          {'error': 'Message: unknown error: failed to close window in 20 seconds\n  (Session info: headless chrome=83.0.4103.97)\n'},
                          {'error': 'Empty result list'},
                          {'error': 'Message: unknown error: unable to discover open pages\n'}]}
        cursor = analyzedUsers.find(query)
        users = list(map(lambda document: document['_id'], cursor))
        users.extend(newL)
        res = list(set(users))
        return res

    users = list(map(lambda document: document['_id'], cursor))
    shuffle(users) 
    return users

def parseOldUsers(daysback):
    # Find new users to analyze from all tweets
    updateUserNotAnalyzed()

    cursor = None
    analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
    dateStart = convertToEST(datetime.datetime.now()) - datetime.timedelta(days=daysback)
    query = {"$and": [{'error': ''},
                        {'last_updated': {'$lte': dateStart}}]}
    cursor = analyzedUsers.find(query)
    users = list(map(lambda document: document['_id'], cursor))
    shuffle(users)
    return users


# Return soup object page of that user
def findPageUser(username):
    analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
    cursor = analyzedUsers.find({'_id': username})
    driver = None
    try:
        driver = webdriver.Chrome(executable_path=constants['driver_bin'],
                                  options=constants['chrome_options'])
        driver.set_page_load_timeout(90)
    except Exception as e:
        return ('', str(e), 0)

    # Hardcoded to the first day we have historical stock data
    start_date = convertToEST(datetime.datetime(2019, 6, 1))
    if (cursor.count() != 0 and 'last_updated' in cursor[0] and cursor[0]['error'] == ''):
        start_date = cursor[0]['last_updated']
        print('FOUND', start_date)
    current_date = convertToEST(datetime.datetime.now())
    date_span = current_date - start_date
    current_span_hours = 24 * date_span.days + int(date_span.seconds/3600)
    start = time.time()
    url = 'https://stocktwits.com/%s' % username
    try:
        driver.get(url)
    except Exception as e:
        end = time.time()
        endDriver(driver)
        return ('', str(e), end - start)

    # messages = driver.find_elements_by_class_name(constants['messageStreamAttr'])
    # print(len(messages))
    # if (len(messages) == 0):
    #     endDriver(driver)
    #     end = time.time()
    #     return ('', 'User has no tweets', end - start)

    try:
        scroll.scrollFor(driver, current_span_hours)
    except Exception as e:
        try:
            endDriver(driver)
        except Exception as e1:
            end = time.time()
            return ('', str(e1), end - start)
        end = time.time()
        return ('', str(e), end - start)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    end = time.time()
    print('Parsing user took %d seconds' % (end - start))
    try:
        endDriver(driver)
    except Exception as e:
        return ('', str(e), end - start)
    return (soup, '', (end - start))


# Gets initial information for user from selenium
def findUserInfoDriver(username):
    driver = None
    try:
        driver = webdriver.Chrome(executable_path=constants['driver_bin'],
                                  options=constants['chrome_options'])
        driver.set_page_load_timeout(90)
    except Exception as e:
        endDriver(driver)
        return (None, str(e))

    url = 'https://stocktwits.com/%s' % username
    try:
        driver.get(url)
    except Exception as e:
        endDriver(driver)
        return (None, str(e))

    user_info_dict = dict()
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    ideas = soup.find_all('h2', attrs={'class': constants['ideaAttr']})
    memberTextArray = soup.find_all('span', attrs={'class': constants['html_class_user_info']})

    if (len(ideas) == 0):
        endDriver(driver)
        return (None, "User doesn't exist")

    # find user type, will be stored in bitwise fashion
    # plus is bit 3, lifetime is bit 2, official is bit 1, premium bit 0
    # user_block = soup.find('div', attrs={'class': constants['html_class_user_div']})
    plus = soup.find('div', attrs={'class': 'lib_XwnOHoV lib_3UzYkI9 lib_lPsmyQd lib_2TK8fEo'})
    official = soup.find('i', attrs={'class': 'lib_3rvh3qQ lib_AHwHgd8 st_15f6hU9 st_2Y5n_y3'})
    premium = soup.find('a', attrs={'class': 'st_3yezEtB st_3PVuCod st_bPzIqx3 st_2t3n5Ue st_1VMMH6S st_1jzr122 st_wva9-Y8 st_2mehCkH st_8u0ePN3'})

    status = 0
    if (plus):
        status += 8 if plus.text == 'Lifetime' else 4
    status += 2 if official else 0
    status += 1 if premium else 0

    if (len(memberTextArray) >= 1):
        try:
            joinDateArray = memberTextArray[-1].text.split(' ')[2:]
            joinDate = ' '.join(map(str, joinDateArray))
            dateTime = parser.parse(joinDate).strftime("%Y-%m-%d")
            user_info_dict['join_date'] = dateTime
        except Exception as e:
            endDriver(driver)
            return (None, str(e))

    user_info_dict['ideas'] = parseKOrInt(ideas[0].text)
    user_info_dict['following'] = parseKOrInt(ideas[1].text)
    user_info_dict['followers'] = parseKOrInt(ideas[2].text)
    user_info_dict['like_count'] = parseKOrInt(ideas[3].text)
    user_info_dict['user_status'] = status

    endDriver(driver)
    return (user_info_dict, '')


# Gets initial information for user from API
def findUserInfo(username):
    response = requests.get(url='https://api.stocktwits.com/api/2/streams/user/%s.json' % username)

    # If exceed the 200 limited API calls
    try:
        responseStatus = response.json()['response']['status']
        if (responseStatus == 429):
            return ({'ideas': -1}, '')
    except Exception as e:
        return (None, str(e))

    try:
        info = response.json()['user']
    except Exception as e:
        return (None, str(e))

    user_info_dict = dict()
    fields = {'join_date', 'followers', 'following', 'ideas', 'like_count'}
    for f in fields:
        user_info_dict[f] = info[f]

    status = 0
    if (info["plus_tier"] == 'life'): status += 8
    if (info["plus_tier"] == 'month'): status += 4
    if (info["official"]): status += 2
    if (info["premium_room"] != ""): status += 1

    user_info_dict['user_status'] = status
    return (user_info_dict, '')


def parseUserData(username, soup):
    res = []
    allSymbols = getActualAllStocks()
    messages = soup.find_all('div',
                             attrs={'class': constants['messageStreamAttr']})
    for m in messages:
        t = m.find('div', {'class': constants['timeAttr']}).find_all('a')
        # t must be length of 2, first is user, second is date
        if (t is None):
            continue

        allT = m.find('div', {'class': constants['messageTextAttr']})
        allText = allT.find_all('div')
        textFound = allText[1].find('div').text  # No post processing
        if (textFound == 'Bearish' or textFound == 'Bullish'):
            textFound = allText[3].find('div').text
        isBull = isBullMessage(m)
        likeCnt = likeCount(m)
        commentCnt = commentCount(m)
        symbols = findSymbol(textFound, allSymbols)

        # Only care about tweets that are labeled
        if (len(symbols) == 0):
            continue
        dateString = ""

        # Handle edge cases
        if (textFound == 'Lifetime' or textFound == 'Plus'):
            textFound = allText[4].find('div').text

        if (t[1].text == ''):
            dateString = t[2].text
        else:
            dateString = t[1].text

        (dateTime, errorMsg) = findDateTime(dateString)
        if (errorMsg != ""):
            print(errorMsg)
            continue

        dateAsString = dateTime.strftime("%Y-%m-%d %H:%M:%S")
        hashString = textFound + dateAsString + username
        hashID = customHash(hashString)

        cur_res = {}
        cur_res['_id'] = hashID
        cur_res['symbol'] = symbols[0]
        cur_res['user'] = username
        cur_res['time'] = dateTime
        cur_res['isBull'] = isBull
        cur_res['likeCount'] = likeCnt
        cur_res['commentCount'] = commentCnt
        cur_res['messageText'] = textFound
        res.append(cur_res)
    return res


# extract status information from bits
def getUserStatus(status):
    return {'lifetime': bool(status & 8), 'plus': bool(status & 4),
            'official': bool(status & 2), 'premium': bool(status & 1)}


# Loop through all stock tweets and finds users that are not already in db
def updateUserNotAnalyzed():
    allUsers = constants['db_client'].get_database('stocktwits_db').users_not_analyzed
    cursor = allUsers.find()
    users = set(list(map(lambda document: document['_id'], cursor)))

    userSet = set([])
    tweets = constants['stocktweets_client'].get_database('tweets_db').tweets.find()
    count = 0
    for doc in tweets:
        count += 1
        if (count % 10000 == 0):
            print(count)
        currUserName = doc['user']
        if (currUserName not in users):
            userSet.add(currUserName)

    listNewUsers = list(userSet)
    listNewUsers.sort()
    for user in listNewUsers:
        allUsers.insert_one({'_id': user})
    print("Finished Updating:", len(listNewUsers))


# ------------------------------------------------------------------------
# -------------------- User Prediction Functions -------------------------
# ------------------------------------------------------------------------


# Initialize user info result for predicting
# For weighted features, weighted based on x^4 curve
# As it gets close to the 4pm, tweets are weigted more
# Ex. 2.4 hours before 4pm, or around 1:30, tweet worth 67%
def initializeResult(tweets, user):
    result = {}
    result['_id'] = user
    functions = constants['functions']
    keys = ['returnCloseOpen', 'numCloseOpen', 
            'numPredictions', 'returnUnique',
            'numUnique', 'numUniquePredictions', 
            'returnUniqueLog']

    for f in functions:
        result[f] = {}
        for k in keys:
            result[f][k] = {}
            result[f][k]['bull'] = 0
            result[f][k]['bear'] = 0

    result['perStock'] = {}
    uniqueSymbols = set(list(map(lambda tweet: tweet['symbol'], tweets)))
    for symbol in uniqueSymbols:
        result['perStock'][symbol] = {}
        for f in functions:
            result['perStock'][symbol][f] = {}
            for k in keys:
                result['perStock'][symbol][f][k] = {}
                result['perStock'][symbol][f][k]['bull'] = 0
                result['perStock'][symbol][f][k]['bear'] = 0
    return result


# Initialize per stock features 
def initializePerStockFeatures(symbol, result):
    result['perStock'][symbol] = {}
    keys = ['correct_predictions', 'num_predictions',
            'unique_correct_predictions', 'unique_num_predictions', 
            'unique_return', 'unique_return_log', 'unique_return_w1']
    for k in keys:
        result['perStock'][symbol][k] = {}
        result['perStock'][symbol][k]['bull'] = 0
        result['perStock'][symbol][k]['bear'] = 0


# Update feature results for a user given close open prices
# Not using functions for now ('1' by default)
# TODO: pReturnCloseOpen look at price at time of posting
def updateUserFeatures(result, tweet, uniqueStocks):
    cached_prices = constants['cached_prices']
    time = tweet['time']
    symbol = tweet['symbol']
    isBull = tweet['isBull']
    label = 'bull' if (isBull) else 'bear'

    if (symbol == ''):
        return

    closeOpen = findCloseOpenCached(symbol, time, cached_prices)
    if (closeOpen is None):
        return

    percent_change = closeOpen[2]
    correct_prediction = (isBull and percent_change >= 0) or (isBull is False and percent_change <= 0)
    correct_prediction_num = 1 if correct_prediction else 0

    # Initialize perstock object
    if (symbol not in result['perStock']):
        initializePerStockFeatures(symbol, result)

    result['correct_predictions'][label] += correct_prediction_num
    result['perStock'][symbol]['correct_predictions'][label] += correct_prediction_num
    result['num_predictions'][label] += 1
    result['perStock'][symbol]['num_predictions'][label] += 1

    w = findWeight(time, 'log(x)')
    # For unique predictions per day, only count (bull/bear) if its majority
    time_string = symbol + ' ' + findDateString(time, cached_prices)
    if (time_string in uniqueStocks):
        if (isBull == uniqueStocks[time_string]['last_prediction']):
            uniqueStocks[time_string]['count'] += w
    else:
        time_result = {'time': time, 
                    'symbol': symbol, 
                    'percent_change': percent_change,
                    'last_prediction': isBull,
                    'count': w}
        uniqueStocks[time_string] = time_result


# Returns stats from user info for prediction
def getStatsPerUser(user):
    analyzedUsersDB = constants['db_user_client'].get_database('user_data_db')
    userAccuracy = analyzedUsersDB.user_accuracy_actual
    result = userAccuracy.find({'_id': user})
    if (result.count() != 0):
        return result[0]

    tweetsDB = constants['stocktweets_client'].get_database('tweets_db').tweets
    labeledTweets = tweetsDB.find({"$and": [{'user': user},
                                            {'symbol': {"$ne": ''}},
                                            {'symbol': {'$ne': None}},
                                            {"$or": [
                                                {'isBull': True},
                                                {'isBull': False}
                                            ]}]})

    labeledTweets = list(map(lambda tweet: tweet, labeledTweets))
    labeledTweets.sort(key=lambda x: x['time'], reverse=True)
    result = initializeResult(labeledTweets, user)
    uniqueStocks = {}

    # Loop through all tweets made by user and feature extract per user
    cached_prices = readPickleObject('newPickled/averaged.pkl')
    for tweet in labeledTweets:
        updateUserFeatures(result, tweet, uniqueStocks, cached_prices)

    # Update unique predictions per day features
    for time_string in uniqueStocks:
        symbol = uniqueStocks[time_string]['symbol']
        times = uniqueStocks[time_string]['times']
        times.sort()
        mid = len(times) // 2
        average_time = None
        if (len(times) % 2 == 0):
            delta = (times[mid] - times[mid - 1]) / 2
            average_time = times[mid - 1] + delta
        else:
            average_time = times[mid]
        
        # Find whether tweet was bull or bear based on majority
        label = 'bull'
        if (uniqueStocks[time_string]['bear'] > uniqueStocks[time_string]['bull']):
            label = 'bear'
        if (uniqueStocks[time_string]['bear'] == uniqueStocks[time_string]['bull']):
            label = 'both'
        keys = ['returnUnique', 'numUnique', 'numUniquePredictions']
        functions = constants['functions']

        for k in keys:
            for f in functions:
                w = findWeight(average_time, f)
                val = w * uniqueStocks[time_string][k]
                if (label == 'both'):
                    result[f][k]['bear'] += val
                    result[f][k]['bull'] += val
                    result['perStock'][symbol][f][k]['bear'] += val
                    result['perStock'][symbol][f][k]['bull'] += val
                else:
                    result[f][k][label] += val
                    result['perStock'][symbol][f][k][label] += val

        # return unique (log)
        for f in functions:
            w = findWeight(average_time, f)
            unique_return = uniqueStocks[time_string]['returnUnique']
            if (label == 'both'):
                num_labels = len(times) // 2
                val = w * unique_return * (math.log10(num_labels) + 1)
                result[f]['returnUniqueLog']['bear'] += val
                result[f]['returnUniqueLog']['bull'] += val
                result['perStock'][symbol][f]['returnUniqueLog']['bear'] += val
                result['perStock'][symbol][f]['returnUniqueLog']['bull'] += val
            else:
                num_labels = uniqueStocks[time_string][label]
                val = w * unique_return * (math.log10(num_labels) + 1)
                result[f]['returnUniqueLog'][label] += val
                result['perStock'][symbol][f]['returnUniqueLog'][label] += val

        # print(average_time, symbol, uniqueStocks[time_string]['returnUnique'], result['1']['returnUnique']['bull'], result['1']['returnUnique']['bear'])

    # Remove symbols that user didn't have valid tweets about
    for symbol in list(result['perStock'].keys()):
        if (result['perStock'][symbol]['x']['numPredictions']['bull'] == 0 and
            result['perStock'][symbol]['x']['numPredictions']['bear'] == 0):
            del result['perStock'][symbol]

    # Update last updated time
    exists = userAccuracy.find({'_id': user})
    if (exists.count() != 0):
        return exists[0]
    userAccuracy.insert(result, check_keys=False)

    # Update last updated time
    last_calculated = analyzedUsersDB.last_user_accuracy_actual_calculated
    currTime = convertToEST(datetime.datetime.now())
    lastTime = {'_id': user, 'time': currTime}
    exists = last_calculated.find_one(lastTime)
    if (exists):
        updateQuery = {'_id': result['_id']}
        newCoreInfo = {'$set': lastTime}
        last_calculated.update_one(updateQuery, newCoreInfo)
    else:
        last_calculated.insert_one(lastTime)

    return result


# Returns all information regarding a user
# Need better error handling
# Save this in database so don't need to make to 2 calls to consolidate data
# def getAllUserInfo(username):
    # userInfo = checkUserInfo[0]
    # result = getStatsPerUser(username)
    # if (len(result) == 0):
    #     return {}

    # result['followers'] = userInfo['followers']
    # result['following'] = userInfo['following']
    # result['ideas'] = userInfo['ideas']
    # result['likeCount'] = userInfo['like_count']
    # result['userStatus'] = userInfo['user_status']
    # result['joinDate'] = findJoinDate(userInfo['join_date'])
    # return result


# Finds users that haven't been calculated yet
def calculateAllUserInfo():
    # Users that don't have errors
    analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
    time = datetime.datetime(2020, 6, 1)
    query = {"$and": [{'error': ''}, 
                      {'last_updated': {'$exists': True}},
                      {'last_updated': {'$gte': time}}]}
    cursor = analyzedUsers.find(query)
    users = list(map(lambda document: document['_id'], cursor))

    # Remove users that were recently parsed
    last_calculated = constants['db_user_client'].get_database('user_data_db').last_user_accuracy_actual_calculated
    query = {'time': {'$gte': datetime.datetime(2020, 6, 1)}}
    cursor = last_calculated.find(query)
    analyzed_already = list(map(lambda document: document['_id'], cursor))
    users = list(set(users) - set(analyzed_already))
    print(len(users))
    shuffle(users)
    for username in users:
        result = getStatsPerUser(username)
        if (len(result) == 0):
            continue
        print(username, result['1']['returnUniqueLog']['bull'] + result['1']['returnUniqueLog']['bear'])


# User Infos from saved file
def setupUserInfos(updateObject=False):
    print("Setup User Info")
    path = 'pickledObjects/userInfosV2.pkl'
    result = readPickleObject(path)
    if (updateObject is False):
        return result

    allUsers = constants['db_user_client'].get_database('user_data_db').users
    accuracy = constants['db_user_client'].get_database('user_data_db').user_accuracy_v2
    allUsersAccs = allUsers.find()
    modCheck = 0
    count = 0
    for user in allUsersAccs:
        userId = user['_id']
        count += 1
        if (userId in result):
            print('found', userId)
            continue
        if (accuracy.find_one({'_id': userId}) is None):
            print(userId)
            result[userId] = 1
            continue
        res = getAllUserInfo(user)
        print('new', userId)
        result[userId] = res
        modCheck += 1
        if (modCheck % 100 == 0):
            writePickleObject(path, result)
            modCheck = 0
            print(count)

    # result = {}
    # for symbol in stocks:
    #     print(symbol)
    #     accuracy = constants['db_user_client'].get_database('user_data_db').user_accuracy_v2
    #     allUsersAccs = accuracy.find({'perStock.' + symbol: {'$exists': True}})
    #     print(allUsersAccs.count())
    #     for user in allUsersAccs:
    #         if (user['_id'] not in result):
    #             print(user['_id'])
    #             result[user['_id']] = user

    writePickleObject(path, result)
    return result