import os
import datetime
from . import scroll
from .fileIO import *
from .stockPriceAPI import *
from .messageExtract import *
from bs4 import BeautifulSoup


# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


messageStreamAttr = 'st_1m1w96g'
timeAttr = 'st_HsSv26f'
messageTextAttr = 'st_2giLhWN'


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------



# Return soup object page of that stock 
def findPageStock(symbol, days, driver, savePage):
	# if html is stored
	path = 'stocksPages/' + symbol + '.html'
	if (os.path.isfile(path)):
		print("File Exists")
		# html = open(path, "r")
		soup = BeautifulSoup(open(path), 'html.parser')
		print("Finished Reading in")
		return (soup, False)

	url = "https://stocktwits.com/symbol/" + symbol
	driver.get(url)
	foundEnough = scroll.scrollFor(symbol, days, driver, True)

	if (foundEnough == False):
		return (None, True)

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')

	if (savePage):
		with open(path, "w") as file:
		    file.write(str(soup))

	return (soup, False)



def getBearBull(symbol, date, soup):
	savedSymbolHistorical = get_historical_intraday(symbol, date)
	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	res = []

	for m in messages:
		t = m.find('a', {'class': timeAttr})
		if (t == None):
			continue
		textM = m.find('div', attrs={'class': messageTextAttr})
		cleanText = ' '.join(removeSpecialCharacters(textM.text).split())
		print(cleanText)
		dateTime = findDateTime(t.text)
		user = findUser(m)
		isBull = isBullMessage(m)

		if (isValidMessage(dateTime, date, isBull, user, symbol, 0) == False):
			continue

		foundAvg = priceAtTime(dateTime, savedSymbolHistorical) # fix this function to take dateTimeadjusted

		messageInfo = [user, isBull, dateTime, foundAvg, cleanText]
		res.append(messageInfo)

	return res