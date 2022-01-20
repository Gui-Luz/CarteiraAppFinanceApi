import os
import configparser
import logging
from bs4 import BeautifulSoup as bs
import requests
import psycopg2
from datetime import datetime, date

config_file = configparser.ConfigParser()
config_file.read(os.path.dirname(__file__) + '/config.ini')
ENV = config_file['ENV']['env']
api_key = config_file['API INTEGRATION']['finance']
URL = config_file['API INTEGRATION']['stocks_list_page']
LOG_RECYCLE_DAY = config_file['API INTEGRATION']['log_recycle_day']
STOCK_PRICES = config_file['TABLES']['stock_prices']
DATABASE = config_file['DATABASE']['database']
HOST = config_file['DATABASE']['host']
USER = config_file['DATABASE']['user']
PASSWORD = config_file['DATABASE']['password']


def sql():
    conn = connect_to_database()
    cursor = conn.cursor()
    return cursor, conn

def retrieve_all_tuples_from_table(table):
    syntax = f"SELECT * FROM {table};"
    cursor, conn = sql()
    cursor.execute(syntax)
    tuples = cursor.fetchall()
    conn.close()
    return tuples


def connect_to_database():
    conn = psycopg2.connect(database=DATABASE, host=HOST, user=USER, password=PASSWORD)
    conn.cursor()
    return conn


def clean_log_history():
    global LOG_RECYCLE_DAY
    day = date.today().day
    if str(day) == str(LOG_RECYCLE_DAY):
        try:
            os.system('rm engine.log')
        except:
            pass


def get_list_available_stocks():
    try:
        r = requests.get(URL)
        logging.debug(f'[+] Request status code: {r.status_code}')
        if r.status_code == 200:
            soup = bs(r.text, 'html.parser')
            stock_tag = soup.findAll('code')
            available_stocks_list = list(set([stock.text for stock in stock_tag]))
            logging.debug(f'[+] {len(available_stocks_list)} stocks found...')
            return True, available_stocks_list
        else:
            return False, None
    except Exception as e:
        return False, e


def get_stocks_table_in_db():
    logging.debug(f'[+] Getting stocks in storage...')
    tuples = retrieve_all_tuples_from_table(STOCK_PRICES)
    logging.debug(f'[+] Stocks found: {len(tuples)}')
    return tuples


def compare_stock_available_with_stocks_in_storage(stocks_available, stocks_in_db):
    active_stocks = [stock[0] for stock in stocks_in_db if stock[4]]
    inactive_stocks = [stock[0] for stock in stocks_in_db if not stock[4]]
    logging.debug(f'[+] Active stocks: {len(active_stocks)}')
    logging.debug(f'[+] Inactive stocks: {len(inactive_stocks)}')
    stocks_for_activation = [stock for stock in stocks_available if (stock not in active_stocks) and (stock in inactive_stocks)]
    stocks_for_adding = [stock for stock in stocks_available if (stock not in active_stocks) and (stock not in inactive_stocks)]
    logging.debug(f'[+] Stocks for activation: {len(stocks_for_activation)}')
    logging.debug(f'[+] Stocks for activation: {(stocks_for_activation)}')
    logging.debug(f'[+] Stocks for adding: {len(stocks_for_adding)}')
    logging.debug(f'[+] Stocks for adding: {(stocks_for_adding)}')
    return stocks_for_adding, stocks_for_activation


def insert_tuples_on_stock_prices_table(stocks_for_adding):
    logging.debug(f'[+] Adding {len(stocks_for_adding)} stocks to stocks price table...')
    conn = connect_to_database()
    cursor = conn.cursor()
    for stock in stocks_for_adding:
        try:
            syntax = f"""INSERT INTO {STOCK_PRICES} (stock, description, price, datetime, active) 
                        VALUES ('{stock}', 'Null', '0', '{datetime.now()}', 'True')"""
            cursor.execute(syntax)
        except Exception as e:
            logging.warning(f'{stock}: {e}')
    conn.commit()
    conn.close()


def activate_stocks_in_stock_prices_tables(stocks_for_activating):
    logging.debug(f'[+] Activating {len(stocks_for_activating)} stocks in stocks price table...')
    conn = connect_to_database()
    cursor = conn.cursor()
    for stock in stocks_for_activating:
        try:
            syntax = f"""UPDATE stock_prices
                            SET active = 'True'
                            WHERE "stock" = '{stock}'"""
            cursor.execute(syntax)
        except Exception as e:
            logging.warning(f'{stock}: {e}')
    conn.commit()
    conn.close()


def request_stock_price(available_stocks):
    logging.debug(f'[+] Getting {len(available_stocks)} stock prices...')
    stocks_info = []
    for stock in available_stocks:
        api_url = f'https://api.hgbrasil.com/finance/stock_price?key={api_key}&symbol={stock}'
        r = requests.get(api_url)
        if r.status_code == 200:
            try:
                json = r.json()
                symbol = json['results'][stock]['symbol']
                name = json['results'][stock.upper()]['name']
                price = json['results'][stock]['price']
                updated_at = json['results'][stock]['updated_at']
                stocks_info.append((symbol, name, price, updated_at))
            except KeyError as e:
                logging.warning(f'[+] Could not get {stock} price')
                logging.warning(f'[+] Error message {e}')
                pass
        else:
            logging.warning(f'[+] Could not request URL: {api_url}')
            pass
    return stocks_info


def update_stock_info(stocks_info):
    logging.debug(f'[+] Updating {len(stocks_info)} stocks in stocks price table...')
    conn = connect_to_database()
    cursor = conn.cursor()
    for stock in stocks_info:
        try:
            syntax = f"""UPDATE stock_prices
                            SET price = '{stock[2]}',
                            description = '{stock[1]}',
                            datetime = '{stock[3]}'
                            WHERE "stock" = '{stock[0]}';"""
            cursor.execute(syntax)
        except Exception as e:
            logging.warning(f'{stock}: {e}')
    conn.commit()
    conn.close()
    logging.debug('[+] Stocks updated!')


def main():
    global ENV, URL
    clean_log_history()
    if ENV == 'production':
        logging.basicConfig(level=logging.DEBUG, filename='engine.log', format='%(levelname)s:%(message)s')
    if ENV == 'development':
        logging.basicConfig(level=logging.DEBUG, filename='engine.log', format='%(levelname)s:%(message)s')

    logging.debug(f'[+] STARTING STOCK PRICES THIRD PARTY INTEGRATION ENGINE')
    logging.debug(f'[+] {datetime.now()}')
    logging.debug(f'[+] API endpoint: {URL}...')
    available_stocks = get_list_available_stocks()
    if available_stocks[0]:
        stocks_on_storage = get_stocks_table_in_db()
        stocks_for_adding, stocks_for_activation = compare_stock_available_with_stocks_in_storage(available_stocks[1],
                                                                                                  stocks_on_storage)
        if stocks_for_activation:
            activate_stocks_in_stock_prices_tables(stocks_for_activation)
        if stocks_for_adding:
            insert_tuples_on_stock_prices_table(stocks_for_adding)
        stocks_info = request_stock_price(available_stocks[1])
        update_stock_info(stocks_info)
    else:
        logging.critical(f'[+] Could not find available stocks... Breaking!')
        logging.critical(f'[+] Error message: {available_stocks[1]}')
    logging.debug(f'[+] {datetime.now()}')
    logging.debug('[+] END')

