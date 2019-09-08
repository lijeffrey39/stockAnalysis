import datetime

from dateutil.parser import parse

from bs4 import BeautifulSoup

from .helpers import *

# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


# SET NAME ATTRIBUTES
priceAttr = 'st_2BF7LWC'
messageStreamAttr = 'st_1m1w96g'
timeAttr = 'st_HsSv26f'
usernameAttr = 'st_x9n-9YN'
messageTextAttr = 'st_2giLhWN'
likeCountAttr = 'st_1tZ744c'
commmentCountAttr = 'st_1cZCCSt'
messagesCountAttr = 'st__tZJhLh'
bullBearAttr = 'st_11GoBZI'


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


def isValidMessage(dateTime, dateNow, isBull, user, symbol, daysInFuture):
    if (dateTime is None):
        return False

    dateCheck = datetime.datetime(dateTime.year, dateTime.month, dateTime.day)
    dateNow = datetime.datetime(dateNow.year, dateNow.month, dateNow.day)

    delta = datetime.timedelta(daysInFuture)
    newTime = dateTime + delta
    # If the next day at 9:30 am is < than the current time, then there is a stock price
    newTime = datetime.datetime(newTime.year, newTime.month, newTime.day, 9, 30)
    newTimeDay = newTime.weekday()
    inside = inTradingHours(dateTime, symbol)

    if (user is None or
        # isBull == None or
        symbol is None or
        inside is False or
        (daysInFuture == 0 and dateCheck != dateNow) or
        (daysInFuture > 0 and newTime > dateNow) or
        (dateCheck > dateNow)):
            return False
    return True


# Find time of a message
# If the time is greater than the current time, it is from last year
def findDateTime(message):
    if (message is None):
        return None
    else:
        dateTime = parse(message)
        currDay = datetime.datetime.now()
        nextDay = currDay + datetime.timedelta(1)
        if (dateTime > nextDay):
            return datetime.datetime(2018, dateTime.month,
                                     dateTime.day, dateTime.hour, 
                                     dateTime.minute)
        return dateTime


def findSymbol(message):
    textM = message.find('div')
    spans = textM.find_all('span')

    tickers = []
    foundTicker = False
    for s in spans:
        foundA = s.find('a')
        ticker = foundA.text

        if ('@' in ticker or '#' in ticker or '.X' in ticker):
            continue

        tickers.append(ticker[1:])

        if ("$" in ticker):
            foundTicker = True

    # Never found a ticker or more than 1 ticker
    if (foundTicker is False or len(tickers) > 1):
        return []
    else:
        return tickers


# Find username of a message
def findUser(message):
    if (message is None):
        return None
    else:
        user = message['href'][1:]
        return user


def likeCount(message):
    count = message.find('span', attrs={'class': likeCountAttr})
    if (count is None):
        return 0
    else:
        return int(count.text)


def commentCount(message):
    count = message.find('span', attrs={'class': commmentCountAttr})
    if (count is None):
        return 0
    else:
        return int(count.text)


# True if bull
def isBullMessage(message):
    bullBearText = message.find('span', attrs={'class': bullBearAttr})
    if bullBearText is None:
        return None
    bullBearSpan = bullBearText.find_all('span')

    if (bullBearSpan[0].text == "Bearish"):
        return False
    else:
        return True
