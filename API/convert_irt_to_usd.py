import requests, logging
usd_default_price = 60_000

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
}

def convert_irt_to_usd_by_teter(irt: int):

    response = requests.get(
        'https://api.ompfinex.com/v2/udf/real/history?symbol=USDTIRT&resolution=60&from=1717100000&to=1717134009&countback=320',
        headers=headers,
        verify=False
    )

    try:
        response.raise_for_status()
        usd_value = int(float(response.json().get('o', [0])[-1]))
        return round(irt / usd_value, 2)
    except Exception as e:
        logging.error(f'Error in get teter price.\n{e}')
        return round(irt / usd_default_price, 2)

