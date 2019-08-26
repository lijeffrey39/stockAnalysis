from hyperparameters import constants
import requests
import datetime 
import hashlib
import pymongo
import time


def updateStock(ticker, hours_back, interval=5):
    api_call = 'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=%s&interval=%dmin&outputsize=full&apikey=%s' % (ticker, interval, constants['alpha_vantage_api_key'])
    response = requests.get(url=api_call)
    price_data = None
    price_data_list = []
    try:
        price_data = response.json()['Time Series (%dmin)' % (interval)]
    except KeyError:
        time.sleep(60)
        response = requests.get(url=api_call)
        try:
            price_data = response.json()['Time Series (%dmin)' % (interval)]
        except:
            print(response.json())
            return
    price_data_list = []
    stock_data_collection = constants['db_client'].get_database('stocks_data_db').stock_data
    for timestamp_s in price_data:
        price_data_dict = {}
        timestamp = datetime.datetime.strptime(timestamp_s, '%Y-%m-%d %H:%M:%S')
        datetime_elapsed = datetime.datetime.now() - timestamp
        hours_elapsed = 24 * datetime_elapsed.days + int(datetime_elapsed.seconds/3600)
        if hours_elapsed > hours_back:
            break
        else:
            id = ticker+timestamp_s
            price_data_dict['_id'] = id
            price_data_dict['ticker'] = ticker
            price_data_dict['timestamp'] = timestamp_s
            price_data_dict['date'] = timestamp_s[:10]
            price_data_dict['price'] = 0.5 * round((float(price_data[timestamp_s]['2. high'])+float(price_data[timestamp_s]['3. low'])), 2)
            price_data_list.append(price_data_dict)

            #stock_data_collection.update({'_id':id}, {'$set': price_data_dict}, upsert=True)
    stock_data_collection.insert_many(price_data_list)


def updateAllStocks(hours_back=24, interval=5):
    all_tickers = constants['db_client'].get_database('stocktwits_db').all_stocks.find({})
    for t in all_tickers:
        if t['_id'] in already_written:
            continue
        print('Updating stock data for ticker %s' % (t['_id']))
        updateStock(t['_id'], hours_back, interval)
        written_file.write(t['_id']+'\n')

already_written = set()
with open('already_written.txt', 'r') as f:
    for line in f:
        already_written.add(line.strip())
written_file = open('already_written.txt', 'a+')
updateAllStocks(hours_back=24*35)
written_file.close()