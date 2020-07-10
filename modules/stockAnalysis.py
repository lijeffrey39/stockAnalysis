import datetime
from datetime import timedelta
import time
from random import shuffle
import pickle

from selenium import webdriver
from selenium.webdriver.common.keys import Keys

from bs4 import BeautifulSoup

from . import scroll
from .helpers import convertToEST, customHash, endDriver, readPickleObject, writePickleObject
from .hyperparameters import constants
from .messageExtract import *
from .stockPriceAPI import *


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


def getTopStocks(numStocks=100):
    sortedStockList = getSortedStocks()
    return sortedStockList[:numStocks]

def getSortedStocks():
    stockCounts = constants['db_client'].get_database(
        'stocktwits_db').stock_counts_150
    cursor = stockCounts.find()
    stocks = list(map(lambda document: document, cursor))
    newdict = sorted(stocks, key=lambda k: k['count'], reverse=True)
    newlist = list(map(lambda document: document['_id'], newdict))
    remove_list = ['MDR', 'I', 'HSGX', 'RTTR', 'UWT', 'JCP', 'SES', 'DWT', 'SPEX', 'RBZ', 'YUMA', 'BPMX', 'SNNA', 'PTIE', 'FOMX', 'TROV', 'HIIQ', 'S', 'XGTI', 'MDCO', 'NLNK', 'SSI', 'VLRX', 'ATIS', 'INNT', 'DCAR', 'CUR', 'AKS', 'FTNW', 'KEG', 'CNAT', 'MLNT', 'GNMX', 'AKRX', 'CLD', 'ECA', 'DCIX', 'PIR', 'DF', 'AXON', 'CIFS', 'XON', 'SBOT', 'KOOL', 'HAIR', 'ARQL', 'IPCI', 'ACHN', 'ABIL', 'RTN', 'AMR', 'FTR', 'DERM', 'CBS', 'OILU', 'JMU', 'CELG', 'DRYS', 'AGN', 'SBGL', 'UPL', 'VTL', 'BURG', 'DO', 'SN', 'PVTL', 'UTX', 'HEB', 'WFT', 'CY', 'SYMC', 'PTX', 'AKAO', 'AVP', 'GEMP', 'CBK', 'HABT', 'RARX', 'ORPN', 'IGLD', 'ROX', 'LEVB', 'CTRP', 'CARB', 'AAC', 'HK', 'CRZO', 'MNGA', 'PEGI', 'OHGI', 'ZAYO', 'GLOW', 'MLNX', 'COT', 'SORL', 'BBT', 'FGP', 'SGYP', 'STI', 'FCSC', 'NIHD', 'ONCE', 'ANFI', 'VSI', 'INSY', 'CVRS', 'GG', 'WIN', 'BRS', 'NVLN', 'EMES', 'CBLK', 'ARRY', 'ESV', 'HRS', 'APHB', 'RHT', 'CLDC', 'EPE', 'APC', 'ACET', 'DATA', 'SDLP', 'GHDX', 'OHRP', 'EDGE', 'DFRG', 'VSM', 'RGSE', 'ASNS', 'BSTI', 'CADC', 'MXWL', 'PETX', 'IMDZ', 'ATTU', 'RLM', 'OMED']
    res = [i for i in newlist if i not in remove_list] 
    return res

def stockcount1000daily(date, num):
    bad_stocks = ['JCP', 'INPX', 'LK', 'HTZ', None, 'SPEX', 'NNVC', 'HSGX', 'LGCY', 'YRIV', 'MLNT', 'IFRX', 'OBLN', 'MLNT', 'MDR', 'FLKS', 'RTTR', 'CORV', 'WORX', 'BRK.B']
    stock_counts_collection = constants['db_user_client'].get_database('user_data_db').daily_stockcount
    prevTime = datetime.datetime(date.year, date.month, date.day, 00, 00)- datetime.timedelta(days = 1)
    currTime = prevTime + datetime.timedelta(days = 1)
    dateString = date.strftime("%Y%m%d")
    print(dateString)
    print(prevTime)

    res = stock_counts_collection.find({'_id': dateString})
    print(res.count())
    if (res.count() != 0):
        print('EXISTS')
    else:
        tweets = constants['stocktweets_client'].get_database('tweets_db').tweets
        agg = tweets.aggregate([{ "$match": { "time" : { '$gte' : prevTime, '$lte': currTime } } }, {'$group' : { '_id' : '$symbol', 'count' : {'$sum' : 1}}}, { "$sort": { "count": 1 } }])
        countList = []
        for i in agg:
            countList.append(i)
        stock_counts_collection.insert_one({'_id': dateString, 'stocks': countList})

    test = stock_counts_collection.find({'_id': dateString})
    stock_list = test[0]['stocks']
    newdict = sorted(stock_list, key=lambda k: k['count'], reverse=True)
    filtered_dict = list(filter(lambda document: document['_id'] not in bad_stocks, newdict))
    newlist = list(map(lambda document: document['_id'], filtered_dict))
    result = newlist[:num]
    return result

def updateStockCount():
    currTime = datetime.datetime.now() - datetime.timedelta(days=21)
    prevTime = currTime - datetime.timedelta(days=60)
    analyzedUsers = constants['stocktweets_client'].get_database('tweets_db').tweets
    res = analyzedUsers.aggregate([{ "$match": { "time" : { '$gte' : prevTime, '$lte': currTime } } }, {'$group' : { '_id' : '$symbol', 'count' : {'$sum' : 1}}}, { "$sort": { "time": 1} }])
    for i in res:
        # query = {'_id': i['_id']}
        # newVal = {'$set': {'count30': i['count']}}
        # db.update_one(query, newVal)
        print(i)
        # db.insert({'_id': i['_id'], 'count': i['count']})

def updateStockCountPerWeek(curr_time):
    year_week = curr_time.isocalendar()[:2]
    year = year_week[0]
    week = year_week[1]
    year_week_id = str(year) + '_' + str(week)
    print(year_week_id)
    prev_time = curr_time - datetime.timedelta(days=14)
    stock_counts_collection = constants['db_client'].get_database('stocktwits_db').stock_counts_perweek_14
    result = stock_counts_collection.find({'_id': year_week_id})
    if (result.count() != 0):
        print('EXISTS')
        return

    tweets_collection = constants['stocktweets_client'].get_database('tweets_db').tweets
    res = tweets_collection.aggregate([{ "$match": { "time" : { '$gte' : prev_time, '$lte' : curr_time}}}, 
                                    {'$group' : { '_id' : '$symbol', 'count' : {'$sum' : 1}}}, 
                                    { "$sort": { "count": 1 } }])
    mapped_counts = list(map(lambda document: document, res))
    stock_counts_collection.insert({'_id': year_week_id, 'stocks': mapped_counts})


# Get top stocks for that week given a date
def getTopStocksforWeek(date, num):
    bad_stocks = ['JCP', 'INPX', 'LK', 'HTZ', None, 'SPEX', 'NNVC', 'HSGX', 'LGCY', 'YRIV', 'MLNT', 'IFRX', 'OBLN', 'MLNT', 'MDR', 'FLKS', 'RTTR', 'CORV', 'WORX']
    path = 'newPickled/stock_counts_14.pkl'
    cached_stockcounts = readPickleObject(path)
    year_week = date.isocalendar()[:2]
    year = year_week[0]
    week = year_week[1]
    year_week_id = str(year) + '_' + str(week)

    stock_list = []
    if (year_week_id in cached_stockcounts):
        stock_list = cached_stockcounts[year_week_id]
    else:
        db = constants['db_client'].get_database('stocktwits_db').stock_counts_perweek_14
        cursor = db.find({"_id" : year_week_id})
        if (cursor.count() == 0):
            return None
        stock_list = cursor[0]['stocks']
        cached_stockcounts[year_week_id] = stock_list
        writePickleObject(path, cached_stockcounts)

    newdict = sorted(stock_list, key=lambda k: k['count'], reverse=True)
    filtered_dict = list(filter(lambda document: document['_id'] not in bad_stocks, newdict))
    test = list(map(lambda document: (document['_id'], document['count']), filtered_dict))
    newlist = list(map(lambda document: document['_id'], filtered_dict))
    result = newlist[:num]
    second_list = ['SPY', 'TSLA', 'IBIO', 'AYTU', 'XSPA', 'GNUS', 'SPCE', 'INO', 'CODX', 'BA', 'AAPL', 
        'FCEL', 'AMD', 'SRNE', 'MARK', 'B', 'NIO', 'ONTX', 'ROKU', 'INPX', 
        'ACB', 'AMZN', 'SHLL', 'WKHS', 'BIOC', 'MVIS', 'DIS', 'VXRT', 'BYND', 'JNUG', 
        'TTOO', 'TVIX', 'TOPS', 'VTIQ', 'VBIV', 'TBLT', 'ADXS', 'AAL', 'CLVS', 'SHIP', 'GHSI', 
        'AMRN', 'UGAZ', 'AIM', 'ZOM', 'GILD', 'VISL', 'FB', 'HTBX', 'EROS', 'KTOV', 'TTNP', 
        'TNXP', 'MSFT', 'ZM', 'UAVS', 'DGLY', 'QQQ', 'BNGO', 'NFLX', 'NVAX', 'MRNA', 
        'USO', 'MFA', 'IDEX', 'BB', 'BABA', 'CCL', 'OPK', 'NOVN', 'SHOP', 'ENPH', 'BCRX', 
        'DK', 'SPEX', 'BYFC', 'OCGN', 'WTRH', 'AUPH', 'MNKD', 'FMCI', 'I', 'IZEA', 
        'NNVC', 'UBER', 'CEI', 'NCLH', 'NVDA', 'D', 'SQ', 'OPGN', 'NAK']
    result = list(set(result+second_list))
    from random import shuffle
    shuffle(result)
    return result


# Get top stocks for that week given a date
def getTopStocksCached(date, num, cached_stockcounts):
    bad_stocks = ['JCP', 'INPX', 'LK', 'HTZ', None, 'SPEX', 'NNVC', 'HSGX', 'LGCY', 'YRIV', 'MLNT', 'IFRX', 'OBLN', 'MLNT', 'MDR', 'FLKS', 'RTTR', 'CORV', 'WORX']
    path = 'newPickled/stock_counts_14.pkl'
    year_week = date.isocalendar()[:2]
    year = year_week[0]
    week = year_week[1]
    year_week_id = str(year) + '_' + str(week)

    stock_list = []
    if (year_week_id in cached_stockcounts):
        stock_list = cached_stockcounts[year_week_id]
    else:
        db = constants['db_client'].get_database('stocktwits_db').stock_counts_perweek_14
        cursor = db.find({"_id" : year_week_id})
        if (cursor.count() == 0):
            return None
        stock_list = cursor[0]['stocks']
        cached_stockcounts[year_week_id] = stock_list
        writePickleObject(path, cached_stockcounts)

    stock_list.sort(key=lambda k: k['count'], reverse=True)
    filtered_dict = list(filter(lambda document: document['_id'] not in bad_stocks and document['_id'] in constants['top_stocks'], stock_list[:150]))
    # test = list(map(lambda document: (document['_id'], document['count']), filtered_dict))
    result = list(map(lambda document: document['_id'], filtered_dict[:num]))
    second_list = ['SPY', 'TSLA', 'IBIO', 'AYTU', 'XSPA', 'GNUS', 'SPCE', 'INO', 'CODX', 'BA', 'AAPL', 
        'FCEL', 'AMD', 'SRNE', 'MARK', 'B', 'NIO', 'ONTX', 'ROKU', 'INPX', 
        'ACB', 'AMZN', 'SHLL', 'WKHS', 'BIOC', 'MVIS', 'DIS', 'VXRT', 'BYND', 'JNUG', 
        'TTOO', 'TVIX', 'TOPS', 'VTIQ', 'VBIV', 'TBLT', 'ADXS', 'AAL', 'CLVS', 'SHIP', 'GHSI', 
        'AMRN', 'UGAZ', 'AIM', 'ZOM', 'GILD', 'VISL', 'FB', 'HTBX', 'EROS', 'KTOV', 'TTNP', 
        'TNXP', 'MSFT', 'ZM', 'UAVS', 'DGLY', 'QQQ', 'BNGO', 'NFLX', 'NVAX', 'MRNA', 
        'USO', 'MFA', 'IDEX', 'BB', 'BABA', 'CCL', 'OPK', 'NOVN', 'SHOP', 'ENPH', 'BCRX', 
        'DK', 'SPEX', 'BYFC', 'OCGN', 'WTRH', 'AUPH', 'MNKD', 'FMCI', 'I', 'IZEA', 
        'NNVC', 'UBER', 'CEI', 'NCLH', 'NVDA', 'D', 'SQ', 'OPGN', 'NAK']
    result = list(set(result+second_list))
    return result


# Return soup object page of that stock
def findPageStock(symbol, hoursBack):
    driver = None
    try:
        driver = webdriver.Chrome(executable_path=constants['driver_bin'],
                                  options=constants['chrome_options'],
                                  desired_capabilities=constants['caps'])
        driver.set_page_load_timeout(90)
    except Exception as e:
        return ('', str(e), 0)

    start = time.time()
    url = "https://stocktwits.com/symbol/%s" % symbol

    try:
        driver.get(url)
    except Exception as e:
        end = time.time()
        endDriver(driver)
        return ('', str(e), end - start)

    try:
        scroll.scrollFor(driver, hoursBack)
    except Exception as e:
        endDriver(driver)
        end = time.time()
        print(e)
        return ('', str(e), end - start)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    end = time.time()
    print('Parsing stock took %d seconds' % (end - start))
    endDriver(driver)
    return (soup, '', (end - start))


# Returns whether the stock should be parsed or not
# Will be parsed if it has been more than 12 hours since the last time it was
def shouldParseStock(symbol, dateString):
    db = constants['stocktweets_client'].get_database('stocks_data_db')
    # tweetsErrorCollection = db.stock_tweets_errors
    # if (tweetsErrorCollection.
    #         count_documents({'symbol': symbol,
    #                          'date': dateString}) != 0):
    #     return (False, 0)

    lastParsed = db.last_parsed
    lastTime = lastParsed.find({'_id': symbol})
    tweetsMapped = list(map(lambda document: document, lastTime))
    currTime = convertToEST(datetime.datetime.now())

    if (len(tweetsMapped) == 0):
        datePrev = parse(dateString)
        hoursBack = ((currTime - datePrev).total_seconds() / 3600.0) + 1
        print(currTime, datePrev, hoursBack)
        return (True, hoursBack)

    lastTime = tweetsMapped[0]['time']
    totalHoursBack = (currTime - lastTime).total_seconds() / 3600.0
    #totalHoursBack = 15
    print(currTime, lastTime, totalHoursBack)

    # need to continue to parse if data is more than 3 hours old
    if (totalHoursBack > constants['hoursBackToAnalyze']):
        return (True, totalHoursBack)
    else:
        return (False, 0)


# Updates the time this symbol was last parsed
def updateLastParsedTime(db, symbol):
    lastParsedDB = db.last_parsed
    lastTime = lastParsedDB.find({'_id': symbol})
    tweetsMapped = list(map(lambda document: document, lastTime))
    currTime = convertToEST(datetime.datetime.now())

    # If no last parsed time has been set yet
    if (len(tweetsMapped) == 0):
        lastParsedDB.insert_one({'_id': symbol, 'time': currTime})
    else:
        # update last parsed time as current time
        query = {'_id': symbol}
        newVal = {'$set': {'time': currTime}}
        lastParsedDB.update_one(query, newVal)


# Updates the time stamp for the last message for
# this symbol to find avoid overlap
def updateLastMessageTime(db, symbol, result):
    currLastTime = result[0]['time']
    lastMessageTimeCollection = db.last_message

    lastTime = lastMessageTimeCollection.find({'_id': symbol})
    timesMapped = list(map(lambda document: document, lastTime))

    # if no last message has been set yet
    if (len(timesMapped) == 0):
        newLastMessage = {'_id': symbol, 'time': currLastTime}
        lastMessageTimeCollection.insert_one(newLastMessage)
        return result

    lastTime = timesMapped[0]['time']
    newResult = []
    for tweet in result:
        # if (tweet['time'] > lastTime):
        newResult.append(tweet)

    query = {'_id': symbol}
    newVal = {'$set': {'time': currLastTime}}
    lastMessageTimeCollection.update_one(query, newVal)
    return newResult


def parseStockData(symbol, soup):
    res = []
    messages = soup.find_all('div',
                             attrs={'class': constants['messageStreamAttr']})

    # want to add new users to users_not_analyzed table
    for m in messages:
        t = m.find('div', {'class': constants['timeAttr']}).find_all('a')
        # length of 2, first is user, second is date
        if (t is None):
            continue

        allT = m.find('div', {'class': constants['messageTextAttr']})
        allText = allT.find_all('div')
        username = findUser(t[0])
        textFound = allText[1].find('div').text  # No post processing
        if (textFound == 'Bearish' or textFound == 'Bullish'):
            textFound = allText[3].find('div').text
        isBull = isBullMessage(m)
        likeCnt = likeCount(m)
        commentCnt = commentCount(m)
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
        cur_res['symbol'] = symbol
        cur_res['user'] = username
        cur_res['time'] = dateTime
        cur_res['isBull'] = isBull
        cur_res['likeCount'] = likeCnt
        cur_res['commentCount'] = commentCnt
        cur_res['messageText'] = textFound
        res.append(cur_res)
    return res


# Remove duplicate tweets from db given a symbol
def removeDuplicatesDB(symbol):
    return symbol


# Analyze errored stocks
def analyzeErrors(date):
    dateString = date.strftime("%Y-%m-%d")

    clientStockTweets = constants['stocktweets_client']
    db = clientStockTweets.get_database('stocks_data_db')
    tweetsErrorCollection = db.stock_tweets_errors
    allStocks = constants['db_client'].get_database('stocktwits_db').all_stocks
    errorsWithDate = tweetsErrorCollection.find({'date': dateString})
    errorsMapped = list(map(lambda document: document, errorsWithDate))

    # Remove stocks that are empty
    # for error in errorsMapped:
    #     print(error['error'])
    #     print(error['symbol'])
    #     if (error['error'] == 'Len of messages was 0 ???'):
    #         allStocks.delete_one({'_id': error['symbol']})
    #         tweetsErrorCollection.delete_one({'_id': error['_id']})

    return
