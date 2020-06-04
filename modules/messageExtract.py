import datetime

from dateutil.parser import parse

from .helpers import convertToEST
from .hyperparameters import constants

# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


# SET NAME ATTRIBUTES
priceAttr = 'st_2BF7LWC'
messageStreamAttr = 'st_1m1w96g'
timeAttr = 'st_HsSv26f'
usernameAttr = 'st_x9n-9YN'
messageTextAttr = 'st_2giLhWN'
commmentCountAttr = 'st_1cZCCSt'
messagesCountAttr = 'st__tZJhLh'
bullBearAttr = 'st_11GoBZI'


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


# Finds symbol from a string (Only returns if exactly 1 symbol fonud)
def findSymbol(text, allSymbols):
    textArray = text.split(' ')
    foundSymbols = []
    for w in textArray:
        if ('$' in w):
            # if number in string, continue
            if (any(char.isdigit() for char in w)):
                continue
            foundSymbols.append(w)

    foundStocks = []
    for s in foundSymbols:
        ind = s.find('$')
        if (len(s) == 1):
            continue
        found = ""
        for i in range(ind + 1, len(s) + 1):
            currSymbolCheck = s[ind + 1:i]
            if (currSymbolCheck in allSymbols):
                found = currSymbolCheck

        if (found != ""):
            foundStocks.append(found)
    return foundStocks


# Returns datetime object from message
def findDateFromMessage(message):
    text = message.text
    t = text.split('\n')
    dateString = ''
    if (t[1] == "Bearish" or t[1] == "Bullish"):
        dateString = t[2]
    else:
        dateString = t[1]
    # if (t[0] == "Bearish" or t[0] == "Bullish"):
    #     if (t[2] == 'Plus' or t[2] == 'Lifetime'):
    #         dateString = t[3]
    #     else:
    #         dateString = t[2]
    # else:
    #     if (t[1] == 'Plus' or t[1] == 'Lifetime'):
    #         dateString = t[2]
    #     else:
    #         dateString = t[1]
    return findDateTime(dateString)


# Find time of a message
# If the time is greater than the current time, it is from last year
def findDateTime(dateString):
    if (dateString == 'now'):
        currTime = convertToEST(datetime.datetime.now())
        currTime = datetime.datetime(currTime.year, currTime.month,
                                     currTime.day, currTime.hour,
                                     currTime.minute)
        return (currTime, '')
    if (dateString[-1] == 'm'):
        time = int(dateString[:-1])
        currTime = convertToEST(datetime.datetime.now())
        currTime = datetime.datetime(currTime.year, currTime.month,
                                     currTime.day, currTime.hour,
                                     currTime.minute)
        newTime = currTime - datetime.timedelta(minutes=time)
        return (newTime, '')

    try:
        dateTime = parse(dateString)
        dateTime = convertToEST(dateTime)
    except Exception as e:
        return (None, str(e))
    currDay = convertToEST(datetime.datetime.now())
    nextDay = currDay + datetime.timedelta(1)
    if (dateTime > nextDay):
        return (datetime.datetime(2018, dateTime.month,
                                  dateTime.day, dateTime.hour,
                                  dateTime.minute), '')
    return (dateTime, '')


# Find username of a message
def findUser(message):
    if (message is None):
        return None
    else:
        user = message['href'][1:]
        return user


def likeCount(message):
    count = message.find('span', attrs={'class': constants['likeCountAttr']})
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


# Converts string to int
def parseKOrInt(s):
    if ('k' in s):
        num = float(s[:-1])
        return int(num * 1000)
    elif ('m' in s):
        num = float(s[:-1])
        return int(num * 1000000)
    else:
        return int(s)
