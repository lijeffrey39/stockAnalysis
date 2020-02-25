import datetime
import time
import statistics
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
from .helpers import (readPickleObject, writePickleObject)
from random import shuffle
import matplotlib.pyplot as plt


def findAllUsers():
    accuracy = constants['db_user_client'].get_database('user_data_db').users
    allUsersAccs = accuracy.find()
    allUserNames = list(map(lambda doc: doc['_id'], allUsersAccs))
    print(len(allUserNames))
    print(allUserNames[:10])


def removeMessagesWithStock(stock):
    analyzedUsersDB = constants['db_user_client'].get_database('user_data_db')
    userAccuracy = analyzedUsersDB.user_accuracy_v2
    allAccs = userAccuracy.find({'perStock.' + stock: { '$exists': True }})
    mappedTweets = list(map(lambda doc: [doc['_id'], doc['perStock'][stock]['1']['returnUnique']['bull']], allAccs))
    mappedTweets.sort(key=lambda x: x[1], reverse=True)
    print(len(mappedTweets))
    # shuffle(mappedTweets)
    xs = []
    ys = []
    for x in mappedTweets:
        user = x[0]
        # userAccuracy.delete_one({'_id': user})
        result = getAllUserInfo(user)
        if (len(result) != 0):
            # result['accuracyUnique']
            stockCorrect = result['perStock'][stock]['1']['numUnique']['bull'] + result['perStock'][stock]['1']['numUnique']['bear']
            stockPredictions = result['perStock'][stock]['1']['numUniquePredictions']['bull'] + result['perStock'][stock]['1']['numUniquePredictions']['bear']
            returns = result['perStock'][stock]['1']['returnUnique']['bull'] + result['perStock'][stock]['1']['returnUnique']['bear']
            accuracy = stockCorrect / stockPredictions
            xs.append(accuracy)
            ys.append(returns)
            print(user, accuracy, returns)

    print(xs)
    print(ys)
    plt.plot(xs, ys, 'ro')
    plt.show()


def findTopUsers():
    analyzedUsersDB = constants['db_user_client'].get_database('user_data_db')
    userAccuracy = analyzedUsersDB.user_accuracy_v2
    allAccs = userAccuracy.find()
    mappedTweets = list(map(lambda doc: [doc['_id'], doc['1']['returnUnique']['bull']], allAccs))
    mappedTweets.sort(key=lambda x: x[1], reverse=True)

    for x in mappedTweets[:30]:
        print(x[0], x[1])
        findBadMessages(x[0])


def findBadMessages(user):
    analyzedUsersDB = constants['db_user_client'].get_database('user_data_db')
    userAccuracy = analyzedUsersDB.user_accuracy_v2
    # userAccuracy.delete_one({'_id': user})
    userInfo = getAllUserInfo(user)
    if (len(userInfo) == 0):
        return
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


def findOutliers(stock):
    # returns = [669.5659999999999, 532.6819999999999, 531.539, 526.7639999999999, 511.41799999999995, 109.92499999999998, 101.82, 81.062, 78.419, 73.171, 70.671, 67.361, 58.239, 60.754000000000005, 52.19800000000001, 41.442, 27.136999999999997, 16.711, 15.731, 14.177999999999997, 14.008, 13.921000000000001, 13.625, 13.603, 12.059, 11.783, 11.668, 11.623000000000001, 8.714, 8.153, 7.895, 7.232, 6.979, 6.966, 6.461, 6.347, 8.837, 6.273, 6.183, 6.012, 5.941, 5.941, 5.922, 5.88, 5.827, 5.674, 5.674, 5.0280000000000005, 4.972, 4.732, 4.63, 4.63, 4.598, 4.598, 4.598, 4.574, 4.167, 4.029999999999999, 3.8110000000000017, 3.789, 3.7340000000000004, 4.284, 3.455, 3.455, 3.384, 3.3500000000000005, 3.212, 3.0200000000000005, -5.584999999999999, 2.886, 2.713, 2.5860000000000007, 2.576, 2.5, 2.472, 2.3770000000000007, 2.247, 2.098, 1.6719999999999997, 1.667, 1.667, 1.667, 1.667, 1.667, 1.563, 1.481, 1.4370000000000005, 1.235, 1.2339999999999995, 1.152, 1.111, 1.039, 0.909, 0.909, 0.909, 0.8759999999999999, 0.763, 0.598, 0.565, 0.565, 0.524, 0.524, 0.524, -0.666, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -2.688, 0.0, 0.0, -13.555000000000001, 0.0, 0.0, -1.667, 0.0, 0.0, 0.0, 0.0, 0.676, 1.333, 0.0, 0.0, 0.0, 0.0, -6.18, 0.0, 0.0, 0.0, 0.0, 0.0, 4.947, 0.0, -0.01399999999999979, -0.014000000000000012, -0.019000000000000017, -0.06599999999999995, -0.14800000000000002, -0.46399999999999997, -0.488, -0.538, -0.538, -0.538, -0.558, -0.575, -0.6039999999999999, -0.6379999999999999, -0.769, -0.799, -0.943, -1.087, -1.087, -1.087, -1.087, -1.087, -1.087, 0.29800000000000004, -1.087, -1.099, -1.099, -1.099, -1.1059999999999999, -1.13, -1.13, -1.143, -1.22, -1.237, -1.242, -1.258999999999999, -1.333, -1.361, -1.443, -1.622, -1.698, -1.698, -1.698, -1.698, -1.698, -1.698, -1.751, -1.9180000000000008, -2.073, -2.206, -2.326, -2.391, -2.395, -2.484, -2.5, -2.514, -2.2, -3.021, -2.778, -2.7969999999999997, -2.8949999999999996, -3.057, -3.3040000000000003, -3.454, -3.477, -3.54, -3.804, -4.024, -4.059, -4.094, -4.181, -4.311000000000001, -4.359000000000001, -4.387, -5.474, -4.682, -5.213, -5.231000000000001, -5.305999999999999, -5.552, -5.59, -5.820999999999999, -5.866999999999999, -6.042, -6.300000000000001, -6.365, -6.850999999999999, -7.053000000000001, -7.447, -8.303, -8.8, -10.047, -12.484, -12.948999999999996, -13.494, -19.517, -21.052999999999997, -23.700999999999993, -37.632, -38.45, -54.009]

    analyzedUsersDB = constants['db_user_client'].get_database('user_data_db')
    userAccuracy = analyzedUsersDB.user_accuracy_v2
    allAccs = userAccuracy.find({'perStock.' + stock: { '$exists': True }})
    mappedTweets = list(map(lambda doc: [doc['_id'], doc['perStock'][stock]['1']['returnUnique']['bull']], allAccs))
    returns = []
    users = []
    print(len(mappedTweets))
    for x in mappedTweets:
        user = x[0]
        # userAccuracy.delete_one({'_id': user})
        result = getAllUserInfo(user)
        if (len(result) != 0):
            # result['accuracyUnique']
            # stockCorrect = result['perStock'][stock]['1']['numUnique']['bull'] + result['perStock'][stock]['1']['numUnique']['bear']
            # stockPredictions = result['perStock'][stock]['1']['numUniquePredictions']['bull'] + result['perStock'][stock]['1']['numUniquePredictions']['bear']
            r = result['perStock'][stock]['1']['returnUnique']['bull'] + result['perStock'][stock]['1']['returnUnique']['bear']
            returns.append(r)
            users.append(user)

    mean = statistics.mean(returns)
    std = statistics.stdev(returns)
    print(mean, std)

    for i in range(len(returns)):
        stdDev = (r - mean) / std
        if (stdDev > 3):
            print(users[i], r, stdDev)


def findErrorUsers():
    analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
    dateStart = convertToEST(datetime.datetime.now()) - datetime.timedelta(days=20)
    query = {"$and": [{'error': {'$ne': 'Not enough ideas'}},
                      {'error': {'$ne': "User doesn't exist"}},
                      {'error': {'$ne': ""}},
                      {'error': {'$ne': "User doesn't exist / API down"}},
                      {'error': {'$ne': 'User has no tweets'}},
                      {'error': {'$ne': "Empty result list"}}]}
    cursor = analyzedUsers.find(query)
    print(cursor.count())

    # for x in cursor[:100]:
    #     print(x['_id'], x['error'])


def saveUserInfo():
    accuracy = constants['db_user_client'].get_database('user_data_db').user_accuracy_v2
    allUsersAccs = accuracy.find()
    path = 'pickledObjects/tempUserInfo.pkl'
    result = readPickleObject(path)
    count = 0
    for user in allUsersAccs:
        print(user['_id'])
        result[user['_id']] = user
        if (count % 100 == 0):
            count = 0
            print(count)
    
    writePickleObject(path, result)


# def readUserInfo():
#     path = 'pickledObjects/tempUserInfo.pkl'
#     result = readPickleObject(path)
#     res = {}
#     count = 0
#     for user in result:
#         print(user, result[user]['1']['numCloseOpen']['bull'])
#         result[user['_id']] = user
#         count += 1
#         if (count % 100 == 0):
#             count = 0
#             print(count)

#     writePickleObject(path res)