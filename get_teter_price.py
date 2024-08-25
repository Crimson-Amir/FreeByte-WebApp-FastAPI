import requests

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
}

def get_teter_price_in_rial():

    response = requests.get(
        'https://api.ompfinex.com/v2/udf/real/history?symbol=USDTIRT&resolution=60&from=1717100000&to=1717134009&countback=320',
        headers=headers,
        verify=False
    )

    try:
        response.raise_for_status()
        return int(float(response.json().get('o', [0])[-1]))
    except Exception as e:
        print(f'Error in get request -> {e}')
        return 0

