import os
import datetime
from . import scroll
from .fileIO import *
from .stockPriceAPI import *
from .messageExtract import *
from bs4 import BeautifulSoup

from selenium.common.exceptions import TimeoutException

from .helpers import addToFailedList


# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


messageStreamAttr = 'st_2o0zabc'
timeAttr = 'st_2q3fdlM'
messageTextAttr = 'st_29E11sZ'


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------



# def addToFailedList(date, stock):
# 	path = "failedList.csv"
# 	failedList = readMultiList(path)
# 	failedList.append([date, stock, True])
# 	writeSingleList(path, failedList)
# 	return


# Return soup object page of that stock
def findPageStock(symbol, date, driver, savePage):

	dateNow = datetime.datetime.now()
	days = (dateNow - date).days # days to scroll for

	# if html is stored
	path = 'stocksPages/' + symbol + '.html'
	if (os.path.isfile(path)):
		print("File Exists")
		# html = open(path, "r")
		soup = BeautifulSoup(open(path), 'html.parser')
		print("Finished Reading in")
		return (soup, False)

	url = "https://stocktwits.com/symbol/" + symbol
	failPath = "failedList.csv"

	# Handling exceptions and random shit
	try:
		driver.get(url)
	except:
		print("Timed Out from findPageStock")
		addToFailedList(failPath, date, symbol)
		return (None, True)

	try:
	  	foundEnough = scroll.scrollFor(symbol, days, driver, False)
	except TimeoutException as ex:
	  	print("TIMEOUT EXCEPTION:", ex)
	  	addToFailedList(failPath, date, symbol)
	  	foundEnough = scroll.scrollFor(symbol, days, driver, False)

	if (foundEnough == False):
		return (None, True)

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')

	# If want to save page for "constant" time access
	if (savePage):
		with open(path, "w") as file:
		    file.write(str(soup))

	return (soup, False)



def getBearBull(symbol, date, soup):
	savedSymbolHistorical = []
	try:
		savedSymbolHistorical = get_historical_intraday(symbol, date)
	except:
		return []

	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	res = []

	print(len(messages))
	for m in messages:
		t = m.find('div', {'class': timeAttr})
		t = t.find_all('a') # length of 2, first is user, second is date
		if (t == None):
			continue

		allT = m.find('div', {'class': messageTextAttr})
		allText = allT.find_all('div')
		dateTime = findDateTime(t[1].text)
		user = findUser(t[0])
		textFound = allText[1].find('div').text
		cleanText = ' '.join(removeSpecialCharacters(textFound).split())
		isBull = isBullMessage(m)

		# print(cleanText, user, dateTime)

		if (isValidMessage(dateTime, date, isBull, user, symbol, 0) == False):
			continue

		foundAvg = priceAtTime(dateTime, savedSymbolHistorical) # fix this function to take dateTimeadjusted

		messageInfo = [user, isBull, dateTime, foundAvg, cleanText]
		res.append(messageInfo)

	return res
