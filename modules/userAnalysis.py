import os
import datetime
from . import scroll
from .messageExtract import *
from .stockPriceAPI import *
from .fileIO import *
from bs4 import BeautifulSoup


# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


# Invalid symbols so they aren't check again
invalidSymbols = []
messageStreamAttr = 'st_1m1w96g'
timeAttr = 'st_HsSv26f'


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------



# Return soup object page of that user 
def findPageUser(username, days, driver, savePage):
	# if html is stored
	path = 'usersPages/' + username + '.html'
	if (os.path.isfile(path)):
		print("File Exists")
		# html = open(path, "r")
		soup = BeautifulSoup(open(path), 'html.parser')
		return soup

	url = "https://stocktwits.com/" + username
	driver.get(url)
	foundEnough = scroll.scrollFor(username, days, driver, False)

	if (foundEnough == False):
		return None

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')

	if (savePage):
		with open(path, "w") as file:
		    file.write(str(soup))

	return soup


def analyzeUser(username, soup, daysInFuture):

	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	dateNow = datetime.datetime.now()
	res = []

	for m in messages:
		t = m.find('a', attrs={'class': timeAttr})
		dateTime = findDateTime(t.text)
		user = findUser(m)
		isBull = isBullMessage(m)
		symbol = findSymbol(m)
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

		# If result of any price is a 0
		if (prices == 0 or priceAtPost == 0 or newPrices == 0 or price10 == 0 or price1030 == 0 or newPrices == -1):
			continue

		res.append([symbol, dateTime.strftime("%Y-%m-%d %H:%M:%S"), prices, 
			newPrices, isBull, correct, change, percent, likeCnt, commentCnt, priceAtPost, price10, price1030])

	return res

