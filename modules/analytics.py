import os
import datetime
from .fileIO import *



# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------



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


def viewStockActivity():
	path = "stocksResults/"
	folderL = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) == False] 
	
	stockDict = {}

	for folder in folderL:
		newP = path + folder + '/'
		stocks = [f for f in os.listdir(newP) if os.path.isfile(os.path.join(newP, f))] 
		stocks = list(map(lambda x: x[:len(x) - 4], stocks))
		stocks = list(filter(lambda x: '.DS_S' not in x, stocks))
		for s in stocks:
			sPath = newP + s + '.csv'
			read = readMultiList(sPath)
			if s not in stockDict:
				stockDict[s] = [len(read)]
			else:
				stockDict[s].append(len(read))

	res = []
	for k in stockDict:
		res.append([k, sum(stockDict[k])])

	res.sort(key = lambda x: x[1], reverse = True)
	for r in res:
		print(r)


def generateAllUsers():
	path = "newUsers/"
	files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))] 
	files = sorted(list(filter(lambda x: x != '.DS_Store', files)))

	users = []
	for file in files:
		print(file)
		res = readSingleList(path + file)
		res = list(filter(lambda x: len(x) > 0, res))

		users.extend(res)
		users = list(set(users))

	users.sort()
	users = list(map(lambda x: [x], users))
	writeSingleList('allNewUsers.csv', users)