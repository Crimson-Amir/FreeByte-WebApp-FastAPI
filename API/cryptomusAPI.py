import aiohttp, base64, hashlib, json

class MakeRequest:
    @staticmethod
    async def send_request(method, url, params=None, json_data=None, data=None, header=None, session_header=None):
        async with aiohttp.ClientSession(headers=session_header) as session:
            async with session.request(method, url, params=params, json=json_data, data=data, headers=header) as response:
                response.raise_for_status()
                return await response.json()

class Encryption:
    @staticmethod
    def md5_hash(data: bytes) -> str:
        return hashlib.md5(data).hexdigest()

    @staticmethod
    def b64encoding(data: bytes) -> str:
        return base64.b64encode(data).decode('utf-8')

    @staticmethod
    def b64decoding(data: str) -> bytes:
        return base64.b64decode(data)


class Cryptomus:
    def __init__(self, api_key: str, merchant_id: str):
        self._api_key = api_key
        self._merchant_id = merchant_id
        self._encryption = Encryption()
        self.headers = {
            'merchant': self._merchant_id,
            'sign': '',
            'Content-Type': 'application/json'
        }

    def create_sign(self, data: dict) -> str:
        encoded_params = self._encryption.b64encoding(json.dumps(data).encode('utf-8')) if data else ''
        return self._encryption.md5_hash(f'{encoded_params}{self._api_key}'.encode('utf-8'))


class CreateInvoice(Cryptomus):
    request_endpoint = 'https://api.cryptomus.com/v1/payment'

    async def execute(self, amount, currency, order_id, **kwargs) -> dict:
        data = {
            'amount': amount,
            'currency': currency,
            'order_id': order_id,
            **kwargs
        }
        self.headers['sign'] = self.create_sign(data)
        return await MakeRequest().send_request('post', self.request_endpoint, session_header=self.headers, json_data=data)


class InvoiceInfo(Cryptomus):
    request_endpoint = 'https://api.cryptomus.com/v1/payment/info'

    async def execute(self, order_id, uuid=None) -> dict:
        data = {
            'order_id': order_id,
            'uuid': uuid
        }
        self.headers['sign'] = self.create_sign(data)
        return await MakeRequest().send_request('post', self.request_endpoint, session_header=self.headers, json_data=data)


class Refund(Cryptomus):
    request_endpoint = 'https://api.cryptomus.com/v1/payment/refund'

    async def execute(self, address: str, is_subtract: str, **kwargs) -> dict:
        data = {'address': address, 'is_subtract': is_subtract, **kwargs}
        self.headers['sign'] = self.create_sign(data)
        return await MakeRequest().send_request('post', self.request_endpoint, session_header=self.headers, json_data=data)
