import os
import datetime
from . import scroll

from .fileIO import *
from .stockPriceAPI import *
from .messageExtract import *

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException


# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


# Invalid symbols so they aren't check again
invalidSymbols = []
messageStreamAttr = 'st_1m1w96g'
timeAttr = 'st_2q3fdlM'
messageTextAttr = 'st_29E11sZ'
ideaAttr = 'st__tZJhLh'


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------



# Return soup object page of that user 
def findPageUser(username, days, driver, savePage):
	# if html is stored
	path = 'usersPages/' + username + '.html'
	if (os.path.isfile(path)):
		print("File Exists")
		soup = BeautifulSoup(open(path), 'html.parser')
		return soup

	url = "https://stocktwits.com/" + username
	driver.get(url)

	
	try:
	  	foundEnough = scroll.scrollFor(username, days, driver, False)
	except TimeoutException as ex:
	  	print(ex.Message)
	  	foundEnough = scroll.scrollFor(username, days, driver, False)

	if (foundEnough == False):
		return None

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')

	if (savePage):
		with open(path, "w") as file:
		    file.write(str(soup))

	return soup


# First write to userCalculated, then write to newUserInfo.csv
def saveUserToCSV(username, result, otherInfo):
	res = []
	read = list(filter(lambda x: x[5] != -1, result))
	symbols = list(set(map(lambda x: x[0], read)))
	total = float(len(read))

	for s in symbols:
		filterSymbol = list(filter(lambda x: x[0] == s, read))
		totalCorrect = list(map(lambda x: abs(float(x[7])), list(filter(lambda x: x[5] == 1, filterSymbol))))
		totalIncorrect = list(map(lambda x: abs(float(x[7])), list(filter(lambda x: x[5] == 0, filterSymbol))))
		summedCorrect = reduce(lambda a, b: a + b, totalCorrect) if len(totalCorrect) > 0 else 0
		summedIncorrect = reduce(lambda a, b: a + b, totalIncorrect) if len(totalIncorrect) > 0 else 0
		res.append([s, round(100 * len(filterSymbol) / total, 2), len(totalCorrect), 
			len(totalIncorrect), round(summedCorrect - summedIncorrect, 2)])

	res.sort(key = lambda x: x[4], reverse = True)
	writeSingleList('newUserCalculated/' + username + '_info.csv', res)

	resNewUserInfo = []
	if (len(res) == 0):
		resNewUserInfo = [username, 0, 0, 0.0]
	else:
		totalReturn = round(reduce(lambda a, b: a + b, list(map(lambda x: x[4], res))), 4)
		correct = round(reduce(lambda a, b: a + b, list(map(lambda x: x[2], res))), 4)
		incorrect = round(reduce(lambda a, b: a + b, list(map(lambda x: x[3], res))), 4)
		resNewUserInfo = [username, correct, incorrect, totalReturn]

	resNewUserInfo.extend(otherInfo)
	currNewUserInfo = readMultiList('newUserInfo.csv')
	currNewUserInfo.append(resNewUserInfo)
	currNewUserInfo.sort(key = lambda x: float(x[3]), reverse = True)
	writeSingleList('newUserInfo.csv', currNewUserInfo)



def findUserInfo(username, soup):
	ideas = soup.find_all('h2', attrs={'class': ideaAttr})
	res = []
	for i in ideas:
		res.append(i.text)
	return res


def analyzeUser(username, soup, daysInFuture):

	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	dateNow = datetime.datetime.now()
	res = []

	for m in messages:
		t = m.find('div', {'class': timeAttr})
		t = t.find_all('a') # length of 2, first is user, second is date
		if (t == None):
			continue

		allT = m.find('div', {'class': messageTextAttr})
		allText = allT.find_all('div')
		dateTime = findDateTime(t[1].text)
		messageTextView = allText[1] 
		user = findUser(t[0])
		textFound = messageTextView.find('div').text
		cleanText = ' '.join(removeSpecialCharacters(textFound).split())
		isBull = isBullMessage(m)

		symbol = findSymbol(messageTextView)
		likeCnt = likeCount(m)
		commentCnt = commentCount(m)


		if (isValidMessage(dateTime, dateNow, isBull, user, symbol, daysInFuture) == False):
			continue

		(historical, dateTimeAdjusted) = findHistoricalData(dateTime, symbol, False)
		priceAtPost = priceAtTime(dateTime, historical) # Price at the time of posting
		# Price at 3:59 PM
		prices = priceAtTime(datetime.datetime(dateTime.year, dateTime.month, dateTime.day, 15, 59), historical)


		# Find price after # days
		delta = datetime.timedelta(daysInFuture)
		newTime = dateTime + delta
		newTime = datetime.datetime(newTime.year, newTime.month, newTime.day, 9, 30)

		(historical, dateTimeAdjusted) = findHistoricalData(newTime, symbol, True)
		newPrices = priceAtTime(newTime, historical) # Find price at 9:30 AM
		# Find price at 10:00 AM
		price10 = priceAtTime(datetime.datetime(newTime.year, newTime.month, newTime.day, 10, 0), historical)
		# Find price at 10:30 AM
		price1030 = priceAtTime(datetime.datetime(newTime.year, newTime.month, newTime.day, 10, 30), historical)

		correct = 0
		change = round(newPrices - prices, 4)
		percent = 0
		try:
			percent = round((change * 100.0 / prices), 5)
		except:
			pass

		if ((change > 0 and isBull == True) or (change <= 0 and isBull == False)):
			correct = 1

		if (isBull == None):
			correct = -1

		# If result of any price is a 0
		if (prices == 0 or priceAtPost == 0 or newPrices == 0 or price10 == 0 or price1030 == 0 or newPrices == -1):
			continue

		res.append([symbol, dateTime.strftime("%Y-%m-%d %H:%M:%S"), prices, 
			newPrices, isBull, correct, change, percent, likeCnt, commentCnt, priceAtPost, price10, price1030, cleanText])

	return res

