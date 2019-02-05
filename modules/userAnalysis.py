import os
import sys
sys.path.append("..")

from . import scroll
from .fileIO import *
from bs4 import BeautifulSoup


SAVE_USER_PAGE = False
SAVE_STOCK_PAGE = False

# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------



# Return soup object page of that user 
def findPageUser(username, days, driver):
	# if html is stored
	path = 'usersPages/' + username + '.html'
	if (os.path.isfile(path)):
		print("File Exists")
		# html = open(path, "r")
		soup = BeautifulSoup(open(path), 'html.parser')
		return soup

	url = "https://stocktwits.com/" + username
	driver.get(url)
	foundEnough = scroll.scrollFor(username, days, driver)

	if (foundEnough == False):
		return None

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')

	if (SAVE_USER_PAGE):
		with open(path, "w") as file:
		    file.write(str(soup))

	return soup