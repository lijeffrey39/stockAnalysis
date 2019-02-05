import os
import csv
import threading

from . import helpers
from functools import reduce


# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------



global_lock = threading.Lock()



# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------



def createUsersCSV():
	users = helper.allUsers()
	result = []
	resPath = 'userInfo.csv'

	for user in users:
		path = 'userCalculated/' + user + '_info.csv'
		if (os.path.isfile(path) == False):
			continue

		res = readMultiList(path)
		if (len(res) == 0):
			continue

		res.sort(key = lambda x: x[4], reverse = True)
		res = list(map(lambda x: [x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4])], res))

		total = round(reduce(lambda a, b: a + b, list(map(lambda x: x[4], res))), 4)
		correct = round(reduce(lambda a, b: a + b, list(map(lambda x: x[2], res))), 4)
		incorrect = round(reduce(lambda a, b: a + b, list(map(lambda x: x[3], res))), 4)

		result.append([user, correct, incorrect, total])

	result.sort(key = lambda x: x[3], reverse = True)
	writeSingleList(resPath, result)



def removeSpecialCharacters(string):
	return ''.join(e for e in string if e.isalnum())


# Read a single item CSV
def readSingleList(path):
	l = []

	if not os.path.exists(path):
		return l

	with open(path) as f:
		file = f.readlines()
		for i in file:
			l.append(removeSpecialCharacters(i))
	return l


# Read a multi item CSV
def readMultiList(path):
	l = []

	if not os.path.exists(path):
		return l

	with open(path) as f:
		file = f.readlines()
		for i in file:
			x = i.split(',')
			if (x[0] == '\n' or len(x) == 1):
				continue
			for j in range(len(x)):
				# remove new line
				if ('\n' in x[j]):
					x[j] = x[j][:len(x[j]) - 1]
			l.append(x)
	return l


# Write 1d array of items to CSV 
def writeSingleList(path, items):

	while global_lock.locked():
		continue

	global_lock.acquire()

	with open(path, "w", newline='') as my_csv:
	    csvWriter = csv.writer(my_csv, delimiter=',')
	    csvWriter.writerows(items)

	global_lock.release()



def addToNewList(l, path):
	currList = readSingleList(path)
	currList.extend(l)
	currList = list(set(currList))
	currList.sort()

	for i in range(len(currList)):
		currList[i] = [currList[i]]

	writeSingleList(path, currList)

