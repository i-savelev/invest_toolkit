import requests

def get_last_price(ticker):
    """
    Получает последнюю цену акции с Московской биржи по тикеру через MOEX ISS API.

    Запрашивает данные по эндпоинту:
        `https://iss.moex.com/iss/engines/stock/markets/shares/securities/{ticker}.json?iss.only=marketdata`

    Алгоритм:
    1. Получает JSON с `marketdata`.
    2. Ищет первую строку в `marketdata['data']`, содержащую `'TQBR'` в любом столбце (текущая логика: **берёт последнюю строку**, содержащую `'TQBR'`).
    3. Извлекает значения `'LAST'` и `'MARKETPRICE'`.
    4. Возвращает `LAST`, если не `None`, иначе `MARKETPRICE`.

    :param ticker: Тикер инструмента (например, `"SBER"`, `"PMSB"`).
    :type ticker: str

    :returns: Последняя цена (`LAST`), если доступна; иначе рыночная цена (`MARKETPRICE`);
              `None`, если обе цены `None` или данных нет.
    :rtype: Optional[float]

    :raises requests.exceptions.RequestException: При ошибках HTTP (404, таймаут и др.).
    :raises ValueError: Если ответ не содержит ожидаемых полей (`marketdata`, `columns`, `data`).
    :raises IndexError: Если `'LAST'` или `'MARKETPRICE'` отсутствуют в `columns`.
    :raises KeyError: Если `ticker` не найден или `marketdata` пуст.

    !!! Добавить кэширвоание (@lru_cache или requests-cache.)
    """
    url = f"https://iss.moex.com/iss/engines/stock/markets/shares/securities/{ticker}.json?iss.only=marketdata"
    response = requests.get(url)
    data = response.json()
    share_dict = {}
    data_row = None
    columns = data['marketdata']['columns']
    data_row_list = data['marketdata']['data']
    data_row = data_row_list[0]
    for data_row in data_row_list:
        if "TQBR" in data_row:
            data_row = data_row

    last_price_index = columns.index('LAST')
    market_price_index = columns.index('MARKETPRICE')
    
    last_price = data_row[last_price_index]
    market_price = data_row[market_price_index]
    
    share_dict['last_price'] = last_price
    share_dict['market_price'] = market_price

    if share_dict['last_price']:
        return share_dict['last_price']
    else: 
        return share_dict['market_price']
    

if __name__ == '__main__':
    print(get_last_price("PMSB")) 