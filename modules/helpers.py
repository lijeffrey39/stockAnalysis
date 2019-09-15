import datetime
import operator
import os
from datetime import *

from dateutil.tz import *

import pytz

from .fileIO import *
from .hyperparameters import constants
from .prediction import *
from .stockPriceAPI import *


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


# Close and quit driver
def endDriver(driver):
    driver.close()
    driver.quit()


def convertToEST(dateTime):
    # import pdb; pdb.set_trace()
    if (constants['current_timezone'] != 'EDT' and
        constants['current_timezone'] != 'EST' and
        constants['current_timezone'] != 'Eastern Daylight Time'):
        # localize to current time zone
        currTimeZone = pytz.timezone(constants['current_timezone'])
        dateTime = currTimeZone.localize(dateTime)
        dateTime = dateTime.astimezone(constants['eastern_timezone'])
        dateTime = dateTime.replace(tzinfo=None)
        return dateTime
    return dateTime


def allUsers():
    path = "userinfo/"
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    names = list(map(lambda x: x[:len(x) - 4], files))
    names = list(filter(lambda x: x != '.DS_S', names))
    return names


def inTradingHours(dateTime, symbol):
    day = dateTime.weekday()
    nineAM = datetime.datetime(dateTime.year, dateTime.month, dateTime.day, 9, 30)
    fourPM = datetime.datetime(dateTime.year, dateTime.month, dateTime.day, 16, 0)

    if (dateTime < nineAM or dateTime >= fourPM or day == "0" or day == "6"):
        return False

    historical = historicalFromDict(symbol, dateTime)

    if (len(historical) == 0):
        return False

    strDate = dateTime.strftime("%X")[:5]
    found = False

    for ts in historical:
        if (ts.get('minute') == strDate):
            found = True

    return found


def isTradingDay(date):
    path = date.strftime("stocksResults/%m-%d-%y.csv")
    return (os.path.isfile(path))


# Return list of valid trading days from date on
def findTradingDays(date, upToDate):
    delta = datetime.timedelta(1)
    dates = []

    while (date < upToDate - delta):
        # See if it's a valid trading day
        if (isTradingDay(date)):
            dates.append(date)
        date += delta

    return dates


def analyzedSymbolAlready(name, path):
    # Check to see if username already exists
    newPath = path + name + '.csv'
    return os.path.exists(newPath)


def analyzedUserAlready(name):
    # Check to see if username already exists
    # path = 'userinfo/' + name + '.csv'
    path = 'newUserInfo/' + name + '.csv'
    return os.path.exists(path)


def checkInvalid():
    users = allUsers()
    count = 0

    for name in users:
        l = readMultiList('userInfo/' + name + '.csv')
        res = []

        for r in l:
            four = r[2]
            nine = r[3]
            priceAtPost = r[10]
            ten = r[11]
            ten30 = r[12]
            if (four != '-1' and nine != '-1' and ten != '-1' and ten30 != '-1' and priceAtPost != '-1'):
                continue

            count += 1
    # print(count)


# Returns size number of equal size lists
def chunks(seq, size):
    return (seq[i::size] for i in range(size))


def argMax():
    res = readMultiList('argMax.csv')
    res.sort(key = lambda x: float(x[1]), reverse = True)

    result = []

    for i in range(20):
        temp = res[i]
        numStocks = int(temp[2][2])
        w1 = round(float(temp[3]), 2)
        w2 = round(float(temp[4]), 2)
        w3 = round(float(temp[5]), 2)
        w4 = round(float(temp[6][:4]), 2)
        temp = [round(float(temp[1]), 2), numStocks, w1, w2, w3, w4]
        print(temp)
        result.append(temp)

    for i in range(2, 6):
        w1Total = list(map(lambda x: x[i],result))
        avg = sum(w1Total) / len(w1Total)
        print(avg)


# Find the change in the number of new users each day
def findNewUserChange():
    path = "newUsers/"
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    files = sorted(list(filter(lambda x: x != '.DS_Store', files)))

    users = []
    prevLen = 0
    for file in files:
        print(file)
        res = readSingleList(path + file)
        res = list(filter(lambda x: len(x) > 0, res))

        users.extend(res)
        users = list(set(users))

        print(len(users) - prevLen)
        prevLen = len(users)


    users = list(set(users))
    users.sort()
    users = list(map(lambda x: [x], users))
    writeSingleList('allNewUsers.csv', users)
    print(len(users))



def testWeights(dates):

    statsUsers()
    writeTempListStocks()

    count = 0
    result = []

    for i in range(8, 9):
        numStocks = i
        for j in range(3, 8):
            w1 = j * 0.1
            for k in range(1, 7):
                w2 = k * 0.1
                for l in range(2, 5):
                    w3 = l * 0.3
                    for m in range(5, 11):
                        w4 = m * 0.3

                        count += 1
                        weights = [numStocks, w1, w2, w3, w4]
                        # res = topStocks(date, 2000, weights)
                        # foundReturn = calcReturnBasedResults(date, res)
                        totalReturn = 0

                        for date in dates:
                            res = topStocks(date, 2000, weights)
                            foundReturn = calcReturnBasedResults(date, res)
                            totalReturn += foundReturn

                        print(count, totalReturn, weights)
                        result.append([count, totalReturn, weights])
                        writeSingleList('argMax.csv', result)


# find frequency of user data per stock
def stockFrequency():
    path = "stocksResults/"
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) == False]
    files = sorted(list(filter(lambda x: x != '.DS_Store', files)))

    stocksDict = {}
    maxFound = {}

    for f in files:
        newPath = path + f

        newFiles = [f for f in os.listdir(newPath) if os.path.isfile(os.path.join(newPath, f))]
        newFiles = sorted(list(filter(lambda x: x != '.DS_Store', newFiles)))

        for stockCSV in newFiles:
            stockPath = newPath + '/' + stockCSV

            stockName = stockCSV[:-4]
            stockL = readMultiList(stockPath)
            length = len(stockL)

            if (stockName not in stocksDict):
                stocksDict[stockName] = length
            else:
                stocksDict[stockName] += length

            if (stockName not in maxFound):
                maxFound[stockName] = length
            else:
                maxFound[stockName] = max(length, maxFound[stockName])

    sorted_x = sorted(stocksDict.items(), key=operator.itemgetter(1))
    sorted_y = sorted(maxFound.items(), key=operator.itemgetter(1))

    count = 0
    count1 = 0
    stockList = []
    for x in sorted_x:
        if (x[1] < 30):
            count += 1
        else:
            if (maxFound[x[0]] > 5):
                stockList.append(x[0])
                count1 += 1

    stockList.sort()
    print(len(stockList))
    stockList = list(map(lambda x: [x, stocksDict[x], maxFound[x]], stockList))
    writeSingleList('stockFrequency.csv', stockList)


# Used for allocating stocks based on historical times
def allocateStocks(processes, stockList, filtered):
    ACCOUNT_LOAD = 500

    nums = [0] * processes
    stockList.sort(key = lambda x: int(x[1]), reverse = True)
    stockList = list(map(lambda x: [x[0], int(x[1]) + ACCOUNT_LOAD], stockList))
    stockList = list(filter(lambda x: x[0] in filtered, stockList))

    dict = {}
    for x in stockList:
        dict[x[0]] = x[1]

    sumL = 0
    for i in range(len(stockList)):
        sumL += int(stockList[i][1])

    average = int(sumL / processes)
    stocks = {}
    for i in range(processes):
        stocks[i] = []

    currI = 0
    for i in range(len(stockList)):
        if (nums[currI] < average):
            nums[currI] += int(stockList[i][1])
            currI += 1
            currI = currI % processes
            stocks[currI].append(stockList[i][0])
        else:
            currI += 1
            for j in range(processes):
                if (nums[currI] < average):
                    nums[currI] += int(stockList[i][1])
                    currI += 1
                    currI = currI % processes
                    stocks[currI].append(stockList[i][0])
                    break
                else:
                    currI += 1
                    currI = currI % processes

    # Quick check
    res = []
    for key in stocks:
        arr = stocks[key]
        print(len(arr))
        newArr = []
        for i in range(len(arr)):
            s = arr[i]
            newArr.append([s, dict[s]])

        newArr.sort(key = lambda x: x[1], reverse = True)
        # print(key, newArr[:10])

        res.append(sorted(arr))

    return res
