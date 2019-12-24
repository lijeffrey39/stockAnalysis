import datetime
import time
from .helpers import (convertToEST,
                      customHash,
                      endDriver,
                      getActualAllStocks,
                      findWeight,
                      findJoinDate,
                      getAllStocks)
from .hyperparameters import constants
from .stockPriceAPI import (findCloseOpen,
                            inTradingDay,
                            getUpdatedCloseOpen)
from .stockAnalysis import getTopStocks
from .userAnalysis import getAllUserInfo
from random import shuffle


def removeMessagesWithStock(stock):
    analyzedUsersDB = constants['db_user_client'].get_database('user_data_db')
    userAccuracy = analyzedUsersDB.user_accuracy_v2
    allAccs = userAccuracy.find({'perStock.' + stock: { '$exists': True }})
    mappedTweets = list(map(lambda doc: [doc['_id'], doc['perStock'][stock]['1']['returnCloseOpen']['bull']], allAccs))
    mappedTweets.sort(key=lambda x: x[1], reverse=True)
    print(len(mappedTweets))
    # shuffle(mappedTweets)
    for x in mappedTweets:
        user = x[0]
        userAccuracy.delete_one({'_id': user})
        result = getAllUserInfo(user)
        if (len(result) != 0):
            print(user, result['accuracyUnique'])


def findBadMessages():
    analyzedUsersDB = constants['db_user_client'].get_database('user_data_db')
    userAccuracy = analyzedUsersDB.user_accuracy_v2


    # allAccs = userAccuracy.find()
    # mappedTweets = list(map(lambda doc: [doc['_id'], doc['1']['returnUnique']['bull']], allAccs))
    # mappedTweets.sort(key=lambda x: x[1], reverse=True)

    # for x in mappedTweets[:30]:
    #     print(x[0], x[1])

    # return

    user = 'cantrder72'
    # userAccuracy.delete_one({'_id': user})
    userInfo = getAllUserInfo(user)
    perStock = list(userInfo['perStock'].keys())
    print(perStock)
    res = {}
    s1 = 0
    print(userInfo['1']['returnUnique']['bull'])
    for s in perStock:
        res[s] = userInfo['perStock'][s]['1']['returnUnique']['bull']
        s1 += userInfo['perStock'][s]['1']['returnUnique']['bull']
    print(s1)
    bestParams = list(res.items())
    bestParams.sort(key=lambda x: x[1], reverse=False)
    for x in bestParams:
        print(x)
