import os
import datetime
from .stockPriceAPI import *
from .fileIO import *


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------



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


def analyzedSymbolAlready(name, path):
	# Check to see if username already exists
	users = readMultiList(path)
	filtered = filter(lambda x: len(x) >= 2, users)
	mappedUsers = map(lambda x: x[0], filtered)
	return (name in mappedUsers)


def analyzedUserAlready(name):
	# Check to see if username already exists
	path = 'userinfo/' + name + '.csv'
	return os.path.exists(path)


def chunks(seq, size):
    return (seq[i::size] for i in range(size))