from dateutil.parser import parse
import datetime


# Find time of a message
def findDateTime(message):
	if (message == None):
		return None
	else:
		try:
			dateTime = parse(message)
		except:
			return None
		currDay = datetime.datetime.now()
		test = currDay + datetime.timedelta(1)
		if (dateTime > test):
			return datetime.datetime(2018, dateTime.month, dateTime.day, dateTime.hour, dateTime.minute)
		return dateTime


