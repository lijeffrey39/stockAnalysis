import datetime
import optparse
import matplotlib. pyplot as plt
import math
import yfinance as yf
import requests

from modules.helpers import (convertToEST, findTradingDays, getAllStocks,
                             insertResults, findWeight, writePickleObject, readPickleObject)
from modules.hyperparameters import constants
#from modules.nn import calcReturns, testing
from modules.prediction import (basicPrediction, findAllTweets, updateBasicStockInfo, setupUserInfos)
from modules.stockAnalysis import (findPageStock, getTopStocks, parseStockData,
                                   shouldParseStock, updateLastMessageTime,
                                   updateLastParsedTime, updateStockCount, getSortedStocks)
from modules.stockPriceAPI import (updateAllCloseOpen, transferNonLabeled, findCloseOpen, closeToOpen, getUpdatedCloseOpen, 
                                    getCloseOpenInterval, updateyfinanceCloseOpen)
from modules.userAnalysis import (findPageUser, findUsers, insertUpdateError,
                                  parseUserData, shouldParseUser, getStatsPerUser,
                                  updateUserNotAnalyzed, getAllUserInfo,
                                  calculateAllUserInfo, parseOldUsers)
from modules.tests import (findBadMessages, removeMessagesWithStock, 
                           findTopUsers, findOutliers, findAllUsers, findErrorUsers)


client = constants['db_client']
clientUser = constants['db_user_client']
clientStockTweets = constants['stocktweets_client']


# ------------------------------------------------------------------------
# ----------------------- Analyze Specific Stock -------------------------
# ------------------------------------------------------------------------


def analyzeStocks(date, stocks):
    dateString = date.strftime("%Y-%m-%d")
    for symbol in stocks:
        print(symbol)
        db = clientStockTweets.get_database('stocks_data_db')
        (shouldParse, hours) = shouldParseStock(symbol, dateString)
        if (shouldParse is False):
            continue
        (soup, errorMsg, timeElapsed) = findPageStock(symbol, date, hours)
        if (soup == ''):
            stockError = {'date': dateString, 'symbol': symbol,
                          'error': errorMsg, 'timeElapsed': timeElapsed}
            db.stock_tweets_errors.insert_one(stockError)
            continue
        
        try:
            result = parseStockData(symbol, soup)
        except Exception as e:
            stockError = {'date': dateString, 'symbol': symbol,
                          'error': str(e), 'timeElapsed': -1}
            db.stock_tweets_errors.insert_one(stockError)
            print(e)
            continue

        if (len(result) == 0):
            stockError = {'date': dateString, 'symbol': symbol,
                          'error': 'Result length is 0??', 'timeElapsed': -1}
            db.stock_tweets_errors.insert_one(stockError)
            print(stockError)
            continue

        results = updateLastMessageTime(db, symbol, result)

        # No new messages
        if (len(results) != 0):
            insertResults(results)

        updateLastParsedTime(db, symbol)


# ------------------------------------------------------------------------
# ----------------------- Analyze Specific User --------------------------
# ------------------------------------------------------------------------


# updateUser reparses tweets made by user and adds status flag if non-existing
# findNewUsers updates user_not_analyzed table to find new users to parse/store
# reAnalyze reanalyzes users that errored out
def analyzeUsers(reAnalyze, findNewUsers, updateUser):
    users = ['SDF9090']
    print(len(users))
    for username in users:
        print(username)
        coreInfo = shouldParseUser(username, reAnalyze, updateUser)
        if (not coreInfo):
            continue

        (soup, errorMsg, timeElapsed) = findPageUser(username)
        coreInfo['timeElapsed'] = timeElapsed
        if (errorMsg != ''):
            coreInfo['error'] = errorMsg
            insertUpdateError(coreInfo, reAnalyze, updateUser)
            continue

        result = parseUserData(username, soup)
        if (len(result) == 0):
            coreInfo['error'] = "Empty result list"
            insertUpdateError(coreInfo, reAnalyze, updateUser)
            continue

        insertUpdateError(coreInfo, reAnalyze, updateUser)
        insertResults(result)

def dailyAnalyzeUsers(reAnalyze, updateUser, daysback):
    users = parseOldUsers(daysback)
    print(len(users))
    for username in users:
        print(username)
        coreInfo = shouldParseUser(username, reAnalyze, updateUser)
        if (not coreInfo):
            continue

        (soup, errorMsg, timeElapsed) = findPageUser(username)
        coreInfo['timeElapsed'] = timeElapsed
        if (errorMsg != ''):
            coreInfo['error'] = errorMsg
            insertUpdateError(coreInfo, reAnalyze, updateUser)
            continue

        result = parseUserData(username, soup)
        if (len(result) == 0):
            coreInfo['error'] = "Empty result list"
            insertUpdateError(coreInfo, reAnalyze, updateUser)
            continue

        insertUpdateError(coreInfo, reAnalyze, updateUser)
        insertResults(result)


# ------------------------------------------------------------------------
# --------------------------- Main Function ------------------------------
# ------------------------------------------------------------------------


def addOptions(parser):
    parser.add_option('-u', '--users',
                      action='store_true', dest="users",
                      help="parse user information")

    parser.add_option('-s', '--stocks',
                      action='store_true', dest="stocks",
                      help="parse stock information")

    parser.add_option('-p', '--prediction',
                      action='store_true', dest="prediction",
                      help="make prediction for today")

    parser.add_option('-c', '--updateCloseOpens',
                      action='store_true', dest="updateCloseOpens",
                      help="update Close open times")

    parser.add_option('-z', '--hourlyparser',
                      action='store_true', dest="hourlyparser",
                      help="parse through stock pages hourly")
    
    parser.add_option('-d', '--dailyparser',
                      action='store_true', dest="dailyparser",
                      help="parse through non-top x stock pages daily")

    parser.add_option('-a', '--dailyuserparser',
                      action='store_true', dest="dailyuserparser",
                      help="parse through user information that havent been parsed over last x days (14)")


# Make a prediction for given date
def makePrediction(date):
    dates = [datetime.datetime(date.year, date.month, date.day, 9, 30)]
    stocks = getTopStocks(20)
    stocks.remove('AMZN')
    stocks = ['TSLA']
    analyzeStocks(date, stocks)
    # basicPrediction(dates, stocks, True, True)

# Executed hourly, finds all the tweets from the top x stocks
def hourlyparse():
    date = convertToEST(datetime.datetime.now())
    stocks = getTopStocks(50)
    date = datetime.datetime(date.year, date.month, date.day, 9, 30)
    analyzeStocks(date, stocks)

# Executed daily, finds all the tweets from the non-top x stocks
def dailyparse():
    now = convertToEST(datetime.datetime.now())
    date = datetime.datetime(now.year, now.month, now.day)
    stocks = getSortedStocks()
    analyzeStocks(date, stocks[101:1001])

def main():
    opt_parser = optparse.OptionParser()
    addOptions(opt_parser)
    options, _ = opt_parser.parse_args()
    dateNow = convertToEST(datetime.datetime.now())

    if (options.users):
        analyzeUsers(reAnalyze=False, findNewUsers=False, updateUser=True)
    elif (options.stocks):
        now = convertToEST(datetime.datetime.now())
        date = datetime.datetime(now.year, now.month, now.day)
        stocks = getTopStocks(100)
        # print(len(stocks))
        # for i in range(len(stocks)):
        #     if (stocks[i] == "SESN"):
        #         print(i)
        analyzeStocks(date, stocks)
    elif (options.prediction):
        makePrediction(dateNow)
    elif (options.updateCloseOpens):
        updateStockCount()
        now = convertToEST(datetime.datetime.now())
        date = datetime.datetime(now.year, now.month, now.day, 12, 30)
        dateNow = datetime.datetime(now.year, now.month, now.day, 13, 30)
        dates = findTradingDays(date, dateNow)
        print(dates)
        stocks = getSortedStocks()
        updateAllCloseOpen(stocks, dates)
    elif (options.hourlyparser):
        hourlyparse()
    elif (options.dailyparser):
        dailyparse()
    elif (options.dailyuserparser):
        dailyAnalyzeUsers(reAnalyze=True, updateUser=True, daysback=14)
    else:
        print('')
        # currTime = convertToEST(datetime.datetime.now())
        # prevTime = currTime - datetime.timedelta(days=30)   
        # db = constants['db_client'].get_database('stocktwits_db').stock_counts_v2
        # analyzedUsers = constants['stocktweets_client'].get_database('tweets_db').tweets
        # res = analyzedUsers.aggregate([{ "$match": { "time" : { '$gte' : prevTime} } }, {'$group' : { '_id' : '$symbol', 'count' : {'$sum' : 1}}}, { "$sort": { "count": 1 } },])
        # for i in res:
        #     result = {'_id': i['_id'], 'count30': i['count']}
        #     query = {'_id': i['_id']}
        #     newVal = {'$set': {'count30': i['count']}}
        #     db.update_one(query, newVal)
        #     print(result)
            #db.insert_one(result)
        #stocks = getSortedStocks()
        #print(stocks)
        # y = ['AAAU', 'AABB', 'AACAY', 'AACG', 'AAGIY', 'AAMC', 'AAME', 'AAN', 'AAON', 'AAT', 'AAU', 'AAWW', 'AAXJ', 'AB', 'ABAHF', 'ABB', 'ABC', 'ABCB', 'ABG', 'ABM', 'ABTX', 'ABVC', 'AC', 'ACA', 'ACAM', 'ACAMU', 'ACBI', 'ACC', 'ACCO', 'ACER', 'ACES', 'ACFN', 'ACGL', 'ACGLO', 'ACGLP', 'ACH', 'ACIU', 'ACIW', 'ACLS', 'ACM', 'ACMC', 'ACMR', 'ACN', 'ACNB', 'ACP', 'ACRE', 'ACRGF', 'ACRL', 'ACRS', 'ACT', 'ACTG', 'ACTT', 'ACTTU', 'ACTV', 'ACU', 'ACV', 'ACWI', 'ACWV', 'ACWX', 'ACY', 'ADAP', 'ADC', 'ADDYY', 'ADES', 'ADI', 'ADM', 'ADNT', 'ADPT', 'ADRE', 'ADRNY', 'ADS', 'ADSV', 'ADSW', 'ADT', 'ADTN', 'ADUS', 'ADVM', 'ADX', 'ADYX', 'AE', 'AEB', 'AEE', 'AEF', 'AEFC', 'AEG', 'AEGN', 'AEHR', 'AEIS', 'AEL', 'AEMC', 'AEP', 'AER', 'AESE', 'AEY', 'AEYE', 'AFB', 'AFC', 'AFG', 'AFGB', 'AFGH', 'AFH', 'AFI', 'AFIN', 'AFINP', 'AFL', 'AFMD', 'AFPW', 'AFT', 'AFYA', 'AGBA', 'AGBAU', 'AGCO', 'AGCZ', 'AGD', 'AGE', 'AGEEF', 'AGF', 'AGFS', 'AGG', 'AGGFF', 'AGGP', 'AGHI', 'AGI', 'AGLE', 'AGM', 'AGMH', 'AGNCN', 'AGNCO', 'AGND', 'AGO', 'AGQ', 'AGR', 'AGRO', 'AGRS', 'AGS', 'AGTC', 'AGTEF', 'AGTK', 'AGX', 'AGYS', 'AGZD', 'AHC', 'AHH', 'AHL', 'AHOTF', 'AHPI', 'AHT', 'AI', 'AIA', 'AIC', 'AIEQ', 'AIF', 'AIH', 'AIHS', 'AIM', 'AIMC', 'AIN', 'AINC', 'AINV', 'AIO', 'AIQ', 'AIR', 'AIRG', 'AIRR', 'AIRT', 'AIRTP', 'AIT', 'AITX', 'AIV', 'AIXN', 'AIZ', 'AIZP', 'AJG', 'AJIA', 'AJX', 'AJXA', 'AKAM', 'AKG', 'AKR', 'AKRO', 'AKRX', 'AKTS', 'AKTX', 'AKZOF', 'AL', 'ALAC', 'ALBO', 'ALC', 'ALCO', 'ALE', 'ALEAF', 'ALEC', 'ALEX', 'ALG', 'ALGR', 'ALGT', 'ALID', 'ALIM', 'ALJJ', 'ALKM', 'ALKS', 'ALLE', 'ALLK', 'ALLT', 'ALNA', 'ALO', 'ALOT', 'ALPN', 'ALPP', 'ALRM', 'ALRS', 'ALSK', 'ALSN', 'ALTM', 'ALTR', 'ALTY', 'ALV', 'ALX', 'ALYA', 'ALYE', 'AM', 'AMAG', 'AMAL', 'AMANF', 'AMAR', 'AMAZ', 'AMBC', 'AMBO', 'AMCI', 'AMCR', 'AMCX', 'AME', 'AMEH', 'AMG', 'AMH', 'AMIVF', 'AMK', 'AMKAF', 'AMKR', 'AMLM', 'AMLP', 'AMMJ', 'AMMX', 'AMN', 'AMNB', 'AMNF', 'AMOT', 'AMOV', 'AMP', 'AMPH', 'AMPY', 'AMRB', 'AMRC', 'AMRK', 'AMRX', 'AMS', 'AMSF', 'AMSSY', 'AMSWA', 'AMTB', 'AMTBB', 'AMTD', 'AMTX', 'AMWD', 'AMX', 'AMYZF', 'AMZA', 'AN', 'ANAB', 'ANAT', 'ANCN', 'ANCTF', 'ANDA', 'ANDAU', 'ANDE', 'ANDI', 'ANFC', 'ANGI', 'ANGL', 'ANGO', 'ANH', 'ANIK', 'ANIOY', 'ANIP', 'ANPDY', 'ANR', 'ANSS', 'ANTE', 'ANTH', 'ANTM', 'AOBC', 'AOD', 'AON', 'AOR', 'AOS', 'AOSL', 'AP', 'APA', 'APAM', 'APD', 'APEI', 'APEN', 'APEX', 'APH', 'APLE', 'APLS', 'APLT', 'APM', 'APO', 'APOG', 'APRE', 'APRU', 'APT', 'APTS', 'APTV', 'APTX', 'APVO', 'APWC', 'APXTU', 'APY', 'APYP', 'APYX', 'AQB', 'AQN', 'AQNA', 'AQSP', 'AQST', 'AQUA', 'AR', 'ARA', 'ARAV', 'ARAY', 'ARC', 'ARCB', 'ARCC', 'ARCE', 'ARCH', 'ARCO', 'ARCT', 'ARCW', 'ARD', 'ARDC', 'ARDS', 'ARDX', 'ARE', 'AREC', 'ARES', 'ARESF', 'ARFXF', 'ARGO', 'ARGT', 'ARGX', 'ARHH', 'ARI', 'ARKF', 'ARKG', 'ARKK', 'ARKQ', 'ARKR', 'ARKW', 'ARL', 'ARLP', 'ARMK', 'ARMP', 'AROC', 'AROW', 'ARR', 'ARSN', 'ARST', 'ARTC', 'ARTH', 'ARTL', 'ARTNA', 'ARVN', 'ARW', 'ARYA', 'ASA', 'ASB', 'ASC', 'ASCK', 'ASDN', 'ASET', 'ASFI', 'ASG', 'ASGN', 'ASH', 'ASIX', 'ASLN', 'ASM', 'ASMB', 'ASML', 'ASND', 'ASPN', 'ASPS', 'ASPU', 'ASR', 'ASRT', 'ASRV', 'ASRVP', 'ASTE', 'ASTI', 'ASUR', 'ASX', 'ASYS', 'AT', 'ATAX', 'ATEN', 'ATEX', 'ATGE', 'ATGFF', 'ATH', 'ATHE', 'ATHM', 'ATI', 'ATIF', 'ATKR', 'ATLC', 'ATLO', 'ATLS', 'ATNI', 'ATNX', 'ATO', 'ATOM', 'ATR', 'ATRA', 'ATRC', 'ATRI', 'ATRO', 'ATSG', 'ATTO', 'ATUS', 'ATV', 'ATW', 'ATXI', 'ATZ', 'AUB', 'AUBN', 'AUDC', 'AUDVF', 'AUG', 'AUSAF', 'AUSI', 'AUTL', 'AUTO', 'AVA', 'AVAL', 'AVB', 'AVD', 'AVDL', 'AVGOP', 'AVH', 'AVID', 'AVK', 'AVLP', 'AVLR', 'AVNS', 'AVNW', 'AVOI', 'AVRO', 'AVT', 'AVTR', 'AVY', 'AWF', 'AWI', 'AWP', 'AWR', 'AWRE', 'AX', 'AXAHY', 'AXE', 'AXGN', 'AXGT', 'AXLA', 'AXNX', 'AXR', 'AXRX', 'AXS', 'AXTA', 'AXTI', 'AXU', 'AY', 'AYI', 'AZPN', 'AZRE', 'AZUL', 'AZZ', 'B', 'BAB', 'BACHY', 'BADFF', 'BAESY', 'BAF', 'BAH', 'BAK', 'BAM', 'BANC', 'BAND', 'BANF', 'BANR', 'BANT', 'BANX', 'BAP', 'BAR', 'BASFY', 'BASI', 'BAT', 'BATRA', 'BATRK', 'BAX', 'BAYK', 'BAYRY', 'BBAR', 'BBAVF', 'BBC', 'BBCA', 'BBCP', 'BBD', 'BBDC', 'BBDO', 'BBF', 'BBGI', 'BBH', 'BBI', 'BBIO', 'BBJP', 'BBK', 'BBL', 'BBN', 'BBQ', 'BBSI', 'BBU', 'BBVA', 'BBW', 'BBX', 'BC', 'BCBP', 'BCC', 'BCDA', 'BCDRF', 'BCE', 'BCEI', 'BCEL', 'BCH', 'BCKMF', 'BCML', 'BCO', 'BCOM', 'BCOR', 'BCOV', 'BCOW', 'BCPC', 'BCS', 'BCSF', 'BCTF', 'BCV', 'BCX', 'BCYC', 'BDC', 'BDGE', 'BDIC', 'BDJ', 'BDL', 'BDN', 'BDR', 'BDRBF', 'BDRY', 'BEAM', 'BEBE', 'BEDU', 'BELFA', 'BELFB', 'BEMG', 'BEN', 'BEP', 'BERY', 'BEST', 'BFAM', 'BFC', 'BFGC', 'BFIN', 'BFIT', 'BFK', 'BFO', 'BFRA', 'BFS', 'BFST', 'BFY', 'BFZ', 'BGB', 'BGCP', 'BGFV', 'BGG', 'BGH', 'BGI', 'BGIO', 'BGNE', 'BGR', 'BGRN', 'BGRP', 'BGS', 'BGSF', 'BGT', 'BGX', 'BGY', 'BH', 'BHAT', 'BHB', 'BHE', 'BHFAL', 'BHK', 'BHKLY', 'BHLB', 'BHP', 'BHR', 'BHRB', 'BHTG', 'BHV', 'BHVN', 'BIB', 'BICK', 'BIEI', 'BIEL', 'BIF', 'BIL', 'BILL', 'BIMI', 'BIMT', 'BIND', 'BIO', 'BIOL', 'BIOQ', 'BIOX', 'BIP', 'BIPIX', 'BIS', 'BIT', 'BITA', 'BITCF', 'BIV', 'BIZD', 'BJ', 'BJCHF', 'BJK', 'BJRI', 'BK', 'BKCC', 'BKD', 'BKE', 'BKEP', 'BKEPP', 'BKGM', 'BKH', 'BKHRF', 'BKI', 'BKIRF', 'BKK', 'BKLN', 'BKN', 'BKR', 'BKRKY', 'BKSC', 'BKT', 'BKTI', 'BKU', 'BKYI', 'BL', 'BLBD', 'BLCN', 'BLD', 'BLDR', 'BLE', 'BLEVF', 'BLGO', 'BLIS', 'BLKB', 'BLL', 'BLMN', 'BLOK', 'BLSP', 'BLU', 'BLV', 'BLW', 'BLX', 'BLXX', 'BMA', 'BMC', 'BMCH', 'BME', 'BMI', 'BMLP', 'BMMJ', 'BMO', 'BMRA', 'BMRC', 'BMTC', 'BMTM', 'BMWYY', 'BND', 'BNDX', 'BNED', 'BNFT', 'BNGI', 'BNGO', 'BNKL', 'BNO', 'BNS', 'BNSO', 'BNT', 'BNTC', 'BNTX', 'BNY', 'BOCH', 'BOE', 'BOH', 'BOIL', 'BOKF', 'BOKFL', 'BOMN', 'BOND', 'BONXF', 'BOOT', 'BORR', 'BOSC', 'BOSS', 'BOTJ', 'BOTZ', 'BPFH', 'BPMC', 'BPMP', 'BPOP', 'BPOPM', 'BPRN', 'BPSR', 'BPT', 'BPY', 'BPZZF', 'BQH', 'BR', 'BRBR', 'BRC', 'BREW', 'BRF', 'BRFH', 'BRFS', 'BRG', 'BRGO', 'BRID', 'BRKL', 'BRKR', 'BRKS', 'BRN', 'BRO', 'BROG', 'BRP', 'BRPA', 'BRPAU', 'BRQS', 'BRT', 'BRTI', 'BRX', 'BRY', 'BSAC', 'BSBR', 'BSC', 'BSCK', 'BSD', 'BSE', 'BSET', 'BSI', 'BSIG', 'BSJK', 'BSJL', 'BSL', 'BSM', 'BSMN', 'BSMO', 'BSMQ', 'BSMX', 'BSPM', 'BSQR', 'BSRC', 'BSRR', 'BST', 'BSTC', 'BSTG', 'BSTZ', 'BSV', 'BSVN', 'BTA', 'BTAI', 'BTAL', 'BTCY', 'BTEC', 'BTG', 'BTN', 'BTO', 'BTSC', 'BTT', 'BTU', 'BTZ', 'BUG', 'BUI', 'BUKS', 'BUND', 'BURL', 'BUROF', 'BUSE', 'BV', 'BVFL', 'BVN', 'BVNRY', 'BVXV', 'BWAY', 'BWB', 'BWEN', 'BWFG', 'BWG', 'BWX', 'BWXT', 'BWZ', 'BXC', 'BXG', 'BXMT', 'BXMX', 'BXP', 'BXS', 'BY', 'BYD', 'BYDDF', 'BYDDY', 'BYFC', 'BYLD', 'BYM', 'BYND', 'BYSI', 'BYZN', 'BZH', 'BZLFY', 'BZM', 'BZQ', 'BZTG', 'CAAP', 'CAAS', 'CABA', 'CABO', 'CAC', 'CACC', 'CACG', 'CACI', 'CADE', 'CAE', 'CAF', 'CAGDF', 'CAH', 'CAHPF', 'CAI', 'CAIXY', 'CAJ', 'CAKE', 'CAL', 'CALI', 'CALM', 'CALX', 'CAMP', 'CANB', 'CANE', 'CANG', 'CANN', 'CAP', 'CAPC', 'CAPD', 'CAPL', 'CAPR', 'CAPS', 'CARE', 'CARG', 'CARS', 'CARV', 'CARZ', 'CASA', 'CASH', 'CASI', 'CASS', 'CASY', 'CATB', 'CATC', 'CATH', 'CATM', 'CATO', 'CATY', 'CB', 'CBAN', 'CBAT', 'CBB', 'CBBT', 'CBD', 'CBDL', 'CBFV', 'CBH', 'CBKC', 'CBKM', 'CBLI', 'CBMB', 'CBMG', 'CBNK', 'CBNT', 'CBO', 'CBOE', 'CBPO', 'CBRE', 'CBSH', 'CBSHP', 'CBT', 'CBTX', 'CBU', 'CBWBF', 'CBWTF', 'CBZ', 'CCB', 'CCBG', 'CCC', 'CCD', 'CCEP', 'CCF', 'CCFN', 'CCH', 'CCIHY', 'CCJ', 'CCK', 'CCLP', 'CCM', 'CCMP', 'CCNE', 'CCO', 'CCOI', 'CCOR', 'CCR', 'CCRC', 'CCRE', 'CCRN', 'CCS', 'CCSB', 'CCU', 'CCUR', 'CCX', 'CCXI', 'CCZ', 'CDAY', 'CDC', 'CDEV', 'CDK', 'CDL', 'CDLX', 'CDMOP', 'CDNS', 'CDOR', 'CDR', 'CDTI', 'CDTX', 'CDW', 'CDXS', 'CDZI', 'CE', 'CEA', 'CECE', 'CEE', 'CEF', 'CEFL', 'CEIX', 'CEL', 'CELC', 'CELH', 'CELP', 'CELZ', 'CEM', 'CEMI', 'CEN', 'CENT', 'CENTA', 'CEO', 'CEOS', 'CEPU', 'CEQP', 'CERN', 'CERS', 'CESDF', 'CET', 'CETV', 'CETXP', 'CEV', 'CEVA', 'CEY', 'CEZ', 'CF', 'CFA', 'CFB', 'CFBI', 'CFBK', 'CFFA', 'CFFI', 'CFFN', 'CFG', 'CFGX', 'CFI', 'CFO', 'CFR', 'CFX', 'CFXA', 'CG', 'CGA', 'CGBD', 'CGEN', 'CGJTF', 'CGO', 'CGW', 'CHA', 'CHAP', 'CHAU', 'CHCI', 'CHCO', 'CHCT', 'CHDN', 'CHE', 'CHEF', 'CHH', 'CHI', 'CHIC', 'CHIX', 'CHKP', 'CHKR', 'CHL', 'CHMA', 'CHMG', 'CHMI', 'CHN', 'CHNA', 'CHNG', 'CHNGU', 'CHNR', 'CHOOF', 'CHPGF', 'CHRA', 'CHRS', 'CHRW', 'CHS', 'CHSCL', 'CHSCM', 'CHSCN', 'CHSCP', 'CHT', 'CHU', 'CHUY', 'CHW', 'CHWY', 'CHX', 'CHY', 'CHYHY', 'CIA', 'CIB', 'CIBEY', 'CIBR', 'CID', 'CIF', 'CIFAF', 'CIFS', 'CIG', 'CIGI', 'CIH', 'CII', 'CIIX', 'CIK', 'CIL', 'CIM', 'CINF', 'CINR', 'CIO', 'CIR', 'CIT', 'CIVB', 'CIX', 'CIZ', 'CIZN', 'CKH', 'CKPT', 'CKX', 'CL', 'CLAR', 'CLB', 'CLBK', 'CLBS', 'CLC', 'CLCT', 'CLDB', 'CLDT', 'CLFD', 'CLGN', 'CLGX', 'CLH', 'CLI', 'CLIR', 'CLLS', 'CLM', 'CLMT', 'CLNC', 'CLNY', 'CLOK', 'CLOU', 'CLPR', 'CLRG', 'CLS', 'CLSH', 'CLSI', 'CLSK', 'CLUB', 'CLW', 'CLWD', 'CLWT', 'CLX', 'CLXT', 'CM', 'CMA', 'CMBM', 'CMC', 'CMCL', 'CMCM', 'CMCO', 'CMCT', 'CMD', 'CME', 'CMGO', 'CMLS', 'CMO', 'CMP', 'CMPR', 'CMRE', 'CMRX', 'CMS', 'CMSA', 'CMT', 'CMTL', 'CMU', 'CMXC', 'CN', 'CNA', 'CNBB', 'CNBKA', 'CNBS', 'CNCE', 'CNCR', 'CNDT', 'CNF', 'CNFR', 'CNHI', 'CNI', 'CNIG', 'CNK', 'CNLHP', 'CNMD', 'CNNE', 'CNNEF', 'CNNXF', 'CNO', 'CNOB', 'CNONF', 'CNP', 'CNPOF', 'CNQ', 'CNR', 'CNRG', 'CNS', 'CNST', 'CNTY', 'CNX', 'CNXM', 'CNXN', 'CO', 'COCP', 'CODA', 'CODEF', 'CODI', 'COE', 'COF', 'COFS', 'COHN', 'COHR', 'COHU', 'COKE', 'COL', 'COLB', 'COLD', 'COLM', 'COMM', 'COMT', 'CONE', 'CONN', 'COO', 'COOP', 'COP', 'COPX', 'COR', 'CORE', 'CORN', 'CORR', 'COSM', 'COTE', 'COV', 'COWN', 'COWNL', 'CP', 'CPA', 'CPAA', 'CPAAU', 'CPAC', 'CPC', 'CPCAY', 'CPER', 'CPF', 'CPHC', 'CPI', 'CPIX', 'CPK', 'CPKA', 'CPLG', 'CPLP', 'CPMD', 'CPRI', 'CPS', 'CPSH', 'CPSI', 'CPSS', 'CPT', 'CPTA', 'CPTAG', 'CPTAL', 'CPXGF', 'CQP', 'CQQQ', 'CR', 'CRAI', 'CRAK', 'CRBJF', 'CRESY', 'CREX', 'CRF', 'CRGS', 'CRH', 'CRHM', 'CRI', 'CRL', 'CRLBF', 'CRMT', 'CRNC', 'CRNCY', 'CRNX', 'CRS', 'CRSA', 'CRSAU', 'CRSM', 'CRT', 'CRTO', 'CRTX', 'CRUS', 'CRVL', 'CRVS', 'CRWD', 'CRWS', 'CRY', 'CS', 'CSA', 'CSB', 'CSBB', 'CSBTF', 'CSF', 'CSFL', 'CSGP', 'CSGS', 'CSII', 'CSL', 'CSLI', 'CSLLY', 'CSLT', 'CSML', 'CSOD', 'CSPI', 'CSQ', 'CSRLF', 'CSSE', 'CSSEP', 'CSSI', 'CSTE', 'CSTL', 'CSTM', 
        # 'CSTR', 'CSU', 'CSV', 'CSVI', 'CSWC', 'CSWI', 'CTAA', 'CTABF', 'CTAM', 'CTAS', 'CTB', 'CTBB', 'CTBI', 'CTC', 'CTDH', 'CTDT', 'CTEK', 'CTG', 'CTGO', 'CTHR', 'CTIB', 'CTIC', 'CTLT', 'CTMX', 'CTO', 'CTP', 'CTR', 'CTRA', 'CTRC', 'CTRE', 'CTRM', 'CTRN', 'CTRYF', 'CTRYY', 'CTS', 'CTSO', 'CTT', 'CTTAY', 'CTV', 'CTVA', 'CTY', 'CTYX', 'CTZ', 'CUB', 'CUBA', 'CUBE', 'CUBI', 'CUBV', 'CUE', 'CUI', 'CUK', 'CULP', 'CURE', 'CURLF', 'CURO', 'CUT', 'CUTR', 'CUZ', 'CVA', 'CVALF', 'CVBF', 'CVCO', 'CVCY', 'CVET', 'CVGI', 'CVGW', 'CVI', 'CVIA', 'CVLB', 'CVLT', 'CVLY', 'CVR', 'CVSI', 'CVTI', 'CVU', 'CVV', 'CW', 'CWB', 'CWBC', 'CWBHF', 'CWBR', 'CWCO', 'CWEN', 'CWGL', 'CWI', 'CWK', 'CWST', 'CWT', 'CWXZF', 'CXDC', 'CXDO', 'CXE', 'CXH', 'CXO', 'CXP', 'CXSE', 'CXW', 'CXXIF', 'CYAD', 'CYAN', 'CYB', 'CYBE', 'CYCCP', 'CYCN', 'CYD', 'CYDY', 'CYIO', 'CYRN', 'CYRX', 'CYTK', 'CYVF', 'CYYHF', 'CZNC', 'CZWI', 'CZZ', 'D', 'DAC', 'DAIO', 'DAKT', 'DALI', 'DALT', 'DANOY', 'DAO', 'DAR', 'DASTY', 'DAVA', 'DBA', 'DBB', 'DBC', 'DBCP', 'DBE', 'DBEF', 'DBI', 'DBL', 'DBO', 'DBP', 'DBRM', 'DBS', 'DBVT', 'DCF', 'DCHF', 'DCI', 'DCO', 'DCOM', 'DCP', 'DCPH', 'DCTH', 'DCUE', 'DD', 'DDAIF', 'DDF', 'DDM', 'DDOG', 'DDS', 'DDT', 'DEA', 'DEF', 'DEI', 'DEM', 'DENN', 'DENR', 'DEO', 'DESP', 'DEWM', 'DEX', 'DFCO', 'DFEN', 'DFIN', 'DFNL', 'DFP', 'DFRYF', 'DFS', 'DGICA', 'DGICB', 'DGII', 'DGL', 'DGLD', 'DGLT', 'DGP', 'DGRE', 'DGRO', 'DGRS', 'DGRW', 'DGS', 'DGTW', 'DGX', 'DHF', 'DHIL', 'DHR', 'DHT', 'DHX', 'DHY', 'DIAL', 'DIAX', 'DIGP', 'DIM', 'DIN', 'DIOD', 'DISCA', 'DISCB', 'DISCK', 'DIT', 'DIV', 'DJCO', 'DJI', 'DJIA', 'DJT', 'DJU', 'DKGR', 'DKL', 'DL', 'DLA', 'DLAKY', 'DLB', 'DLGNF', 'DLHC', 'DLMAF', 'DLN', 'DLNG', 'DLPN', 'DLPTF', 'DLR', 'DLS', 'DLTH', 'DLX', 'DLYT', 'DMAC', 'DMAN', 'DMB', 'DMF', 'DMLP', 'DMLRY', 'DMO', 'DMRC', 'DMTK', 'DNBHF', 'DNI', 'DNJR', 'DNLI', 'DNN', 'DNNGY', 'DNOW', 'DNP', 'DNZOY', 'DOC', 'DOG', 'DOGZ', 'DOL', 'DON', 'DOO', 'DOOO', 'DOOR', 'DORM', 'DOV', 'DOW', 'DOX', 'DOYU', 'DPDW', 'DPG', 'DPHC', 'DPSGY', 'DPST', 'DPWW', 'DRAD', 'DRADP', 'DRD', 'DRE', 'DRH', 'DRI', 'DRIO', 'DRIV', 'DRKOF', 'DRN', 'DRNA', 'DRQ', 'DRTT', 'DRUA', 'DRV', 'DRVD', 'DS', 'DSDYX', 'DSE', 'DSGT', 'DSGX', 'DSKE', 'DSL', 'DSLV', 'DSM', 'DSNKY', 'DSPG', 'DSS', 'DSSI', 'DSU', 'DSWL', 'DT', 'DTD', 'DTE', 'DTEGY', 'DTF', 'DTGI', 'DTIL', 'DTQ', 'DTRL', 'DTSS', 'DTW', 'DTY', 'DTYS', 'DUC', 'DUG', 'DUKB', 'DUKH', 'DUO', 'DUOT', 'DUUO', 'DVA', 'DVCR', 'DVD', 'DVLP', 'DVY', 'DVYE', 'DWAS', 'DWAT', 'DWLD', 'DWPP', 'DWSH', 'DWSN', 'DX', 'DXBRF', 'DXC', 'DXD', 'DXF', 'DXJ', 'DXJS', 'DXLG', 'DXPE', 'DXR', 'DXYN', 'DY', 'DYAI', 'DYMEF', 'DYNA', 'DYNT', 'DYSL', 'DZK', 'DZSI', 'E', 'EAB', 'EACO', 'EAD', 'EADSY', 'EAF', 'EARN', 'EASI', 'EAST', 'EAT', 'EB', 'EBAYL', 'EBF', 'EBIZ', 'EBMT', 'EBR', 'EBS', 'EBSB', 'EBTC', 'EC', 'ECC', 'ECCB', 'ECCY', 'ECF', 'ECH', 'ECHO', 'ECOL', 'ECOM', 'ECOR', 'ECPG', 'ECRP', 'ECT', 'ED', 'EDAP', 'EDC', 'EDD', 'EDEN', 'EDF', 'EDI', 'EDN', 'EDNT', 'EDSA', 'EDU', 'EDUC', 'EDV', 'EDXC', 'EDZ', 'EE', 'EEA', 'EEMA', 'EEMV', 'EES', 'EEV', 'EEX', 'EFAS', 'EFAV', 'EFBI', 'EFC', 'EFF', 'EFG', 'EFL', 'EFLVF', 'EFOI', 'EFR', 'EFSC', 'EFT', 'EFX', 'EFZ', 'EGBN', 'EGF', 'EGHSF', 'EGHT', 'EGIF', 'EGLE', 'EGOC', 'EGOV', 'EGP', 'EGPT', 'EGRX', 'EH', 'EHC', 'EHI', 'EHT', 'EIC', 'EIDO', 'EIDX', 'EIG', 'EIGI', 'EIGR', 'EIM', 'EIS', 'EL', 'ELC', 'ELD', 'ELEEF', 'ELF', 'ELFIF', 'ELLO', 'ELLXF', 'ELMD', 'ELOX', 'ELP', 'ELPVY', 'ELS', 'ELSE', 'ELTK', 'ELTP', 'ELU', 'ELUXY', 'ELVT', 'EMAN', 'EMB', 'EMBI', 'EMC', 'EMCB', 'EMCF', 'EMCG', 'EMD', 'EME', 'EMF', 'EMGC', 'EMHTF', 'EMHY', 'EMIS', 'EMITF', 'EMKR', 'EML', 'EMLC', 'EMLP', 'EMMA', 'EMMS', 'EMN', 'EMO', 'EMPM', 'EMR', 'EMRAF', 'EMTY', 'EMX', 'ENBL', 'ENBP', 'ENDV', 'ENG', 'ENIA', 'ENIC', 'ENJ', 'ENLAY', 'ENLC', 'ENLV', 'ENO', 'ENOB', 'ENR', 'ENS', 'ENSG', 'ENSV', 'ENT', 'ENTA', 'ENTX', 'ENV', 'ENVA', 'ENX', 'ENZ', 'ENZL', 'ENZN', 'EOD', 'EOI', 'EONGY', 'EOS', 'EOT', 'EPAC', 'EPAM', 'EPAY', 'EPAZ', 'EPC', 'EPD', 'EPHE', 'EPI', 'EPM', 'EPOL', 'EPRT', 'EPSN', 'EPU', 'EPV', 'EPXY', 'EQ', 'EQBK', 'EQC', 'EQH', 'EQIX', 'EQM', 'EQNR', 'EQR', 'EQRR', 'EQS', 'EQT', 'EQX', 'ERA', 'ERBB', 'ERC', 'ERF', 'ERH', 'ERI', 'ERIE', 'ERII', 'ERJ', 'EROS', 'ERUS', 'ERX', 'ERY', 'ERYP', 'ES', 'ESBK', 'ESCA', 'ESE', 'ESG', 'ESGD', 'ESGE', 'ESGG', 'ESGR', 'ESGRP', 'ESGU', 'ESI', 'ESLOF', 'ESLOY', 'ESLT', 'ESMC', 'ESNT', 'ESOA', 'ESP', 'ESPO', 'ESPR', 'ESQ', 'ESRT', 'ESS', 'ESSA', 'ESTA', 'ESTE', 'ESXB', 'ET', 'ETB', 'ETC', 'ETCG', 'ETFC', 'ETG', 'ETH', 'ETHE', 'ETII', 'ETJ', 'ETM', 'ETN', 'ETO', 'ETON', 'ETRN', 'ETST', 'ETTX', 'ETV', 'ETW', 'ETX', 'ETY', 'EUFN', 'EUFX', 'EUM', 'EUO', 'EUR', 'EURN', 'EV', 'EVA', 'EVBG', 'EVBN', 'EVC', 'EVF', 'EVFM', 'EVG', 'EVGBC', 'EVGN', 'EVH', 'EVI', 'EVK', 'EVLMC', 'EVLO', 'EVM', 'EVN', 'EVOK', 'EVOL', 'EVOP', 'EVR', 'EVRG', 'EVRI', 'EVSI', 'EVT', 'EVTCY', 'EVV', 'EVX', 'EVY', 'EWA', 'EWBC', 'EWC', 'EWD', 'EWG', 'EWH', 'EWI', 'EWJ', 'EWJE', 'EWJV', 'EWL', 'EWLU', 'EWM', 'EWN', 'EWQ', 'EWS', 'EWT', 'EWU', 'EWW', 'EWY', 'EWZS', 'EXC', 'EXCH', 'EXD', 'EXDI', 'EXFO', 'EXG', 'EXI', 'EXLS', 'EXP', 'EXPC', 'EXPCU', 'EXPD', 'EXPI', 'EXPO', 'EXR', 'EXSR', 'EXTN', 'EXTR', 'EYE', 'EZA', 'EZM', 'EZPW', 'EZT', 'EZU', 'FAAR', 'FAB', 'FAD', 'FAF', 'FALC', 'FALN', 'FAM', 'FAMI', 'FAN', 'FANH', 'FANUF', 'FANUY', 'FARE', 'FARM', 'FARO', 'FAS', 'FAT', 'FAX', 'FAZ', 'FBC', 'FBHS', 'FBIO', 'FBIOP', 'FBIZ', 'FBK', 'FBM', 'FBMS', 'FBNC', 'FBNDX', 'FBP', 'FBR', 'FBSI', 'FBSS', 'FBT', 'FBZ', 'FC', 'FCA', 'FCAL', 'FCAN', 'FCAP', 'FCBC', 'FCBP', 'FCCO', 'FCCY', 'FCF', 'FCFS', 'FCG', 'FCN', 'FCNCA', 'FCNCB', 'FCNTX', 'FCO', 'FCPT', 'FCT', 'FCVT', 'FDBC', 'FDBL', 'FDEF', 'FDEU', 'FDGRX', 'FDIV', 'FDMO', 'FDN', 'FDP', 'FDS', 'FDT', 'FDUS', 'FEDU', 'FEIM', 'FELE', 'FEM', 'FEMB', 'FEMS', 'FEN', 'FENC', 'FENG', 'FENY', 'FEO', 'FERGY', 'FET', 'FEUL', 'FEX', 'FEZ', 'FF', 'FFA', 'FFBC', 'FFBW', 'FFC', 'FFG', 'FFIC', 'FFIN', 'FFIV', 'FFLWF', 'FFMGF', 'FFNW', 'FFTY', 'FFWM', 'FGB', 'FGBI', 'FGCO', 'FGEN', 'FHB', 'FHK', 'FHKCX', 'FHLC', 'FHN', 'FI', 'FIBK', 'FICO', 'FID', 'FIF', 'FIGM', 'FIND', 'FINS', 'FINX', 'FIOGF', 'FIRE', 'FIS', 'FISI', 'FITB', 'FITBI', 'FITBO', 'FIV', 'FIVG', 'FIX', 'FIXD', 'FIXX', 'FKU', 'FKYS', 'FLAT', 'FLC', 'FLES', 'FLEX', 'FLGT', 'FLIC', 'FLIR', 'FLL', 'FLLV', 'FLMN', 'FLN', 'FLNG', 'FLO', 'FLOOF', 'FLOT', 'FLOW', 'FLR', 'FLRN', 'FLS', 'FLT', 'FLUX', 'FLWS', 'FLXS', 'FLY', 'FM', 'FMAO', 'FMB', 'FMBH', 'FMBI', 'FMBM', 'FMCC', 'FMCI', 'FMCIU', 'FMCKJ', 'FMN', 'FMNB', 'FMO', 'FMS', 'FMX', 'FMY', 'FN', 'FNB', 'FNCB', 'FNCL', 'FND', 'FNDC', 'FNDE', 'FNDF', 'FNDX', 'FNF', 'FNGD', 'FNGR', 'FNGU', 'FNHC', 'FNI', 'FNJN', 'FNK', 'FNLC', 'FNMA', 'FNMAL', 'FNMAS', 'FNMFM', 'FNRN', 'FNV', 'FNWB', 'FNX', 'FNY', 'FOCS', 'FOE', 'FOF', 'FONR', 'FOR', 'FORD', 'FORK', 'FORM', 'FORR', 'FORTY', 'FOX', 'FOXA', 'FOXF', 'FPAC', 'FPE', 'FPF', 'FPH', 'FPI', 'FPL', 'FPPP', 'FPRX', 'FPXI', 'FR', 'FRA', 'FRAF', 'FRBA', 'FRBK', 'FRC', 'FRCK', 'FRD', 'FREL', 'FREQ', 'FRFHF', 'FRGI', 'FRHC', 'FRLG', 'FRLI', 'FRME', 'FRO', 'FROPX', 'FRPH', 'FRPT', 'FRSX', 'FRT', 'FRTA', 'FRZT', 'FSB', 'FSBW', 'FSCSX', 'FSD', 'FSEA', 'FSEN', 'FSFG', 'FSI', 'FSK', 'FSLY', 'FSNUF', 'FSP', 'FSRVU', 'FSS', 'FSSN', 'FSTR', 'FSUGY', 'FSV', 'FSZ', 'FT', 'FTA', 'FTAC', 'FTAI', 'FTC', 'FTCH', 'FTCS', 'FTDR', 'FTEG', 'FTEK', 'FTF', 'FTGC', 'FTHI', 'FTI', 'FTK', 'FTLB', 'FTLF', 'FTM', 'FTNW', 'FTRI', 'FTS', 'FTSI', 'FTSL', 'FTSM', 'FTSSF', 'FTV', 'FTXD', 'FTXG', 'FTXL', 'FTXN', 'FTXO', 'FTXP', 'FUJHY', 'FUJIY', 'FUL', 'FULC', 'FULT', 'FUNC', 'FUND', 'FUNN', 'FURCF', 'FUSB', 'FUTU', 'FUTY', 'FV', 'FVC', 'FVCB', 'FVD', 'FVE', 'FVRR', 'FWONA', 'FWONK', 'FWP', 'FWRD', 'FXA', 'FXB', 'FXC', 'FXE', 'FXF', 'FXNC', 'FXP', 'FXY', 'FYGGY', 'FYRTY', 'FYX', 'G', 'GAB', 'GABC', 'GABLF', 'GAIA', 'GAIN', 'GAINM', 'GALE', 'GAM', 'GAMR', 'GARS', 'GAS', 'GASS', 'GATX', 'GAXY', 'GAYMF', 'GBAB', 'GBCI', 'GBCS', 'GBDC', 'GBIL', 'GBIM', 'GBL', 'GBLI', 'GBLX', 'GBOOY', 'GBP', 'GBTC', 'GBX', 'GCAP', 'GCBC', 'GCC', 'GCEI', 'GCI', 'GCO', 'GCP', 'GCV', 'GD', 'GDEN', 'GDET', 'GDL', 'GDLNF', 'GDO', 'GDOT', 'GDP', 'GDS', 'GDV', 'GEC', 'GECC', 'GEF', 'GEL', 'GELYY', 'GEM', 'GEN', 'GENC', 'GENE', 'GENX', 'GENY', 'GEO', 'GEOS', 'GER', 'GES', 'GETH', 'GETVY', 'GF', 'GFASY', 'GFED', 'GFF', 'GFI', 'GFIN', 'GFN', 'GFNCP', 'GFTX', 'GFY', 'GGAL', 'GGB', 'GGBXF', 'GGG', 'GGM', 'GGN', 'GGO', 'GGT', 'GGTTF', 'GGZ', 'GHC', 'GHG', 'GHL', 'GHM', 'GHSI', 'GHY', 'GIB', 'GIDYL', 'GIFI', 'GIGA', 'GIGB', 'GIGE', 'GIGM', 'GIII', 'GIL', 'GILT', 'GIM', 'GIX', 'GJO', 'GJP', 'GJR', 'GJT', 'GKOS', 'GL', 'GLAD', 'GLBR', 'GLBZ', 'GLCO', 'GLDD', 'GLDI', 'GLDLF', 'GLDM', 'GLGI', 'GLIBA', 'GLIBP', 'GLL', 'GLNCY', 'GLNG', 'GLO', 'GLOB', 'GLOG', 'GLOP', 'GLP', 'GLPG', 'GLPI', 'GLQ', 'GLRE', 'GLT', 'GLU', 'GLV', 'GLXZ', 'GLYC', 'GMAB', 'GMAN', 'GMBL', 'GMDA', 'GMGI', 'GMHI', 'GMHIU', 'GMLP', 'GMNI', 'GMO', 'GMRE', 'GMS', 'GMZ', 'GNBT', 'GNE', 'GNFT', 'GNK', 'GNL', 'GNLN', 'GNMA', 'GNMK', 'GNOM', 'GNPX', 'GNRC', 'GNSS', 'GNT', 'GNTX', 'GNTY', 'GNUS', 'GNW', 'GO', 'GOEX', 'GOF', 'GOGL', 'GOL', 'GOLF', 'GOOD', 'GOODM', 'GORO', 'GOSS', 'GOVT', 'GPAQ', 'GPAQU', 'GPC', 'GPFOF', 'GPI', 'GPJA', 'GPK', 'GPM', 'GPMT', 'GPN', 'GPP', 'GPRE', 'GPRK', 'GPX', 'GRA', 'GRAF', 'GRAM', 'GRBK', 'GRC', 'GRCK', 'GREK', 'GRES', 'GRF', 'GRFS', 'GRID', 'GRIF', 'GRIN', 'GRMC', 'GRNQ', 'GRSHU', 'GRSO', 'GRTS', 'GRUSF', 'GRVY', 'GRWC', 'GRWG', 'GRX', 'GRYN', 'GSB', 'GSBC', 'GSBD', 'GSC', 'GSG', 'GSH', 'GSHD', 'GSIE', 'GSIT', 'GSLC', 'GSV', 'GSX', 'GT', 'GTAT', 'GTBIF', 'GTE', 'GTEC', 'GTEH', 'GTES', 'GTHX', 'GTIM', 'GTLS', 'GTN', 'GTS', 'GTX', 'GTY', 'GTYH', 'GULF', 'GUNR', 'GURE', 'GUT', 'GV', 'GVA', 'GVP', 'GWB', 'GWGH', 'GWRE', 'GWRS', 'GWTI', 'GWW', 'GXC', 'GXG', 'GXGX', 'GXGXU', 'GXTG', 'GXXM', 'GYRO', 'GZTGF', 'HACK', 'HAE', 'HAFC', 'HALL', 'HALO', 'HAON', 'HAPP', 'HARP', 'HASI', 'HAYN', 'HBAN', 'HBANN', 'HBANO', 'HBB', 'HBC', 'HBCP', 'HBCYF', 'HBIO', 'HBM', 'HBMD', 'HBNC', 'HBP', 'HBT', 'HBUV', 'HCA', 'HCAC', 'HCACU', 'HCAP', 'HCAT', 'HCC', 'HCCH', 'HCCI', 
        # 'HCFT', 'HCHC', 'HCI', 'HCKT', 'HCM', 'HCMLY', 'HCR', 'HCSG', 'HCXY', 'HCXZ', 'HCYT', 'HDB', 'HDGE', 'HDII', 'HDS', 'HDSN', 'HE', 'HEBT', 'HEDJ', 'HEES', 'HEFA', 'HEINY', 'HELE', 'HEMP', 'HEP', 'HEPA', 'HEQ', 'HERO', 'HES', 'HESM', 'HEWJ', 'HEXO', 'HFBL', 'HFFG', 'HFRO', 'HFWA', 'HFXI', 'HGH', 'HGKGY', 'HGLB', 'HGSH', 'HGV', 'HHC', 'HHR', 'HHS', 'HHT', 'HI', 'HIE', 'HIFS', 'HIG', 'HIHO', 'HIL', 'HIO', 'HIPH', 'HISEF', 'HITIF', 'HIW', 'HIX', 'HJLI', 'HKIB', 'HKMPY', 'HKXCY', 'HLAL', 'HLG', 'HLI', 'HLIO', 'HLIT', 'HLIX', 'HLNE', 'HLTOY', 'HLTY', 'HLX', 'HMC', 'HMG', 'HMHC', 'HMI', 'HMLA', 'HMLP', 'HMLSF', 'HMMR', 'HMN', 'HMNF', 'HMPQ', 'HMST', 'HMSY', 'HMTV', 'HMY', 'HNDL', 'HNGR', 'HNHPF', 'HNI', 'HNNA', 'HNNMY', 'HNP', 'HNRG', 'HNW', 'HOFT', 'HOLI', 'HOLX', 'HOMB', 'HOME', 'HON', 'HONE', 'HOOK', 'HOPE', 'HOT', 'HOTH', 'HOV', 'HOVNP', 'HP', 'HPF', 'HPGLY', 'HPI', 'HPMM', 'HPP', 'HPS', 'HQH', 'HQI', 'HQL', 'HQY', 'HR', 'HRB', 'HRC', 'HRI', 'HRL', 'HRNNF', 'HRSMF', 'HRTG', 'HRVOF', 'HRVSF', 'HRZN', 'HSBC', 'HSC', 'HSDEF', 'HSDT', 'HSI', 'HSII', 'HSKA', 'HSNGY', 'HSON', 'HST', 'HSTM', 'HSY', 'HT', 'HTA', 'HTBI', 'HTBK', 'HTD', 'HTFA', 'HTGC', 'HTH', 'HTHIY', 'HTHT', 'HTL', 'HTLD', 'HTLF', 'HTY', 'HUB', 'HUBB', 'HUBG', 'HUD', 'HUGE', 'HUN', 'HURC', 'HURN', 'HVBC', 'HVBTF', 'HVN', 'HVT', 'HWBK', 'HWC', 'HWCC', 'HWCPL', 'HWKN', 'HX', 'HXL', 'HY', 'HYAC', 'HYACU', 'HYB', 'HYDB', 'HYGH', 'HYI', 'HYLB', 'HYLS', 'HYLV', 'HYMB', 'HYMTF', 'HYND', 'HYSR', 'HYT', 'HYXE', 'HYZD', 'HZNQF', 'HZO', 'I', 'IAA', 'IAC', 'IAE', 'IAF', 'IAG', 'IAGG', 'IAI', 'IART', 'IASMX', 'IAU', 'IBA', 'IBCP', 'IBKC', 'IBKCN', 'IBKCO', 'IBKCP', 'IBKR', 'IBN', 'IBOC', 'IBP', 'IBTX', 'IBUY', 'ICAD', 'ICAGY', 'ICBK', 'ICCC', 'ICCH', 'ICD', 'ICE', 'ICFI', 'ICHR', 'ICK', 'ICL', 'ICLD', 'ICLK', 'ICLN', 'ICLR', 'ICMB', 'ICNB', 'ICPBF', 'ICSH', 'ICUI', 'IDA', 'IDCC', 'IDE', 'IDN', 'IDT', 'IDU', 'IDV', 'IDWM', 'IDX', 'IDXX', 'IDYA', 'IEA', 'IEC', 'IEFA', 'IEHC', 'IEI', 'IEMG', 'IEO', 'IEP', 'IESC', 'IEUR', 'IEUS', 'IEV', 'IEX', 'IFGL', 'IFN', 'IFNNY', 'IFNY', 'IFRX', 'IFS', 'IFV', 'IG', 'IGA', 'IGAP', 'IGC', 'IGD', 'IGEN', 'IGEX', 'IGF', 'IGGGF', 'IGI', 'IGIB', 'IGMS', 'IGN', 'IGOV', 'IGR', 'IGSB', 'IGXT', 'IHC', 'IHD', 'IHDG', 'IHE', 'IHF', 'IHG', 'IHI', 'IHIT', 'IHRT', 'IHT', 'IHTA', 'IID', 'IIF', 'III', 'IIIN', 'IIIV', 'IIJIY', 'IIM', 'IIN', 'IIPZF', 'IJH', 'IJJ', 'IJK', 'IJR', 'IJS', 'IJT', 'IKNX', 'ILCC', 'ILF', 'ILPT', 'IMAC', 'IMAX', 'IMBBY', 'IMBI', 'IMH', 'IMKTA', 'IMLE', 'IMMR', 'IMO', 'IMOS', 'IMP', 'IMPUY', 'IMRN', 'IMTE', 'IMUC', 'IMUX', 'IMV', 'IMXI', 'INBK', 'INBP', 'INDA', 'INDB', 'INDL', 'INDY', 'INF', 'INFO', 'INFR', 'INFU', 'INFY', 'ING', 'INGN', 'INGR', 'INGXF', 'INLX', 'INMB', 'INMD', 'INN', 'INND', 'INNO', 'INNT', 'INOD', 'INOV', 'INPTF', 'INS', 'INSE', 'INSG', 'INSHF', 'INSI', 'INSM', 'INSP', 'INSU', 'INSUU', 'INSW', 'INT', 'INTF', 'INTG', 'INTI', 'INTL', 'INTT', 'INUV', 'INVE', 'INVH', 'INVT', 'INVVY', 'INWK', 'IO', 'IOR', 'IOSP', 'IOVA', 'IPAC', 'IPAR', 'IPAY', 'IPCIF', 'IPDN', 'IPG', 'IPHA', 'IPHI', 'IPIX', 'IPLDP', 'IPLY', 'IPO', 'IPPLF', 'IPWR', 'IQI', 'IR', 'IRCP', 'IRDM', 'IRET', 'IRIX', 'IRL', 'IRM', 'IRMD', 'IRNC', 'IROQ', 'IRR', 'IRS', 'IRT', 'IRTC', 'IRVRF', 'IRWD', 'ISBA', 'ISBC', 'ISCO', 'ISD', 'ISDR', 'ISDS', 'ISDX', 'ISEE', 'ISG', 'ISHG', 'ISIG', 'ISNS', 'ISOLF', 'ISRA', 'ISSC', 'ISTB', 'ISTR', 'IT', 'ITA', 'ITB', 'ITC', 'ITCB', 'ITCI', 'ITEQ', 'ITGR', 'ITHUF', 'ITI', 'ITIC', 'ITMR', 'ITOT', 'ITRI', 'ITRM', 'ITRN', 'ITT', 'ITUB', 'ITVPY', 'ITW', 'IUS', 'IUSB', 'IUSG', 'IUSV', 'IVAC', 'IVC', 'IVE', 'IVFH', 'IVH', 'IVOG', 'IVOO', 'IVR', 'IVV', 'IVW', 'IVZ', 'IWB', 'IWC', 'IWD', 'IWF', 'IWN', 'IWO', 'IWS', 'IWSY', 'IWV', 'IX', 'IXC', 'IXG', 'IXJ', 'IXP', 'IXUS', 'IYE', 'IYF', 'IYG', 'IYH', 'IYK', 'IYT', 'IYW', 'IYZ', 'JAKK', 'JAN', 'JANL', 'JASN', 'JAX', 'JBGS', 'JBHT', 'JBK', 'JBL', 'JBSAY', 'JBSS', 'JBT', 'JCAP', 'JCE', 'JCI', 'JCO', 'JCOM', 'JCP', 'JCS', 'JCTCF', 'JDD', 'JE', 'JEF', 'JELD', 'JEMD', 'JEQ', 'JETS', 'JFIN', 'JFK', 'JFKKU', 'JFR', 'JFU', 'JG', 'JGH', 'JHB', 'JHG', 'JHI', 'JHS', 'JHX', 'JHY', 'JILL', 'JJC', 'JJGTF', 'JJN', 'JJNTF', 'JJSF', 'JKH', 'JKHY', 'JKI', 'JKRO', 'JLL', 'JLS', 'JMIA', 'JMOM', 'JMP', 'JNCE', 'JNK', 'JOB', 'JOBS', 'JOE', 'JOF', 'JOUT', 'JP', 'JPC', 'JPI', 'JPIN', 'JPN', 'JPS', 'JPST', 'JPXGY', 'JQC', 'JRI', 'JRJC', 'JRO', 'JRS', 'JRSH', 'JRVR', 'JSD', 'JSDA', 'JSHG', 'JSMD', 'JTA', 'JTD', 'JUMT', 'JUST', 'JVTSF', 'JYNT', 'KAI', 'KALU', 'KALV', 'KALY', 'KAMN', 'KAR', 'KB', 'KBA', 'KBAL', 'KBCSF', 'KBCSY', 'KBE', 'KBEVF', 'KBLB', 'KBLM', 'KBLMU', 'KBR', 'KBWB', 'KBWD', 'KBWP', 'KBWR', 'KBWY', 'KC', 'KCDMY', 'KCLI', 'KDP', 'KE', 'KELYA', 'KELYB', 'KEN', 'KEP', 'KEQU', 'KERN', 'KEX', 'KEY', 'KEYS', 'KF', 'KFFB', 'KFRC', 'KFS', 'KFY', 'KGJI', 'KGKG', 'KHRNF', 'KIDS', 'KIM', 'KIN', 'KINS', 'KIO', 'KIQ', 'KIRK', 'KKR', 'KLAC', 'KLDO', 'KLIC', 'KLXE', 'KMDA', 'KMF', 'KMPR', 'KMT', 'KN', 'KNL', 'KNMCY', 'KNOP', 'KNRRY', 'KNSA', 'KNSL', 'KNTNF', 'KNX', 'KOD', 'KOF', 'KOL', 'KOLD', 'KOP', 'KOPN', 'KORU', 'KOS', 'KOSS', 'KRA', 'KRC', 'KRE', 'KREF', 'KRFG', 'KRG', 'KRIUF', 'KRMA', 'KRMD', 'KRNT', 'KRNY', 'KRO', 'KRP', 'KRTX', 'KRUS', 'KRYS', 'KSA', 'KSHB', 'KSM', 'KSU', 'KT', 'KTB', 'KTCC', 'KTF', 'KTH', 'KTN', 'KTYB', 'KURA', 'KVHI', 'KW', 'KWR', 'KXIN', 'KYN', 'KZIA', 'KZR', 'L', 'LACQ', 'LADR', 'LAIX', 'LAKE', 'LAKF', 'LAMR', 'LANC', 'LAND', 'LANDP', 'LARK', 'LASR', 'LATNU', 'LAUR', 'LAWS', 'LAZ', 'LAZY', 'LBAI', 'LBAS', 'LBC', 'LBCC', 'LBRDA', 'LBRDK', 'LBRT', 'LBSR', 'LBTYA', 'LBTYB', 'LBTYK', 'LBUY', 'LBY', 'LCA', 'LCAHU', 'LCII', 'LCNB', 'LCRDX', 'LCTX', 'LCUT', 'LDDFF', 'LDL', 'LDNXF', 'LDOS', 'LDP', 'LDSF', 'LDSI', 'LDUR', 'LE', 'LEA', 'LEAD', 'LEAF', 'LEAI', 'LECO', 'LEE', 'LEG', 'LEGH', 'LEGR', 'LEJU', 'LEMB', 'LEND', 'LEO', 'LEU', 'LEVI', 'LEVL', 'LFAC', 'LFACU', 'LFAP', 'LFC', 'LFIN', 'LFUS', 'LFVN', 'LGC', 'LGI', 'LGIH', 'LGL', 'LGLV', 'LH', 'LHC', 'LHCG', 'LHSIF', 'LHX', 'LIFZF', 'LIGA', 'LII', 'LILA', 'LILAK', 'LIN', 'LINC', 'LIND', 'LINK', 'LINX', 'LIT', 'LITB', 'LIVE', 'LIVN', 'LIVX', 'LK', 'LKAI', 'LKCO', 'LKFN', 'LKQ', 'LKREF', 'LLEX', 'LLIT', 'LLLI', 'LLNW', 'LM', 'LMAT', 'LMB', 'LMBS', 'LMNR', 'LMNX', 'LMRK', 'LMRKN', 'LMRKO', 'LMST', 'LN', 'LNC', 'LND', 'LNDC', 'LNG', 'LNGLY', 'LNGR', 'LNN', 'LNSTY', 'LNT', 'LNTH', 'LOAC', 'LOACU', 'LOAN', 'LOB', 'LOCO', 'LOGC', 'LOGI', 'LOMA', 'LONE', 'LOOP', 'LOPE', 'LORL', 'LOV', 'LOVE', 'LOVFF', 'LPG', 'LPL', 'LPLA', 'LPSN', 'LPTH', 'LPX', 'LQDA', 'LQDH', 'LQDT', 'LRCDF', 'LRDC', 'LRGF', 'LRLCY', 'LRN', 'LRTNF', 'LSBK', 'LSI', 'LSTR', 'LSXMA', 'LSXMB', 'LSXMK', 'LSYN', 'LTC', 'LTIFX', 'LTL', 'LTM', 'LTRPA', 'LTRPB', 'LUB', 'LUKOY', 'LUNA', 'LVBX', 'LVGO', 'LVHD', 'LVMHF', 'LVMUY', 'LW', 'LWAY', 'LWLG', 'LX', 'LXFR', 'LXP', 'LXRP', 'LXU', 'LYB', 'LYFT', 'LYL', 'LYSCF', 'LYSDY', 'LYTS', 'LYV', 'LZAGY', 'LZB', 'LZRFY', 'MAA', 'MAANF', 'MAAX', 'MAC', 'MACE', 'MACK', 'MAG', 'MAGS', 'MAIN', 'MAKE', 'MAN', 'MANH', 'MANT', 'MANU', 'MARPS', 'MAS', 'MASI', 'MATN', 'MATW', 'MATX', 'MAV', 'MAYS', 'MBB', 'MBCN', 'MBI', 'MBIN', 'MBIO', 'MBSD', 'MBT', 'MBUU', 'MBWM', 'MC', 'MCA', 'MCB', 'MCBC', 'MCBS', 'MCC', 'MCCX', 'MCEF', 'MCEP', 'MCF', 'MCFT', 'MCFUF', 'MCHI', 'MCHP', 'MCHX', 'MCI', 'MCIG', 'MCN', 'MCO', 'MCOA', 'MCP', 'MCR', 'MCRB', 'MCRI', 'MCS', 'MCTC', 'MCV', 'MCX', 'MCY', 'MD', 'MDC', 'MDCA', 'MDFZF', 'MDIV', 'MDJH', 'MDLA', 'MDLQ', 'MDLX', 'MDLY', 'MDLZ', 'MDP', 'MDRR', 'MDU', 'MDWD', 'MDXG', 'MDY', 'MEC', 'MEDIF', 'MEEC', 'MEI', 'MEN', 'MEOH', 'MERC', 'MESA', 'MESO', 'MET', 'METC', 'MEXX', 'MFA', 'MFAC', 'MFC', 'MFD', 'MFG', 'MFGP', 'MFIN', 'MFINL', 'MFL', 'MFM', 'MFMS', 'MFNC', 'MFO', 'MFON', 'MFST', 'MFT', 'MFV', 'MG', 'MGA', 'MGC', 'MGDDY', 'MGEE', 'MGEN', 'MGF', 'MGGPX', 'MGI', 'MGIC', 'MGLN', 'MGNT', 'MGP', 'MGPI', 'MGR', 'MGRC', 'MGTA', 'MGTI', 'MGTX', 'MGU', 'MGV', 'MGY', 'MGYR', 'MHD', 'MHE', 'MHF', 'MHGVY', 'MHH', 'MHI', 'MHLA', 'MHLD', 'MHN', 'MHO', 'MICR', 'MIDD', 'MIE', 'MIHI', 'MIK', 'MILN', 'MIN', 'MIND', 'MINDP', 'MINI', 'MINT', 'MIRM', 'MIST', 'MITO', 'MITT', 'MIXT', 'MIY', 'MJARF', 'MJCO', 'MJNA', 'MJNE', 'MKGI', 'MKKGY', 'MKL', 'MKSI', 'MKTX', 'MLAB', 'MLGF', 'MLHR', 'MLI', 'MLM', 'MLND', 'MLP', 'MLPA', 'MLPX', 'MLR', 'MLVF', 'MLXEF', 'MLYF', 'MMAC', 'MMC', 'MMD', 'MMEX', 'MMI', 'MMIN', 'MMLP', 'MMMB', 'MMNFF', 'MMP', 'MMS', 'MMSI', 'MMT', 'MMU', 'MMX', 'MMYT', 'MN', 'MNCL', 'MNCLU', 'MNDO', 'MNE', 'MNLO', 'MNOV', 'MNP', 'MNR', 'MNRL', 'MNRO', 'MNSB', 'MNTA', 'MNTX', 'MOAT', 'MOBL', 'MOBQ', 'MOD', 'MODD', 'MODN', 'MOFG', 'MOGO', 'MOGU', 'MOO', 'MOR', 'MORF', 'MORN', 'MORT', 'MOS', 'MOTS', 'MOV', 'MOXC', 'MPA', 'MPAA', 'MPB', 'MPLX', 'MPNGF', 'MPV', 'MPW', 'MPWR', 'MPX', 'MQT', 'MQY', 'MR', 'MRAM', 'MRBK', 'MRC', 'MRCC', 'MRCY', 'MREO', 'MRLN', 'MRMD', 'MRSN', 'MRTN', 'MRUS', 'MSA', 'MSB', 'MSBF', 'MSBHY', 'MSBI', 'MSC', 'MSCI', 'MSD', 'MSEX', 'MSG', 'MSGN', 'MSM', 'MSN', 'MSNVF', 'MSON', 'MSTR', 'MSVB', 'MT', 'MTB', 'MTBCP', 'MTC', 'MTEM', 'MTEX', 'MTG', 'MTH', 'MTL', 'MTLS', 'MTOR', 'MTR', 'MTRN', 'MTRX', 'MTSC', 'MTSI', 'MTT', 'MTUM', 'MTW', 'MTWD', 'MTX', 'MTYFF', 'MTZ', 'MUA', 'MUB', 'MUC', 'MUDSU', 'MUE', 'MUFG', 'MUH', 'MUI', 'MUJ', 'MUR', 'MUS', 'MUSA', 'MVBF', 'MVC', 'MVEN', 'MVF', 'MVO', 'MVT', 'MVV', 'MWA', 'MWK', 'MX', 'MXC', 'MXE', 'MXF', 'MXIM', 'MXL', 'MXSG', 'MYC', 'MYD', 'MYDP', 'MYE', 'MYF', 'MYFW', 'MYGN', 'MYI', 'MYJ', 'MYN', 'MYOS', 'MYOV', 'MYRG', 'MYRX', 'MYT', 'MZA', 'MZDAY', 'MZZ', 'NAC', 'NACNF', 'NAD', 'NAII', 'NAIL', 'NAN', 'NANX', 'NAOV', 'NATH', 'NATI', 'NATR', 'NAUH', 'NAV', 'NAVI', 'NAZ', 'NB', 'NBB', 'NBGV', 'NBH', 'NBHC', 'NBI', 'NBIO', 'NBLX', 'NBN', 'NBO', 'NBSE', 'NBTB', 'NBW', 'NBY', 'NC', 'NCA', 'NCB', 'NCBS', 'NCMI', 'NCNA', 'NCNNF', 'NCR', 'NCSM', 'NCV', 'NCZ', 'NDAQ', 'NDLS', 'NDP', 'NDSN', 'NDX', 'NE', 'NEA', 'NEAR', 'NEBU', 'NEBUU', 'NEE', 'NEED', 'NEL', 'NEN', 'NEO', 'NEOG', 'NEP', 'NEPH', 'NERD', 'NERV', 'NES', 'NESR', 'NESRF', 'NET', 'NETL', 'NEU', 'NEV', 'NEW', 'NEWA', 'NEWR', 'NEWT', 'NEX', 'NEXA', 'NEXCF', 'NEXOF', 'NEXT', 'NFBK', 'NFC', 'NFE', 'NFG', 'NFIN', 
        # 'NFINU', 'NFJ', 'NFTY', 'NG', 'NGCG', 'NGE', 'NGG', 'NGHC', 'NGHCN', 'NGHCO', 'NGHCP', 'NGL', 'NGM', 'NGS', 'NGTF', 'NGVC', 'NGVT', 'NHA', 'NHC', 'NHCZF', 'NHF', 'NHI', 'NHLD', 'NHS', 'NHTC', 'NHYDY', 'NI', 'NIB', 'NICE', 'NICK', 'NID', 'NIE', 'NIM', 'NIMU', 'NINE', 'NIQ', 'NISTF', 'NIU', 'NJR', 'NJV', 'NKG', 'NKSH', 'NKX', 'NL', 'NLBIF', 'NLS', 'NLST', 'NLTX', 'NLY', 'NM', 'NMCI', 'NMCO', 'NMFC', 'NMI', 'NMIH', 'NML', 'NMM', 'NMR', 'NMRK', 'NMS', 'NMT', 'NMTC', 'NMY', 'NMZ', 'NNA', 'NNBR', 'NNDM', 'NNDNF', 'NNI', 'NNN', 'NNRX', 'NNVC', 'NNY', 'NOA', 'NOAH', 'NOBH', 'NOBL', 'NOC', 'NODK', 'NOHO', 'NOKBF', 'NOM', 'NOMD', 'NONOF', 'NOUV', 'NOV', 'NOVA', 'NOVN', 'NOVT', 'NP', 'NPA', 'NPAUU', 'NPK', 'NPN', 'NPO', 'NPSNY', 'NPTN', 'NPV', 'NR', 'NRC', 'NRCI', 'NRDBY', 'NRG', 'NRGX', 'NRIFF', 'NRIM', 'NRK', 'NRO', 'NRP', 'NRT', 'NRUC', 'NS', 'NSA', 'NSANY', 'NSC', 'NSCO', 'NSEC', 'NSFDF', 'NSIT', 'NSL', 'NSRGY', 'NSRPF', 'NSS', 'NSSC', 'NSTG', 'NSYS', 'NTB', 'NTCT', 'NTDOY', 'NTG', 'NTIC', 'NTIOF', 'NTIP', 'NTL', 'NTN', 'NTP', 'NTR', 'NTRA', 'NTRP', 'NTRR', 'NTRS', 'NTSFF', 'NTTYY', 'NTUS', 'NTZ', 'NUAN', 'NUBD', 'NUGS', 'NUM', 'NUO', 'NURO', 'NUUU', 'NUV', 'NUVA', 'NUVBX', 'NUVI', 'NUVR', 'NUW', 'NUZE', 'NVEC', 'NVEE', 'NVFY', 'NVG', 'NVGI', 'NVGS', 'NVIV', 'NVMI', 'NVO', 'NVR', 'NVRO', 'NVS', 'NVSEF', 'NVST', 'NVT', 'NVTR', 'NVUS', 'NVZMY', 'NWBI', 'NWBO', 'NWE', 'NWFL', 'NWHM', 'NWLI', 'NWN', 'NWPP', 'NWPX', 'NWS', 'NWSA', 'NX', 'NXC', 'NXE', 'NXGN', 'NXN', 'NXP', 'NXQ', 'NXR', 'NXRT', 'NXST', 'NXTC', 'NXTG', 'NXTTF', 'NYA', 'NYCB', 'NYMT', 'NYMTM', 'NYMTN', 'NYMTO', 'NYMTP', 'NYMX', 'NYT', 'NZF', 'OAC', 'OAOFY', 'OBAS', 'OBCI', 'OBMP', 'OBNK', 'OBNNF', 'OBOR', 'OBSV', 'OC', 'OCC', 'OCCI', 'OCFC', 'OCGN', 'OCSI', 'OCSL', 'ODC', 'ODFL', 'ODT', 'OEC', 'OEF', 'OESX', 'OFC', 'OFED', 'OFG', 'OFIX', 'OFLX', 'OFS', 'OGC', 'OGE', 'OGI', 'OGIG', 'OGS', 'OGZPY', 'OI', 'OIA', 'OII', 'OIIM', 'OILNF', 'OIS', 'OKE', 'OLD', 'OLLI', 'OLP', 'OMAB', 'OMC', 'OMCL', 'OMEX', 'OMF', 'OMP', 'ONB', 'ONCT', 'ONDS', 'ONE', 'ONEQ', 'ONTO', 'OOMA', 'OPBK', 'OPES', 'OPHC', 'OPI', 'OPNT', 'OPOF', 'OPP', 'OPRA', 'OPRT', 'OPRX', 'OPTN', 'OPVS', 'OPY', 'OPYGY', 'OR', 'ORA', 'ORAN', 'ORBC', 'ORC', 'ORCC', 'ORGH', 'ORGS', 'ORHB', 'ORI', 'ORLY', 'ORMP', 'ORN', 'OROCF', 'OROVY', 'ORRF', 'ORSNU', 'ORTX', 'OSB', 'OSBC', 'OSG', 'OSIS', 'OSMT', 'OSN', 'OSPN', 'OSS', 'OSSIF', 'OSUR', 'OSW', 'OTCM', 'OTEL', 'OTEX', 'OTLK', 'OTTR', 'OTTV', 'OTTW', 'OUNZ', 'OUSM', 'OUT', 'OVBC', 'OVLY', 'OWCP', 'OXBR', 'OXFD', 'OXLCO', 'OXM', 'OXSQ', 'OXSQZ', 'OYST', 'OZK', 'OZSC', 'PAA', 'PAAC', 'PAACU', 'PAAS', 'PAC', 'PACB', 'PACD', 'PACK', 'PACQ', 'PACQU', 'PACQW', 'PACV', 'PACW', 'PAG', 'PAGP', 'PAHC', 'PAI', 'PAK', 'PAM', 'PANL', 'PAOS', 'PAR', 'PARF', 'PARR', 'PASO', 'PASS', 'PATI', 'PATK', 'PAWZ', 'PAYC', 'PAYS', 'PAYX', 'PB', 'PBA', 'PBB', 'PBC', 'PBCT', 'PBCTP', 'PBD', 'PBF', 'PBFS', 'PBFX', 'PBH', 'PBHC', 'PBIO', 'PBIP', 'PBJ', 'PBMLF', 'PBPB', 'PBS', 'PBSV', 'PBT', 'PBTS', 'PBW', 'PBY', 'PCAR', 'PCB', 'PCEF', 'PCF', 'PCH', 'PCI', 'PCK', 'PCM', 'PCN', 'PCOM', 'PCQ', 'PCRFY', 'PCRX', 'PCSB', 'PCTI', 'PCTL', 'PCTY', 'PCY', 'PCYG', 'PCYO', 'PD', 'PDBC', 'PDCE', 'PDCO', 'PDEV', 'PDEX', 'PDFS', 'PDI', 'PDL', 'PDLB', 'PDLI', 'PDM', 'PDN', 'PDP', 'PDS', 'PDSB', 'PDT', 'PEB', 'PEBK', 'PEBO', 'PECK', 'PEER', 'PEG', 'PEGA', 'PEIX', 'PEN', 'PENN', 'PEO', 'PER', 'PERI', 'PESI', 'PETS', 'PETZ', 'PEY', 'PEYE', 'PEYUF', 'PEZ', 'PFBC', 'PFBI', 'PFC', 'PFD', 'PFF', 'PFG', 'PFGC', 'PFI', 'PFIE', 'PFIN', 'PFIS', 'PFL', 'PFLT', 'PFM', 'PFMS', 'PFMT', 'PFN', 'PFO', 'PFPT', 'PFS', 'PFSI', 'PFSW', 'PGC', 'PGF', 'PGH', 'PGJ', 'PGM', 'PGNY', 'PGOL', 'PGP', 'PGR', 'PGRE', 'PGTI', 'PGTK', 'PGUS', 'PGX', 'PGZ', 'PH', 'PHAS', 'PHAT', 'PHB', 'PHBI', 'PHCF', 'PHD', 'PHG', 'PHGE', 'PHI', 'PHIO', 'PHK', 'PHM', 'PHO', 'PHOT', 'PHR', 'PHT', 'PHX', 'PHYS', 'PI', 'PIC', 'PICB', 'PICK', 'PICO', 'PID', 'PIE', 'PIH', 'PIHPP', 'PII', 'PIM', 'PIN', 'PINC', 'PING', 'PINS', 'PIO', 'PIZ', 'PJET', 'PJH', 'PJP', 'PJT', 'PK', 'PKBK', 'PKE', 'PKG', 'PKI', 'PKO', 'PKOH', 'PKW', 'PKX', 'PLAB', 'PLBC', 'PLC', 'PLD', 'PLDGP', 'PLIN', 'PLL', 'PLMR', 'PLNHF', 'PLOW', 'PLPC', 'PLSE', 'PLSI', 'PLT', 'PLTM', 'PLUS', 'PLW', 'PLXP', 'PLXS', 'PLYA', 'PLYM', 'PMBC', 'PMCB', 'PMD', 'PME', 'PMF', 'PML', 'PMM', 'PMO', 'PMT', 'PMTS', 'PMX', 'PNBK', 'PNF', 'PNFP', 'PNGAY', 'PNI', 'PNM', 'PNNT', 'PNQI', 'PNR', 'PNRG', 'PNTG', 'PNW', 'POAI', 'PODD', 'POGRX', 'POL', 'POLA', 'POOL', 'POR', 'POST', 'POTN', 'POTX', 'POW', 'POWI', 'POWL', 'PPA', 'PPAL', 'PPBI', 'PPC', 'PPCB', 'PPCCY', 'PPG', 'PPH', 'PPHI', 'PPIH', 'PPJE', 'PPL', 'PPLT', 'PPR', 'PPRQF', 'PPRUY', 'PPSI', 'PPT', 'PPX', 'PQG', 'PRA', 'PRAA', 'PRAH', 'PRCP', 'PRDEX', 'PRED', 'PRF', 'PRFT', 'PRFZ', 'PRGS', 'PRGTX', 'PRGX', 'PRH', 'PRHSX', 'PRI', 'PRIM', 'PRK', 'PRKR', 'PRLB', 'PRMW', 'PRN', 'PRNB', 'PRNT', 'PRO', 'PROF', 'PROS', 'PROV', 'PRPH', 'PRPL', 'PRQR', 'PRS', 'PRSC', 'PRSP', 'PRT', 'PRTA', 'PRTH', 'PRTS', 'PRU', 'PRVB', 'PRVL', 'PS', 'PSA', 'PSB', 'PSC', 'PSCC', 'PSCD', 'PSCE', 'PSCF', 'PSCH', 'PSCI', 'PSCM', 'PSCT', 'PSCU', 'PSF', 'PSI', 'PSIX', 'PSJ', 'PSK', 'PSL', 'PSLDX', 'PSLV', 'PSM', 'PSMT', 'PSN', 'PSNL', 'PSO', 'PSP', 'PSQ', 'PST', 'PSTI', 'PSTL', 'PSTV', 'PSV', 'PSX', 'PSXP', 'PT', 'PTAM', 'PTC', 'PTCT', 'PTE', 'PTEN', 'PTF', 'PTGX', 'PTH', 'PTMN', 'PTNR', 'PTNYF', 'PTON', 'PTR', 'PTSC', 'PTSI', 'PTVCA', 'PTVCB', 'PTY', 'PUB', 'PUGOY', 'PUI', 'PUK', 'PUMP', 'PURE', 'PUYI', 'PVAC', 'PVBC', 'PVCT', 'PVDG', 'PVH', 'PVL', 'PVOTF', 'PW', 'PWB', 'PWDY', 'PWFL', 'PWOD', 'PWR', 'PWV', 'PXE', 'PXF', 'PXH', 'PXI', 'PXLW', 'PXQ', 'PXT', 'PXXLF', 'PY', 'PYN', 'PYS', 'PYT', 'PYTCY', 'PYZ', 'PZA', 'PZC', 'PZD', 'PZG', 'PZN', 'PZRIF', 'QABA', 'QADA', 'QADB', 'QAT', 'QBAK', 'QBCRF', 'QBIO', 'QCLN', 'QCRH', 'QDEL', 'QDF', 'QED', 'QEP', 'QES', 'QFIN', 'QGEN', 'QID', 'QIWI', 'QLC', 'QLD', 'QLS', 'QLTA', 'QMCI', 'QMCO', 'QNBC', 'QNST', 'QNTO', 'QPRC', 'QQEW', 'QQQE', 'QQQX', 'QRHC', 'QRTEA', 'QRTEB', 'QSR', 'QTEC', 'QTRX', 'QTS', 'QTUM', 'QTWO', 'QUAD', 'QUAL', 'QUASX', 'QUIK', 'QUMU', 'QUOT', 'QVAL', 'QVCD', 'QYLD', 'R', 'RA', 'RADA', 'RAFA', 'RAIL', 'RAMP', 'RAND', 'RAPT', 'RARE', 'RAVE', 'RAVN', 'RBA', 'RBB', 'RBBN', 'RBC', 'RBCAA', 'RBCN', 'RBKB', 'RBNC', 'RBNW', 'RBS', 'RBYCF', 'RBZ', 'RC', 'RCAR', 'RCB', 'RCEL', 'RCG', 'RCHA', 'RCI', 'RCKT', 'RCKY', 'RCM', 'RCMT', 'RCON', 'RCP', 'RCRT', 'RCS', 'RDCM', 'RDDTF', 'RDEIY', 'RDFN', 'RDGL', 'RDHL', 'RDI', 'RDIB', 'RDN', 'RDNT', 'RDSMY', 'RDUS', 'RDVT', 'RDVY', 'RDWR', 'RDY', 'RE', 'REAL', 'REDU', 'REE', 'REED', 'REET', 'REFR', 'REG', 'REGI', 'REI', 'REK', 'REKR', 'RELL', 'RELV', 'RELX', 'REM', 'REML', 'REMX', 'REMYY', 'RENN', 'REPH', 'REPL', 'REPYY', 'RES', 'RESI', 'RETA', 'RETL', 'RETO', 'REV', 'REVG', 'REW', 'REX', 'REXN', 'REXR', 'REZ', 'REZI', 'RFAP', 'RFEU', 'RFI', 'RFIL', 'RFL', 'RFP', 'RGA', 'RGBP', 'RGCO', 'RGEN', 'RGLD', 'RGR', 'RGRX', 'RGS', 'RGT', 'RGUS', 'RHHBY', 'RHI', 'RHNO', 'RHP', 'RIBT', 'RICK', 'RIF', 'RILY', 'RILYO', 'RILYP', 'RING', 'RIOCF', 'RISE', 'RIV', 'RIVE', 'RJF', 'RKFL', 'RKUNY', 'RL', 'RLGT', 'RLGY', 'RLH', 'RLI', 'RLJ', 'RLLRF', 'RLMD', 'RM', 'RMANF', 'RMAX', 'RMBI', 'RMBL', 'RMBS', 'RMCF', 'RMED', 'RMG', 'RMI', 'RMM', 'RMNI', 'RMR', 'RMT', 'RMTI', 'RNDB', 'RNEM', 'RNET', 'RNG', 'RNGR', 'RNLSY', 'RNP', 'RNR', 'RNST', 'RNVA', 'RNWK', 'ROAD', 'ROBO', 'ROBT', 'ROCK', 'RODM', 'ROG', 'ROIC', 'ROK', 'ROL', 'ROLL', 'ROM', 'ROP', 'ROS', 'ROSE', 'ROSEU', 'ROSGQ', 'ROYL', 'ROYT', 'RP', 'RPAI', 'RPAY', 'RPAYW', 'RPLA', 'RPM', 'RPT', 'RQHTF', 'RQI', 'RRBI', 'RRD', 'RRGB', 'RRR', 'RS', 'RSF', 'RSG', 'RSLS', 'RSP', 'RSPI', 'RST', 'RSTRF', 'RSX', 'RT', 'RTIX', 'RTLR', 'RTOKY', 'RTON', 'RTPPF', 'RTRX', 'RTW', 'RUBY', 'RUHN', 'RUSHA', 'RUSHB', 'RUSL', 'RUTH', 'RVI', 'RVLT', 'RVLV', 'RVRA', 'RVRF', 'RVSB', 'RVT', 'RVX', 'RWJ', 'RWM', 'RWO', 'RWR', 'RWT', 'RWVG', 'RWX', 'RXL', 'RXN', 'RY', 'RYAAY', 'RYAM', 'RYAOF', 'RYB', 'RYI', 'RYN', 'RYTM', 'RYU', 'RZA', 'RZB', 'RZLT', 'RZV', 'RZZN', 'SA', 'SAA', 'SAB', 'SABR', 'SACH', 'SAF', 'SAFE', 'SAFRY', 'SAFT', 'SAH', 'SAIA', 'SAIC', 'SAIL', 'SAL', 'SALM', 'SALRY', 'SALT', 'SAMA', 'SAMAU', 'SAMG', 'SAN', 'SAND', 'SANM', 'SANW', 'SAP', 'SAPGF', 'SAPMY', 'SAR', 'SASR', 'SATS', 'SAVA', 'SAXPY', 'SB', 'SBAC', 'SBB', 'SBBP', 'SBBX', 'SBCF', 'SBE', 'SBES', 'SBFG', 'SBGI', 'SBGSY', 'SBH', 'SBI', 'SBLK', 'SBNC', 'SBNY', 'SBOW', 'SBPH', 'SBR', 'SBRA', 'SBS', 'SBSAA', 'SBSI', 'SBT', 'SC', 'SCCO', 'SCD', 'SCG', 'SCHA', 'SCHB', 'SCHD', 'SCHE', 'SCHF', 'SCHH', 'SCHK', 'SCHL', 'SCHM', 'SCHN', 'SCHO', 'SCHX', 'SCHZ', 'SCI', 'SCIF', 'SCJ', 'SCKT', 'SCL', 'SCM', 'SCMWY', 'SCO', 'SCOO', 'SCOR', 'SCPE', 'SCPH', 'SCPL', 'SCR', 'SCS', 'SCSC', 'SCTY', 'SCU', 'SCVL', 'SCWX', 'SCX', 'SCZ', 'SD', 'SDC', 'SDD', 'SDG', 'SDI', 'SDIV', 'SDPI', 'SDS', 'SDVY', 'SDY', 'SEAC', 'SEAS', 'SEB', 'SECO', 'SECYF', 'SEED', 'SEEL', 'SEF', 'SEIC', 'SEII', 'SELF', 'SEM', 'SENEA', 'SENEB', 'SERV', 'SES', 'SF', 'SFBC', 'SFBS', 'SFE', 'SFEF', 'SFI', 'SFL', 'SFNC', 'SFST', 'SFTBF', 'SFTBY', 'SFUN', 'SG', 'SGA', 'SGAMY', 'SGBLY', 'SGBX', 'SGC', 'SGDM', 'SGEN', 'SGH', 'SGLB', 'SGLRF', 'SGMA', 'SGMD', 'SGOC', 'SGOL', 'SGQRF', 'SGRP', 'SGRY', 'SGSI', 'SGTPY', 'SGU', 'SH', 'SHBI', 'SHCAY', 'SHEN', 'SHG', 'SHI', 'SHLDQ', 'SHLL', 'SHLO', 'SHLRF', 'SHLX', 'SHM', 'SHMP', 'SHO', 'SHOO', 'SHRG', 'SHSP', 'SHV', 'SHVLF', 'SHW', 'SHY', 'SHYG', 'SI', 'SIAF', 'SIBN', 'SIC', 'SID', 'SIEB', 'SIEGY', 'SIF', 'SIFY', 'SIGA', 'SIGI', 'SIGM', 'SIGO', 'SII', 'SIJ', 'SIL', 'SILC', 'SILJ', 'SILK', 'SILV', 'SIM', 'SIML', 'SIMO', 'SIN', 'SING', 'SINT', 'SIPC', 'SIRC', 'SIRZF', 'SITC', 'SITE', 'SITO', 'SIVB', 'SIVR', 'SJ', 'SJI', 'SJIU', 'SJM', 'SJNK', 'SJR', 'SJT', 'SJW', 'SKAS', 'SKDI', 'SKF', 'SKFRY', 'SKM', 'SKOR', 'SKPO', 'SKT', 'SKY', 'SKYW', 'SKYY', 'SLAB', 'SLCT', 'SLF', 'SLG', 'SLGG', 'SLGL', 'SLGN', 'SLM', 'SLNG', 'SLNM', 'SLP', 'SLRC', 'SLRK', 'SLRX', 'SLT', 'SLTTF', 'SLVO', 'SLVP', 'SLVRF', 'SLX', 'SLY', 'SMBC', 'SMBK', 'SMCI', 'SMDD', 'SMDM', 'SMED', 'SMFG', 'SMG', 'SMGI', 'SMGZY', 'SMHB', 'SMHI', 'SMICY', 'SMID', 'SMIT', 
        # 'SMLP', 'SMLR', 'SMM', 'SMMC', 'SMMCF', 'SMMCU', 'SMMF', 'SMN', 'SMP', 'SMPL', 'SMTC', 'SMTS', 'SMTX', 'SNA', 'SNBP', 'SNBR', 'SNCA', 'SNDE', 'SNDL', 'SNDR', 'SNDX', 'SNFCA', 'SNLN', 'SNLP', 'SNN', 'SNNVF', 'SNP', 'SNR', 'SNRG', 'SNSR', 'SNV', 'SNWV', 'SNX', 'SNY', 'SOAN', 'SOCL', 'SOFO', 'SOHO', 'SOHOO', 'SOHU', 'SOI', 'SOIL', 'SOL', 'SOLCF', 'SOLN', 'SOLY', 'SOME', 'SON', 'SONA', 'SONG', 'SONM', 'SOR', 'SOT', 'SOTK', 'SOUL', 'SOYB', 'SP', 'SPAQ', 'SPAR', 'SPB', 'SPCB', 'SPCE', 'SPE', 'SPEM', 'SPFI', 'SPG', 'SPGI', 'SPGX', 'SPH', 'SPHD', 'SPHQ', 'SPIB', 'SPIN', 'SPKE', 'SPKEP', 'SPKKY', 'SPLB', 'SPLG', 'SPLP', 'SPLV', 'SPNE', 'SPNS', 'SPOK', 'SPOXF', 'SPPP', 'SPR', 'SPRO', 'SPRT', 'SPRWF', 'SPSB', 'SPSC', 'SPSM', 'SPT', 'SPTL', 'SPTM', 'SPTN', 'SPUU', 'SPWH', 'SPXC', 'SPXCY', 'SPXEW', 'SPXU', 'SPXX', 'SPYD', 'SPYG', 'SPYV', 'SPYX', 'SR', 'SRC', 'SRCE', 'SRCL', 'SRDX', 'SRE', 'SREA', 'SRET', 'SRF', 'SRG', 'SRI', 'SRKZF', 'SRL', 'SRLN', 'SRLP', 'SRMX', 'SRRA', 'SRRE', 'SRRK', 'SRRTF', 'SRS', 'SRT', 'SRTTY', 'SRTY', 'SRUS', 'SRV', 'SRVR', 'SSB', 'SSBI', 'SSC', 'SSD', 'SSEZF', 'SSG', 'SSI', 'SSKN', 'SSL', 'SSNLF', 'SSNT', 'SSO', 'SSP', 'SSPK', 'SSPKU', 'SSRM', 'SSSS', 'SSTK', 'SSY', 'ST', 'STAA', 'STAG', 'STAR', 'STBA', 'STC', 'STCN', 'STE', 'STFC', 'STG', 'STHC', 'STIM', 'STK', 'STKL', 'STKS', 'STKXF', 'STL', 'STLC', 'STLD', 'STLY', 'STML', 'STN', 'STND', 'STNG', 'STOK', 'STON', 'STOR', 'STPP', 'STRA', 'STRL', 'STRM', 'STRO', 'STRS', 'STRT', 'STS', 'STSA', 'STT', 'STTH', 'STWC', 'STWD', 'STXB', 'STXS', 'SUB', 'SUBCY', 'SUI', 'SUM', 'SUMR', 'SUN', 'SUNS', 'SUP', 'SUPV', 'SURF', 'SUSB', 'SUSC', 'SUSL', 'SUZ', 'SVA', 'SVBI', 'SVBL', 'SVC', 'SVM', 'SVRA', 'SVT', 'SVVC', 'SVXY', 'SWAV', 'SWI', 'SWKH', 'SWM', 'SWTX', 'SWX', 'SWZ', 'SWZNF', 'SXC', 'SXI', 'SXT', 'SY', 'SYATF', 'SYBT', 'SYBX', 'SYDDF', 'SYK', 'SYKE', 'SYNA', 'SYNC', 'SYNH', 'SYNL', 'SYPR', 'SYRS', 'SYSX', 'SYTE', 'SYX', 'SYY', 'SZC', 'SZDEF', 'TA', 'TAC', 'TACO', 'TACT', 'TAIT', 'TAK', 'TAKD', 'TAL', 'TALO', 'TAN', 'TANH', 'TANNI', 'TANNL', 'TANNZ', 'TAOP', 'TAPM', 'TAPR', 'TARO', 'TAST', 'TAT', 'TATT', 'TAUG', 'TAYD', 'TBB', 'TBBK', 'TBC', 'TBF', 'TBI', 'TBIO', 'TBK', 'TBL', 'TBLTW', 'TBNK', 'TBPH', 'TBPMF', 'TBRGU', 'TBT', 'TC', 'TCAP', 'TCBI', 'TCBK', 'TCCO', 'TCDA', 'TCEHY', 'TCF', 'TCFC', 'TCFF', 'TCI', 'TCMD', 'TCNNF', 'TCO', 'TCP', 'TCPC', 'TCRD', 'TCRR', 'TCRZ', 'TCS', 'TCX', 'TDA', 'TDAC', 'TDACU', 'TDC', 'TDE', 'TDF', 'TDI', 'TDIV', 'TDRRF', 'TDS', 'TDTF', 'TDW', 'TDY', 'TEAF', 'TEAR', 'TECD', 'TECH', 'TECL', 'TECO', 'TECR', 'TECS', 'TECTP', 'TEDU', 'TEF', 'TEI', 'TEL', 'TEN', 'TENB', 'TEO', 'TER', 'TERP', 'TESS', 'TEX', 'TEXC', 'TFFP', 'TFI', 'TFII', 'TFSL', 'TFX', 'TG', 'TGA', 'TGC', 'TGEN', 'TGH', 'TGI', 'TGIFF', 'TGLO', 'TGLS', 'TGNA', 'TGODF', 'TGP', 'TGRR', 'TGS', 'TH', 'THBR', 'THBRU', 'THCA', 'THCAU', 'THCB', 'THCBU', 'THD', 'THFF', 'THG', 'THM', 'THMO', 'THO', 'THQ', 'THR', 'THRM', 'THS', 'THST', 'THTX', 'THW', 'TIBRU', 'TIGO', 'TIGR', 'TIKK', 'TILE', 'TILT', 'TINO', 'TIP', 'TIPT', 'TISI', 'TITN', 'TK', 'TKAMY', 'TKAT', 'TKC', 'TKOI', 'TKR', 'TLC', 'TLF', 'TLH', 'TLI', 'TLK', 'TLOG', 'TLRS', 'TLSA', 'TLSS', 'TLSYY', 'TLYS', 'TM', 'TMDX', 'TMF', 'TMHC', 'TMICY', 'TMO', 'TMP', 'TMPS', 'TMQ', 'TMRC', 'TMSR', 'TMST', 'TMV', 'TMW', 'TNAV', 'TNB', 'TNC', 'TNCP', 'TNGL', 'TNK', 'TNP', 'TNSGF', 'TNT', 'TOCA', 'TOFB', 'TOKE', 'TOMDF', 'TOMZ', 'TOP', 'TORC', 'TOSBF', 'TOT', 'TOTA', 'TOTAU', 'TOTL', 'TOUR', 'TOWN', 'TPB', 'TPC', 'TPCO', 'TPCS', 'TPH', 'TPHS', 'TPIC', 'TPL', 'TPOR', 'TPRE', 'TPTX', 'TPVG', 'TPVY', 'TPZ', 'TR', 'TRC', 'TREC', 'TREVF', 'TREX', 'TRHC', 'TRI', 'TRIB', 'TRLFF', 'TRMB', 'TRMD', 'TRMK', 'TRMT', 'TRN', 'TRND', 'TRNE', 'TRNF', 'TRNO', 'TRNS', 'TRNX', 'TRON', 'TROV', 'TROW', 'TROX', 'TRP', 'TRRB', 'TRS', 'TRSSF', 'TRST', 'TRT', 'TRTC', 'TRTN', 'TRTX', 'TRU', 'TRUE', 'TRUL', 'TRUP', 'TRV', 'TRVI', 'TRWH', 'TRX', 'TS', 'TSBK', 'TSC', 'TSCAP', 'TSCBP', 'TSCO', 'TSE', 'TSEM', 'TSI', 'TSLX', 'TSM', 'TSPG', 'TSQ', 'TSRI', 'TSSI', 'TSU', 'TT', 'TTC', 'TTCM', 'TTEC', 'TTEK', 'TTGT', 'TTI', 'TTM', 'TTMI', 'TTNDY', 'TTP', 'TTT', 'TTTN', 'TTTSF', 'TU', 'TUES', 'TUFN', 'TUIFY', 'TUR', 'TURN', 'TURV', 'TUSK', 'TV', 'TVC', 'TVE', 'TW', 'TWER', 'TWI', 'TWIN', 'TWM', 'TWMC', 'TWN', 'TWNK', 'TWNKW', 'TWO', 'TWOH', 'TWST', 'TX', 'TXG', 'TXRH', 'TXSO', 'TXT', 'TY', 'TYD', 'TYG', 'TYL', 'TZAC', 'TZACU', 'UAE', 'UAMY', 'UAN', 'UBA', 'UBCP', 'UBER', 'UBFO', 'UBMCF', 'UBOH', 'UBOT', 'UBP', 'UBR', 'UBS', 'UBSFY', 'UBSI', 'UBT', 'UBX', 'UCBI', 'UCC', 'UCO', 'UCPA', 'UDFI', 'UDN', 'UDOW', 'UDR', 'UE', 'UEEC', 'UEIC', 'UEPS', 'UFAB', 'UFCS', 'UFI', 'UFO', 'UFPI', 'UFPT', 'UFS', 'UG', 'UGA', 'UGE', 'UGI', 'UGL', 'UGLD', 'UGP', 'UHAL', 'UHT', 'UI', 'UIHC', 'UL', 'ULBI', 'ULH', 'UMBF', 'UMC', 'UMDD', 'UMH', 'UMPQ', 'UMRX', 'UN', 'UNAM', 'UNB', 'UNF', 'UNL', 'UNM', 'UNMA', 'UNSS', 'UNT', 'UNTY', 'UNVC', 'UNVR', 'UONE', 'UONEK', 'UPLC', 'UPLD', 'URA', 'URE', 'URG', 'URGN', 'UROV', 'URTY', 'USA', 'USAC', 'USAK', 'USAP', 'USAS', 'USCI', 'USCR', 'USD', 'USDP', 'USEG', 'USEI', 'USFD', 'USIG', 'USIO', 'USL', 'USLM', 'USLV', 'USM', 'USMC', 'USMV', 'USNA', 'USOI', 'USPH', 'USRM', 'USRT', 'UST', 'USV', 'USWS', 'UTF', 'UTG', 'UTHR', 'UTI', 'UTL', 'UTMD', 'UTSI', 'UUUU', 'UVE', 'UVSP', 'UVV', 'UWHR', 'UWM', 'UYG', 'UYM', 'UZA', 'UZB', 'UZC', 'VAGIX', 'VAL', 'VALIX', 'VALLX', 'VALSX', 'VALU', 'VAM', 'VAPE', 'VAPO', 'VAR', 'VB', 'VBF', 'VBFC', 'VBIV', 'VBK', 'VBLT', 'VBND', 'VBR', 'VBTX', 'VC', 'VCF', 'VCIF', 'VCISY', 'VCIT', 'VCLT', 'VCNX', 'VCRA', 'VCSH', 'VCTR', 'VCV', 'VCYT', 'VDE', 'VEA', 'VEC', 'VECO', 'VEDL', 'VEGL', 'VEGN', 'VEND', 'VEON', 'VER', 'VERB', 'VERO', 'VERY', 'VET', 'VETS', 'VEU', 'VFC', 'VFF', 'VFINX', 'VFL', 'VFLQ', 'VFMF', 'VFMO', 'VFMV', 'VFQY', 'VFRM', 'VFVA', 'VGI', 'VGIT', 'VGK', 'VGLT', 'VGM', 'VGR', 'VGSH', 'VGT', 'VGZ', 'VHI', 'VHT', 'VIAV', 'VIBI', 'VICI', 'VICR', 'VIDI', 'VIE', 'VIG', 'VIGI', 'VIIX', 'VIOT', 'VIP', 'VIR', 'VIRC', 'VIS', 'VISL', 'VIST', 'VIV', 'VIVE', 'VIVK', 'VIVO', 'VJET', 'VKI', 'VKIN', 'VKQ', 'VLGEA', 'VLHYX', 'VLMGF', 'VLRS', 'VLT', 'VLY', 'VMBS', 'VMC', 'VMD', 'VMI', 'VMM', 'VMO', 'VNCE', 'VNE', 'VNET', 'VNLA', 'VNM', 'VNNHF', 'VNO', 'VNOM', 'VNQ', 'VNQI', 'VNRX', 'VNTR', 'VNUE', 'VO', 'VOC', 'VOD', 'VOE', 'VOLT', 'VONE', 'VONG', 'VONV', 'VOO', 'VOOG', 'VOPKY', 'VOT', 'VOX', 'VOXX', 'VOYA', 'VPG', 'VPL', 'VPRB', 'VPU', 'VRA', 'VRAY', 'VRCA', 'VREX', 'VREYF', 'VRIG', 'VRML', 'VRNA', 'VRNS', 'VRNT', 'VRRM', 'VRS', 'VRSK', 'VRSN', 'VRSSF', 'VRTS', 'VRTU', 'VRTV', 'VRUS', 'VSAT', 'VSDA', 'VSEC', 'VSH', 'VSLR', 'VSMV', 'VSS', 'VST', 'VSTO', 'VSTR', 'VSYM', 'VT', 'VTA', 'VTC', 'VTEB', 'VTGDF', 'VTHR', 'VTI', 'VTIP', 'VTN', 'VTNR', 'VTR', 'VTSI', 'VTV', 'VTWG', 'VTWO', 'VUG', 'VUSE', 'VV', 'VVI', 'VVPR', 'VVR', 'VVV', 'VWAGY', 'VWDRY', 'VWO', 'VWOB', 'VXF', 'VXRT', 'VXUS', 'VXZ', 'VYM', 'VYMI', 'VYST', 'WABC', 'WAFD', 'WAFU', 'WAL', 'WALA', 'WANT', 'WASH', 'WAT', 'WBAI', 'WBHC', 'WBK', 'WBS', 'WBT', 'WCAGY', 'WCC', 'WCLD', 'WCN', 'WCRS', 'WCVC', 'WD', 'WDDMF', 'WDFC', 'WDR', 'WEA', 'WEAT', 'WEC', 'WEI', 'WEICY', 'WELL', 'WERN', 'WES', 'WEX', 'WEYL', 'WEYS', 'WF', 'WFAFY', 'WFCL', 'WFICF', 'WH', 'WHD', 'WHEN', 'WHF', 'WHG', 'WHLM', 'WHLR', 'WHLRD', 'WHLRP', 'WHSI', 'WIA', 'WIFI', 'WILC', 'WIMHY', 'WIMI', 'WINA', 'WINMQ', 'WINR', 'WINS', 'WIP', 'WIRE', 'WISA', 'WISH', 'WIT', 'WIW', 'WIZD', 'WIZP', 'WK', 'WLBMF', 'WLDCF', 'WLDN', 'WLFC', 'WLKP', 'WLMS', 'WLTW', 'WLWHY', 'WMC', 'WMG', 'WMGI', 'WMICX', 'WMK', 'WMS', 'WNC', 'WNEB', 'WNS', 'WOOD', 'WOPEY', 'WOR', 'WORK', 'WORX', 'WOW', 'WPC', 'WPG', 'WPP', 'WPS', 'WRB', 'WRCDF', 'WRE', 'WRI', 'WRK', 'WRLD', 'WRLSU', 'WRN', 'WRTC', 'WSBC', 'WSBF', 'WSC', 'WSFS', 'WSG', 'WSO', 'WSPOF', 'WSR', 'WST', 'WSTG', 'WSTL', 'WTBA', 'WTFC', 'WTFCM', 'WTM', 'WTRE', 'WTREP', 'WTRH', 'WTRU', 'WTS', 'WTT', 'WTTR', 'WU', 'WUHN', 'WVE', 'WVFC', 'WVVI', 'WW', 'WWD', 'WWW', 'WY', 'WYND', 'XAIR', 'XAN', 'XAR', 'XBIOW', 'XBIT', 'XBUY', 'XCOM', 'XCUR', 'XDSL', 'XEL', 'XELA', 'XELB', 'XENE', 'XENT', 'XES', 'XFLT', 'XFOR', 'XGEIX', 'XGN', 'XHE', 'XHR', 'XIACY', 'XIN', 'XLB', 'XLC', 'XLG', 'XLI', 'XLRE', 'XME', 'XMMO', 'XNCR', 'XOMA', 'XP', 'XPEL', 'XPER', 'XPH', 'XPL', 'XPP', 'XRAY', 'XREG', 'XRF', 'XSD', 'XT', 'XTEG', 'XTLB', 'XTN', 'XYF', 'XYL', 'XYNO', 'Y', 'YAHOY', 'YANG', 'YAYO', 'YCBD', 'YCS', 'YDUQY', 'YECO', 'YGTYF', 'YGYIP', 'YI', 'YIN', 'YJ', 'YLCO', 'YLDE', 'YMAB', 'YNDX', 'YOGA', 'YOLO', 'YORW', 'YPF', 'YRD', 'YTRA', 'YUM', 'YUMC', 'YYY', 'ZAGG', 'ZB', 'ZBH', 'ZBISF', 'ZBRA', 'ZDGE', 'ZEAL', 'ZEUS', 'ZGNX', 'ZION', 'ZIV', 'ZIVO', 'ZIXI', 'ZLAB', 'ZM', 'ZMRK', 'ZMTP', 'ZN', 'ZNH', 'ZOM', 'ZROZ', 'ZSL', 'ZTCOY', 'ZTO', 'ZTR', 'ZTS', 'ZUMZ', 'ZVO', 'ZXAIY', 'ZYME', 'ZYXI']
        # # tweets = clientStockTweets.get_database('tweets_db').tweets.distinct('symbol')
        # print(tweets)
        # import numpy as np
        # main_list = np.setdiff1d(test,stocks).tolist()
        # date = datetime.datetime(2020, 6, 10, 12, 30)
        # dateString = date.strftime("%Y%m%d")
        # restURL = "?chartByDay=True&token=sk_c38d3babd3c144a886597ce6d014e543"
        # actual = []
        # for i in y:
        #     baseURL = "https://cloud.iexapis.com/stable/stock/" + i + "/chart/date/"
        #     URL = baseURL + dateString + restURL
        #     r = requests.get(url=URL)
        #     try:
        #         data = r.json()
        #     except:
        #         continue
        #     if (len(data) == 0):
        #         print('GAYYYYY')
        #         continue
        #     print(i)         
        #     actual.append(i)
        # print(actual)
        # import yfinance as yf
        # x = constants['db_client'].get_database('stocks_data_db').yfin_close_open.find()
        # for i in x:
        #     print(i)
        # tick = yf.Ticker('AAPL')
        # now = convertToEST(datetime.datetime.now())
        # date1 = datetime.datetime(now.year, 5, 20, 12, 30)
        # dateNow = datetime.datetime(now.year, now.month, now.day, 13, 30)
        # dates = findTradingDays(date1, dateNow)
        # count = 0
        # for date in dates:
        #     print(date)
        #     yOpen = tick.history(start=date, end=date)[['Close']].values[0][0].item()
        #     print(type(yOpen))
        #     count+=1
        
        #db = constants['db_client'].get_database('stocks_data_db').yfin_close_open
        # import pickle
        # #allUsers = constants['db_user_client'].get_database('user_data_db').user_accuracy_v2.find()
        # userList = readPickleObject("pickledObjects/test.pkl")
        # newList = []
        # for val in userList:
        #     if val > 70:
        #         newList.append(math.sqrt(math.sqrt(val)))
        # # newList = list(map(lambda x:math.log10(x),newList))
        # plt.hist(newList, 10)
        # plt.show()

        # testing yfinance
        # import yfinance as yf
        # gss = ['BDX']
        # openDiff = closeDiff = 0
        # maxo = maxc = 0
        # for i in gss:
        #     print(i)
        #     tick = yf.Ticker(i)
        #     yesterday = convertToEST(datetime.datetime.now())-datetime.timedelta(days=4)
        #     print(yesterday)
        #     yOpen = tick.history(start=yesterday, end=yesterday)[['Open']].values[0][0].item()
        #     yClose = tick.history(start=yesterday, end=yesterday)[['Close']].values[0][0].item()   
        #     (ogClose, ogOpen, test, bleh) = getUpdatedCloseOpen(i, yesterday)
        #     # print('ours')
        #     print(test, ogClose)
        #     # print('yahoo')
        #     print(yOpen, yClose)
        #     print('diff')
        #     print(test-yOpen, ogClose-yClose)
        #     openDiff += abs(test-yOpen)
        #     closeDiff += abs(ogClose-yClose)
        #     if abs(test-yOpen) > maxo:
        #         maxo = abs(test-yOpen)
        #     if abs(ogClose-yClose) > maxc:
        #         maxc = abs(ogClose-yClose)

        # print('avg o diff: ' + str(openDiff/len(gss)))
        # print('avg c diff: ' + str(closeDiff/len(gss)))
        # print('maxo : ', maxo)
        # print('maxc : ', maxc)
        # print(ogClose)
        # print(ogOpen)
        
        # dateStart = datetime.datetime(2020, 6, 10, 12, 00)
        # dateEnd = datetime.datetime(2020, 6, 10, 16, 30)
        # stocks = getTopStocks(100)
        # stocks1 = getSortedStocks()[101:1001]
        # #test = ['MDR', 'I', 'HSGX', 'RTTR', 'UWT', 'JCP', 'SES', 'DWT', 'SPEX', 'RBZ', 'YUMA', 'BPMX', 'SNNA', 'PTIE', 'FOMX', 'TROV', 'HIIQ', 'S', 'XGTI', 'MDCO', 'NLNK', 'SSI', 'VLRX', 'ATIS', 'INNT', 'DCAR', 'CUR', 'AKS', 'FTNW', 'KEG', 'CNAT', 'MLNT', 'GNMX', 'AKRX', 'CLD', 'ECA', 'DCIX', 'PIR', 'DF', 'AXON', 'CIFS', 'XON', 'SBOT', 'KOOL', 'HAIR', 'ARQL', 'IPCI', 'ACHN', 'ABIL', 'RTN', 'AMR', 'FTR', 'DERM', 'CBS', 'OILU', 'JMU', 'CELG', 'DRYS', 'AGN', 'SBGL', 'UPL', 'VTL', 'BURG', 'DO', 'SN', 'PVTL', 'UTX', 'HEB', 'WFT', 'CY', 'SYMC', 'PTX', 'AKAO', 'AVP', 'GEMP', 'CBK', 'HABT', 'RARX', 'ORPN', 'IGLD', 'ROX', 'LEVB', 'CTRP', 'CARB', 'AAC', 'HK', 'CRZO', 'MNGA', 'PEGI', 'OHGI', 'ZAYO', 'GLOW', 'MLNX', 'COT', 'SORL', 'BBT', 'FGP', 'SGYP', 'STI', 'FCSC', 'NIHD', 'ONCE', 'ANFI', 'VSI', 'INSY', 'CVRS', 'GG', 'WIN', 'BRS', 'NVLN', 'EMES', 'CBLK', 'ARRY', 'ESV', 'HRS', 'APHB', 'RHT', 'CLDC', 'EPE', 'APC', 'ACET', 'DATA', 'SDLP', 'GHDX', 'OHRP', 'EDGE', 'DFRG', 'VSM', 'RGSE', 'ASNS', 'BSTI', 'CADC', 'MXWL', 'PETX', 'IMDZ', 'ATTU', 'RLM', 'OMED']
        # for i in stocks:
        #     print(i)
        #     tweets = clientStockTweets.get_database('tweets_db').tweets.find({"$and": [{'symbol': i},
        #                                                                     {'time': {'$gte': dateStart,
        #                                                                     '$lt': dateEnd}}]})
        #     print(tweets.count())
        #for i in tweets:
            #print(i)

        # check last parsetime
        # stocks = getTopStocks(100)
        # stocks1 = getSortedStocks()[101:551]

        # db = constants['stocktweets_client'].get_database('stocks_data_db')
        # lastParsed = db.last_parsed
        # for i in stocks:
        #     lastTime = lastParsed.find({'_id': i})
        #     print(str(i) + ':' + str(lastTime[0]))

        # db = clientStockTweets.get_database('stocks_data_db')
        # errors = db.stock_tweets_errors.find()
        # for i in errors:
        #     print(i)

        # now = convertToEST(datetime.datetime.now())
        # date = datetime.datetime(now.year, now.month, now.day)
        # stocks = getAllStocks()
        # print(len(stocks))
        # for i in range(len(stocks)):
        #     if (stocks[i] == "SESN"):
        #         print(i)
        # analyzeStocks(date, ['SNAP'])


        # stocks = getAllStocks()
        # print(dates)
        # findAllTweets(stocks, dates, True)
        # testing(35)
        # for i in range(5, 20):
        #     testing(i)
        # calcReturns(35)
        # stocks.remove('AMZN')
        # stocks.remove('SLS')
        # stocks.remove('CEI')

        # tweets = findAllTweets(stocks, dates)
        # updateBasicStockInfo(dates, stocks, tweets)
        # return
        # basicPrediction(dates, stocks, True)

        # time = datetime.datetime(2019, 12, 12, 16, 3)
        # print(findCloseOpen('AAPL', time))

        # updateAllCloseOpen(['TTNP'], dates)
        # for d in dates:
        #     print(d, closeToOpen('TVIX', d))
        # date = datetime.datetime(2019, 12, 16, 16, 10) - datetime.datetime(2019, 12, 16)
        # print(16 * 60 * 60)
        # print(date.total_seconds())
        # for i in range(11, 25):
        #     for j in range(0, 23):
        #         date = datetime.datetime(2019, 12, i, j, 10)
        #         # findCloseOpen('AAPL', date)
        #         print(date, findCloseOpen('AAPL', date))
        #         # print(date, round(findWeight(date, 'x'), 1))

        # calculateAllUserInfo()
        # getStatsPerUser('DaoofDow')
        # print(getAllUserInfo('sjs7'))

        # transferNonLabeled(stocks)

        # findBadMessages('ArmedInfidel')
        # findTopUsers()
        # removeMessagesWithStock('AAPL')
        # findOutliers('GNCA')

        # findTopUsers()

        # setupUserInfos(updateObject=True)
        # findAllUsers()
        
        # findErrorUsers()

        # updateUserNotAnalyzed()
        # (setup, testing) = generateFeatures(dates, stocks, True)
        # basicPrediction(dates, stocks, False, False)
        # neuralnet()
        # updateBasicStockInfo(dates, stocks, findAllTweets(stocks, dates))


if __name__ == "__main__":
    main()
