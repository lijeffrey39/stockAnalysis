import datetime
import time
from random import shuffle

from selenium import webdriver
from selenium.webdriver.common.keys import Keys

from bs4 import BeautifulSoup

from . import scroll
from .helpers import convertToEST, customHash, endDriver
from .hyperparameters import constants
from .messageExtract import *
from .stockPriceAPI import *


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


def getTopStocks(numStocks):
    stocks = ['AMD', 'TSLA', 'WKHS', 'ROKU', 'SLS', 'AAPL', 'FCEL', 'ACB', 'YRIV', 'TEUM', 'OSTK', 'AMZN', 'NIO', 'CEI', 'TVIX', 'NFLX', 'NAKD', 'HSGX', 'BB', 'AMRN', 'FB', 'SHOP', 'SQ', 'CHK', 'GE', 'NAK', 'RKDA', 'SNAP', 'JAGX', 'ENPH', 'MU', 'TBLT', 'TOPS', 'MNKD', 'UGAZ', 'TRXC', 'BA', 'DIS', 'NBEV', 'BABA', 'NVCN', 'PRPO', 'TEVA', 'DPW', 'MSFT', 'NTEC', 'ADXS', 'NVDA', 'NBRV', 'MNK', 'CGC', 'PTN', 'JNUG', 'MDR', 'QQQ', 'XXII', 'IQ', 'CRMD', 'YUMA', 'ADMP', 'ULTA', 'RBZ', 'IBIO', 'SESN', 'ATVI', 'RAD', 'AVEO', 'AMRH', 'CRON', 'TNDM', 'TXMD', 'DWT', 'TWTR', 'JD', 'XBIO', 'GUSH', 'JCP', 'CLF', 'FRAN', 'CLDR', 'APHA', 'FIT', 'DNR', 'BAC', 'ADMA', 'BZUN', 'GLD', 'INPX', 'OGEN', 'UWT', 'TLRY', 'PLUG', 'AUPH', 'T', 'MO', 'SLV', 'WATT', 'ENDP', 'X', 'NUGT', 'TRVN', 'DGAZ', 'TWLO', 'AMRS', 'AWSM', 'UVXY', 'SPHS', 'LCI', 'USO', 'TGT', 'ZS', 'CLD', 'MAXR', 'VSTM', 'OMER', 'CVM', 'IDEX', 'GME', 'AVGR', 'BIDU', 'NSPR', 'ISR', 'TWOU', 'CRM', 'BHC', 'PCG', 'LXRX', 'LODE', 'LPTX', 'TTD', 'ICPT', 'BLIN', 'PHUN', 'FDX', 'TTOO', 'AAL', 'VUZI', 'CPRX', 'ALT', 'ACAD', 'NVAX', 'IWM', 'TLT', 'AKER', 'AIMT', 'BPMX', 'JDST', 'SBUX', 'F', 'TTNP', 'NTNX', 'CMG', 'BIOC', 'NETE', 'CVS', 'JPM', 'MYSZ', 'LULU', 'SRPT', 'GLBS', 'HEAR', 'KNDI', 'TLRD', 'NKE', 'IDXG', 'NXTD', 'GALT', 'EKSO', 'MDB', 'OPTT', 'OPGN', 'COST', 'ALGN', 'PULM', 'DIA', 'AMC', 'GDX', 'ACST', 'SNNA', 'ABBV', 'HMNY', 'KHC', 'CLVS', 'DTEA', 'AG', 'SES', 'VKTX', 'WMT', 'CETX', 'ATNM', 'ZNGA', 'CRC', 'DUST', 'FFHL', 'ABEO', 'FPAY', 'GLUU', 'PBYI', 'INTC', 'OKTA', 'MCD', 'V', 'LABU', 'SPWR', 'PYX', 'SFIX', 'EOLS', 'BBBY', 'MRNS', 'BMY', 'PYPL', 'RH', 'MARK', 'HD', 'SRNE', 'WLL', 'APRN', 'NVTA', 'M', 'HIIQ', 'XGTI', 'MTCH', 'JNJ', 'GOOGL', 'PFE', 'SWN', 'GEVO', 'AYX', 'PTI', 'SMSI', 'CHFS', 'STNE', 'TROV', 'NEPT', 'IIPR', 'VTVT', 'HEB', 'GERN', 'DOCU', 'VLRX', 'GOOG', 'BLDP', 'GPRO', 'SHAK', 'CSCO', 'NDRA', 'SPLK', 'AKS', 'PANW', 'SAEX', 'ADBE', 'ACRX', 'VXX', 'BPTH', 'CYTR', 'EXEL', 'GS', 'AVGO', 'HUYA', 'SNES', 'EA', 'ASNA', 'SENS', 'S', 'NOG', 'SBOT', 'DMPI', 'QCOM', 'JWN', 'UNH', 'KMPH', 'BE', 'ATOS', 'MRKR', 'PLX', 'KR', 'RIOT', 'ARWR', 'SWIR', 'MRO', 'GM', 'AMPE', 'APPS', 'NOK', 'AUY', 'EYPT', 'QD', 'EARS', 'COUP', 'RIG', 'RRC', 'DRRX', 'MDCO', 'HTZ', 'AMR', 'CLSD', 'ZKIN', 'AGRX', 'MTP', 'ETSY']
    stocks = ['ROKU', 'FCEL', 'ACB', 'AAPL', 'TSLA', 'AMD', 'WKHS', 'NIO', 'OSTK', 'ADXS', 'AMZN', 'TEUM', 'TVIX', 'BB', 'NFLX', 'HSGX', 'UGAZ', 'NAKD', 'SLS', 'CEI', 'CHK', 'SHOP', 'TOPS', 'MDR', 'SQ', 'AMRN', 'ENPH', 'JAGX', 'BABA', 'FB', 'QQQ', 'SNAP', 'MU', 'PRPO', 'NTEC', 'MNK', 'DIS', 'MNKD', 'TRXC', 'ULTA', 'BA', 'MSFT', 'CGC', 'YUMA', 'DWT', 'ATVI', 'FRAN', 'ADMP', 'AUPH', 'CRMD']
    stocks = ['TSLA', 'AMD', 'ROKU', 'WKHS', 'AAPL', 'FCEL', 'ACB', 'TEUM', 'AMZN', 'NIO', 'NFLX', 'UGAZ', 'TVIX', 'OSTK', 'NAKD', 'FB', 'ADXS', 'YRIV', 'AMRN', 'DIS', 'BB', 'CHK', 'SHOP', 'SQ', 'ENPH', 'SNAP', 'BA', 'BABA', 'TRXC', 'MSFT', 'AGRX', 'GE', 'MDR', 'JAGX', 'MNKD', 'HSGX', 'RKDA', 'NAK', 'MU', 'ADMP', 'PCG', 'NBEV', 'QQQ', 'PRPO', 'TBLT', 'TEVA', 'TWTR', 'NVCN', 'CGC', 'MNK', 'FIT', 'TTNP', 'ATVI', 'NVDA', 'CRMD', 'CRON', 'IQ', 'NBRV', 'JNUG', 'TNDM', 'X', 'SESN', 'NTEC', 'PTN', 'XXII', 'AUPH', 'SES', 'RBZ', 'INPX', 'XBIO', 'IBIO', 'ULTA', 'APHA', 'RAD', 'TXMD', 'BAC', 'YUMA', 'CLF', 'AVEO', 'ADMA', 'AWSM', 'JD', 'MCD', 'DWT', 'PLUG', 'ENDP', 'GLD', 'TWLO', 'BZUN', 'JCP', 'TRVN', 'TLRY', 'DGAZ']
    stocks.remove('HSGX')
    stocks.remove('AMZN')
    # stocks.remove('ACB')
    # stocks.remove('CHK')
    # stocks.extend(['SBUX', 'TGT', 'COST', 'VMW', 'VZ', 'BABA', 'AVGO'])
    stocks = stocks[:numStocks]
    shuffle(stocks)
    return stocks


# Return soup object page of that stock
def findPageStock(symbol, date, hoursBack):
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

    # inputElement = driver.find_element_by_tag_name("input")
    # inputElement.send_keys(symbol)
    # inputElement.send_keys(Keys.ENTER)
    # time.sleep(1)
    # allButtons = driver.find_elements_by_class_name('st_1luPg-o')
    # for button in allButtons:
    #     if button.text == symbol:
    #         button.click()
    #         break
    hoursBack = 8
    try:
        scroll.scrollFor(driver, hoursBack)
    except Exception as e:
        endDriver(driver)
        end = time.time()
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
    tweetsErrorCollection = db.stock_tweets_errors
    if (tweetsErrorCollection.
            count_documents({'symbol': symbol,
                             'date': dateString}) != 0):
        return (False, 0)

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
    print(lastTime, currTime, totalHoursBack)

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
        if (tweet['time'] > lastTime):
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
        print(dateTime)
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
