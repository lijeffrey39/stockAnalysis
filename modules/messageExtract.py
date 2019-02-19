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
bullSentAttr = 'st_1WHAM8- st_3bEptPi'
bearSentAttr = 'st_2KbIj7l st_3bEptPi'
messageTextAttr = 'st_2giLhWN'
likeCountAttr = 'st_1tZ744c'
commmentCountAttr = 'st_1YAqrKR'
messagesCountAttr = 'st__tZJhLh'


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------



def isValidMessage(dateTime, dateNow, isBull, user, symbol, daysInFuture):
	if (dateTime == None):
		return False

	dateCheck = datetime.datetime(dateTime.year, dateTime.month, dateTime.day)
	dateNow = datetime.datetime(dateNow.year, dateNow.month, dateNow.day)

	delta = datetime.timedelta(daysInFuture)
	newTime = dateTime + delta
	# If the next day at 9:30 am is < than the current time, then there is a stock price
	newTime = datetime.datetime(newTime.year, newTime.month, newTime.day, 9, 30)
	newTimeDay = newTime.weekday()
	inside = inTradingHours(dateTime, symbol)

	if (user == None or 
		# isBull == None or 
		symbol == None or
		inside == False or
		(daysInFuture == 0 and dateCheck != dateNow) or
		(daysInFuture > 0 and newTime > dateNow) or
		(dateCheck > dateNow)): 
		return False
	return True



# Find time of a message
def findDateTime(message):
	if (message == None):
		return None
	else:
		try:
			dateTime = parse(message)
		except:
			return None
		currDay = datetime.datetime.now()
		test = currDay + datetime.timedelta(1)
		if (dateTime > test):
			return datetime.datetime(2018, dateTime.month, dateTime.day, dateTime.hour, dateTime.minute)
		return dateTime


def findSymbol(message):
	textM = message.find('div', attrs={'class': messageTextAttr})
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
	if (foundTicker == False or len(tickers) > 1):
		return None
	else:
		return tickers[0]


# Find username of a message
def findUser(message):
	u = message.find('a', attrs={'class': usernameAttr})

	if (u == None):
		return None
	else:
		user = u['href'][1:]
		return user


def likeCount(message):
	count = message.find('span', attrs={'class': likeCountAttr})
	if (count == None):
		return 0
	else:
		return int(count.text)


def commentCount(message):
	count = message.find('span', attrs={'class': commmentCountAttr})
	if (count == None):
		return 0
	else:
		return int(count.text)


# True if bull
def isBullMessage(message):
	bull = message.find('span', attrs={'class': bullSentAttr})
	bear = message.find('span', attrs={'class': bearSentAttr})

	if (bull == None and bear == None):
		return None

	if (bull):
		return True 
	else: 
		return False