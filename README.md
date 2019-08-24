# stockAnalysis
Analyzing stock performance using Stock Twits

## Running the program

Flags: <br />
--daysback: # days to scrape back from the current day <br />
--numstocks: top n stocks to invest from (lower means more risk) <br />


1. Scrape data from a given day

```
# scrape the current day's tweets for all stocks
python3 stocktwits.py --stocks --daysback 0 
```

2. Scrape data from users

```
# scrape tweets from all users 
python3 stocktwits.py --users --daysback 75 
python3 stocktwits.py --u --daysback 20 
```


3. Calculate returns from past data

```
# calculate returns for each day back from current day
python3 stocktwits.py --returns --daysback 30 --numstocks 5 
```

4. Predict stocks

```
# predict which stocks to buy 
# run at end of the day
python3 stocktwits.py --numstocks 1
```
