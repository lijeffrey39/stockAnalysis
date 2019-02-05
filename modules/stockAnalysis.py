import os
from . import scroll
from bs4 import BeautifulSoup
from stocktwits import *


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------



# Return soup object page of that stock 
def findPageStock(symbol, days, driver):
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
	foundEnough = scroll.scrollFor(symbol, days, driver)

	if (foundEnough == False):
		return (None, True)

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')

	if (SAVE_STOCK_PAGE):
		with open(path, "w") as file:
		    file.write(str(soup))

	return (soup, False)