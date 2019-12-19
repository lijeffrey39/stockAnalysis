import datetime
import time
from random import shuffle

import requests
from dateutil import parser
from selenium import webdriver

from bs4 import BeautifulSoup

from . import scroll
from .fileIO import *
from .helpers import (convertToEST,
                      customHash,
                      endDriver,
                      getActualAllStocks)
from .hyperparameters import constants
from .messageExtract import *
from .stockPriceAPI import *
from .stockAnalysis import getTopStocks


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


# Handles inserting coreInfo into mongodb
# if reanlyze, assumes user is already in db so need to update coreinfo
def insertUpdateError(coreInfo, reAnalyze, updateUser):
    analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
    if (reAnalyze is False and updateUser is False):
        analyzedUsers.insert_one(coreInfo)
    else:
        updateQuery = {'_id': coreInfo['_id']}
        newCoreInfo = {'$set': coreInfo}
        analyzedUsers.update_one(updateQuery, newCoreInfo)


# Checks whether to parse user
# Can parse/analyze users if it is set to true
def shouldParseUser(username, reAnalyze, updateUser):
    analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
    if (reAnalyze is False and updateUser is False and
        analyzedUsers.count_documents({'_id': username}) != 0):
        return None

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
    if (findNewUsers):
        updateUserNotAnalyzed()
        return

    cursor = None
    # Find all tweets this user posted again up till last time
    if (updateUser):
        analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
        dateStart = convertToEST(datetime.datetime.now()) - datetime.timedelta(days=7)
        query = {"$and": [{'error': ''},
                          {'last_updated': {'$lte': dateStart}}]}
        cursor = analyzedUsers.find(query)
    elif (reAnalyze):
        analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
        query = {"$and": [{'error': {'$ne': ''}}, 
                          {'error': {'$ne': 'Not enough ideas'}},
                        #   {'error': {'$ne': "'user'"}},
                          {'error': {'$ne': "User doesn't exist"}},
                          {'error': {'$ne': "User has no tweets"}}]}
                        #   {'error': {'$ne': "Scroll for too long"}},]}
        cursor = analyzedUsers.find(query)
    else:
        analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
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
        return newL

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
    start_date = convertToEST(datetime.datetime(2019, 2, 1))
    # if (cursor.count() != 0 and 'last_updated' in cursor[0] and cursor[0]['error'] == ''):
    #     start_date = cursor[0]['last_updated']
    #     print('FOUND', start_date)
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

    messages = driver.find_elements_by_class_name(constants['messageStreamAttr'])
    if (len(messages) == 0):
        endDriver(driver)
        end = time.time()
        return ('', 'User has no tweets', end - start)

    try:
        scroll.scrollFor(driver, current_span_hours)
    except Exception as e:
        endDriver(driver)
        end = time.time()
        return ('', str(e), end - start)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    end = time.time()
    print('Parsing user took %d seconds' % (end - start))
    endDriver(driver)
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
    user_block = soup.find('div', attrs={'class': constants['html_class_user_div']})
    plus = user_block.find('div', attrs={'class': constants['html_class_plus']})
    official = user_block.find('span', attrs={'class': constants['html_class_official']})
    premium = user_block.find('a', attrs={'class': constants['html_class_premium_room']})

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
        isBull = isBullMessage(m)
        likeCnt = likeCount(m)
        commentCnt = commentCount(m)
        symbols = findSymbol(textFound, allSymbols)

        # Only care about tweets that are labeled
        if (len(symbols) == 0):
            continue
        print(symbols)
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
    result['totalTweets'] = len(tweets)
    functions = constants['functions']

    keys = ['returnCloseOpen', 'returnTimePrice', 'numCloseOpen', 
            'numTimePrice', 'numPredictions', 'returnUnique',
            'numUnique', 'totalLikes', 'totalComments']
    
    for k in allKeys:
        result[k] = {}
        for f in functions:
            result[k][f] = {}
            result[k][f]['bull'] = 0
            result[k][f]['bear'] = 0

    result['perStock'] = {}
    uniqueSymbols = set(list(map(lambda tweet: tweet['symbol'], tweets)))
    for symbol in uniqueSymbols:
        result['perStock'][symbol] = {}
        for k in allKeys:
            result['perStock'][symbol][k] = {}
            for f in functions:
                result['perStock'][symbol][k][f] = {}
                result['perStock'][symbol][k][f]['bull'] = 0
                result['perStock'][symbol][k][f]['bear'] = 0

    return result


# Update feature results for a user given close open prices
def updateUserFeatures(result, time, symbol, isBull, seenTweets):
    # edge case
    if (symbol == 'AMRN' and time.month == 11 and time.day == 13 or
        symbol == 'AGRX' and time.month == 10 and time.day == 29):
        return

    if (inTradingDay(time) is False):
        return

    timePrice = getPrice(symbol, time)
    if (timePrice is None):
        return

    closeOpen = averagedOpenClose(symbol, time)
    allTop = getTopStocks(100)
    if (symbol not in allTop):
        closeOpen = getUpdatedCloseOpen(symbol, time)
    # print(symbol, isBull, closeOpen, time, timePrice)
    if (closeOpen is None):
        return

    pChangeCloseOpen = closeOpen[2]
    pChangeTimePrice = round(((closeOpen[1] - timePrice) / timePrice) * 100, 3)
    correctPredCloseOpen = (isBull and pChangeCloseOpen >= 0) or (isBull is False and pChangeCloseOpen < 0)
    correctPredTimePrice = (isBull and pChangeTimePrice >= 0) or (isBull is False and pChangeTimePrice < 0)
    correctNumCloseOpen = 1 if correctPredCloseOpen else 0
    correctNumTimePrice = 1 if correctPredTimePrice else 0
    pReturnCloseOpen = abs(pChangeCloseOpen) if correctPredCloseOpen else -abs(pChangeCloseOpen)
    pReturnTimePrice = abs(pChangeTimePrice) if correctNumTimePrice else -abs(pChangeTimePrice)
    values = [pReturnCloseOpen, pReturnTimePrice, correctNumCloseOpen, correctNumTimePrice, 1]

    if (abs(pReturnTimePrice) > 50):
        print(symbol, isBull, closeOpen, time, timePrice)

    seenTweetString = time.strftime("%Y-%m-%d ") + symbol
    if (seenTweetString not in seenTweets):
        seenTweets.add(seenTweetString)
        values.extend([pReturnCloseOpen, correctNumCloseOpen])
    else:
        values.extend([0, 0])

    keys = ['ReturnCloseOpen', 'ReturnTimePrice', 'NumCloseOpen',
            'NumTimePrice', 'Predictions', 'ReturnUnique', 'NumUnique']
    mappedKeys = list(map(lambda key: ('bull' if (isBull) else 'bear') + key, keys))

    count = 0
    for k in mappedKeys:
        result[k] += values[count]
        result['perStock'][symbol][k] += values[count]
        count += 1


# Returns stats from user info for prediction
def getStatsPerUser(user):
    analyzedUsersDB = constants['db_user_client'].get_database('user_data_db')
    stocks = getTopStocks()
    userAccuracy = analyzedUsersDB.user_accuracy_v2
    result = userAccuracy.find({'_id': user})
    if (result.count() != 0):
        return result[0]

    tweetsDB = constants['stocktweets_client'].get_database('tweets_db')
    labeledTweets = tweetsDB.tweets.find({"$and": [{'user': user},
                                         {'symbol': {"$ne": ''}},
                                         {'symbol': {'$ne': None}},
                                         {'symbol': {
                                             '$in': stocks
                                         }},
                                         {"$or": [
                                            {'isBull': True},
                                            {'isBull': False}
                                         ]}]})

    labeledTweets = list(map(lambda tweet: tweet, labeledTweets))
    result = initializeResult(labeledTweets, user)
    seenTweets = set([])
    print(len(labeledTweets))
    # for t in labeledTweets:
    #     print(t['time'], t['symbol'])
    # return

    # Loop through all tweets made by user and feature extract per user
    for tweet in labeledTweets:
        time = tweet['time']
        symbol = tweet['symbol']
        isBull = tweet['isBull']
        if (symbol in top100):
            updateUserFeatures(result, time, symbol, isBull, seenTweets)

    # Remove symbols that user didn't have valid tweets about
    for symbol in list(result['perStock'].keys()):
        if (result['perStock'][symbol]['bullPredictions'] == 0 and
           result['perStock'][symbol]['bearPredictions'] == 0):
            del result['perStock'][symbol]

    userAccuracy.insert_one(result)

    # currTime = convertToEST(datetime.datetime.now())
    # lastTime = {'_id': user, 'time': currTime}
    # analyzedUsersDB.last_user_accuracy_calculated.insert_one(lastTime)
    return result


# Returns all information regarding a user
# Need better error handling
# Save this in database so don't need to make to 2 calls to consolidate data
def getAllUserInfo(username):
    userInfoDB = constants['db_user_client'].get_database('user_data_db').users
    checkUserInfo = userInfoDB.find({'_id': username})

    # Need to parse the user for basic information
    if (checkUserInfo.count() == 0):
        return {}
    userInfo = checkUserInfo[0]

    # Need to reanalyze user
    if (userInfo['error'] != ''):
        return {}
    result = getStatsPerUser(username)
    if (len(result) == 0):
        return {}

    totalPredictions = result['bullPredictions'] + result['bearPredictions']
    totalCorrect = result['bullNumCloseOpen'] + result['bearNumCloseOpen']
    if (totalPredictions == 0):
        return {}

    result['accuracy'] = totalCorrect * 1.0 / totalPredictions
    result['totalReturn'] = result['bullReturnCloseOpen'] + result['bearReturnCloseOpen']
    result['followers'] = userInfo['followers']
    result['following'] = userInfo['following']
    result['ideas'] = userInfo['ideas']
    result['like_count'] = userInfo['like_count']
    result['user_status'] = userInfo['user_status']
    return result


# Finds users that haven't been calculated yet
def calculateNewUserInfo():
    analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
    query = {"$and": [{'error': ''}, {'last_updated': {'$exists': True}}]}
    cursor = analyzedUsers.find(query)
    users = list(map(lambda document: document['_id'], cursor))
    print(len(users))
    shuffle(users)
    for u in users:
        print(u)
        getAllUserInfo(u)
