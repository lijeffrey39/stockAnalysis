import os
import datetime
from .fileIO import *
from .prediction import *
from .stockPriceAPI import *


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


def isTradingDay(date):
	historical = get_historical_intraday('TVIX', date)
	return len(historical) > 0


# Return list of valid trading days from date on
def findTradingDays(date):
	currDate = datetime.datetime.now()
	delta = datetime.timedelta(1)
	dates = []

	while (date < currDate - delta):
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
	print(count4)


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

