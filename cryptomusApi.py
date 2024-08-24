import aiohttp
import asyncio
import base64
import hashlib
import json
from typing import List, Dict, Optional, Union

"""
:param amount: Amount to be paid. Example: 10.28
:param currency: Currency code
:param order_id: Order ID in your system. max: 128
:param network: Blockchain network code
:param url_return: Before paying, the user can click on the button on the payment form and return to the store page at this URL. max: 255
:param url_success: After successful payment, the user can click on the button on the payment form and return to this URL. max: 255
:param url_callback: URL to which webhooks with payment status will be sent. max: 255
:param is_payment_multiple: Whether the user is allowed to pay the remaining amount. Useful when the user has not paid the entire amount of the invoice for one transaction.
:param lifetime: The lifespan of the issued invoice (in seconds). min: 300 - max: 43200
:param to_currency: The target currency for converting the invoice amount.
:param subtract: Percentage of the payment commission charged to the client. max: 100
:param accuracy_payment_percent: Acceptable inaccuracy in payment. max: 5
:param additional_data: Additional information for you (not shown to the client). max: 255
:param currencies: List of allowed currencies for payment.
:param except_currencies: List of excluded currencies for payment.
:param course_source: The service from which the exchange rates are taken for conversion in the invoice. min: 4 - max: 20
:param from_referral_code: The merchant who makes the request connects to a referrer by code.
:param discount_percent: Positive numbers: Allows you to set a discount. Negative numbers: Allows you to set custom additional commission. min: -99 - max: 100
:param is_refresh: Update the lifetime and get a new address for the invoice if the lifetime has expired.
"""


class SessionError(Exception):
    pass


class MakeRequest:
    def __init__(self, session: aiohttp.ClientSession):
        self._session = session

    async def make_request(self, url: str, headers: Optional[Dict[str, str]] = None, data: Optional[Dict] = None):
        if not self._session:
            raise SessionError("Session is not set!")

        try:
            async with self._session.post(url, headers=headers, json=data, ssl=False, timeout=15) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except aiohttp.ClientResponseError as e:
            print(f"Request failed with status {e.status}: {e.message}")
            return None


class RequestFactory:
    @staticmethod
    async def run_requests(requests_list: Union[List[str], str], session_header: Optional[Dict[str, str]] = None,
                           headers: Optional[Dict[str, str]] = None, data: Optional[Dict] = None,
                           return_exceptions: bool = True):
        if isinstance(requests_list, str):
            requests_list = [requests_list]

        async with aiohttp.ClientSession(headers=session_header) as session:
            request_manager = MakeRequest(session)
            tasks = [request_manager.make_request(request, headers=headers, data=data) for request in requests_list]
            return list(await asyncio.gather(*tasks, return_exceptions=return_exceptions))[0]


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
        self._request_manager = RequestFactory()
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

    async def execute(self, amount: str, currency: str, order_id: str, **kwargs) -> dict:
        data = {
            'amount': amount,
            'currency': currency,
            'order_id': order_id,
            **kwargs
        }
        self.headers['sign'] = self.create_sign(data)
        return await self._request_manager.run_requests(self.request_endpoint, session_header=self.headers, data=data)


class InvoiceInfo(Cryptomus):
    request_endpoint = 'https://api.cryptomus.com/v1/payment/info'

    async def execute(self, order_id: str, uuid: Optional[str] = None) -> dict:
        data = {'order_id': order_id, 'uuid': uuid}
        self.headers['sign'] = self.create_sign(data)
        return await self._request_manager.run_requests(self.request_endpoint, session_header=self.headers, data=data)


class CreateStaticWallet(Cryptomus):
    request_endpoint = 'https://api.cryptomus.com/v1/wallet'

    async def execute(self, currency: str, order_id: str, **kwargs) -> dict:
        data = {'currency': currency, 'order_id': order_id, **kwargs}
        self.headers['sign'] = self.create_sign(data)
        return await self._request_manager.run_requests(self.request_endpoint, session_header=self.headers, data=data)


class PaymentHistory(Cryptomus):
    request_endpoint = 'https://api.cryptomus.com/v1/payment/list'

    async def execute(self, date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
        data = {'date_from': date_from, 'date_to': date_to}
        self.headers['sign'] = self.create_sign(data)
        return await self._request_manager.run_requests(self.request_endpoint, session_header=self.headers, data=data)


class GenerateQrCode(Cryptomus):
    request_endpoint = 'https://api.cryptomus.com/v1/wallet/qr'

    async def execute(self, wallet_address_uuid: str) -> dict:
        data = {'wallet_address_uuid': wallet_address_uuid}
        self.headers['sign'] = self.create_sign(data)
        return await self._request_manager.run_requests(self.request_endpoint, session_header=self.headers, data=data)


class BlockStaticWallet(Cryptomus):
    request_endpoint = 'https://api.cryptomus.com/v1/wallet/block-address'

    async def execute(self, uuid: str, order_id: str, is_force_refund: Optional[str] = None) -> dict:
        data = {'uuid': uuid, 'order_id': order_id, 'is_force_refund': is_force_refund}
        self.headers['sign'] = self.create_sign(data)
        return await self._request_manager.run_requests(self.request_endpoint, session_header=self.headers, data=data)


class Refund(Cryptomus):
    request_endpoint = 'https://api.cryptomus.com/v1/payment/refund'

    async def execute(self, address: str, is_subtract: str, **kwargs) -> dict:
        data = {'address': address, 'is_subtract': is_subtract, **kwargs}
        self.headers['sign'] = self.create_sign(data)
        return await self._request_manager.run_requests(self.request_endpoint, session_header=self.headers, data=data)


class ResendWebhook(Cryptomus):
    request_endpoint = 'https://api.cryptomus.com/v1/payment/resend'

    async def execute(self, order_id: str, uuid: Optional[str] = None) -> dict:
        data = {'order_id': order_id, 'uuid': uuid}
        self.headers['sign'] = self.create_sign(data)
        return await self._request_manager.run_requests(self.request_endpoint, session_header=self.headers, data=data)


class TestingWebhook(Cryptomus):
    request_endpoint = 'https://api.cryptomus.com/v1/test-webhook/{}'
    request_endpoint_key = {
        'testing_payment': 'payment',
        'testing_payout': 'payout',
        'testing_wallet': 'wallet',
    }

    async def execute(self, currency: str, network: str, url_callback: str, test_section: str = 'testing_payment',
                      **kwargs) -> dict:
        data = {'currency': currency, 'network': network, 'url_callback': url_callback, **kwargs}
        self.headers['sign'] = self.create_sign(data)
        endpoint = self.request_endpoint.format(self.request_endpoint_key[test_section])
        return await self._request_manager.run_requests(endpoint, session_header=self.headers, data=data)


class ListOfService(Cryptomus):
    request_endpoint = 'https://api.cryptomus.com/v1/payment/services'

    async def execute(self) -> dict:
        self.headers['sign'] = self.create_sign({})
        return await self._request_manager.run_requests(self.request_endpoint, session_header=self.headers)


def client(cryptomus_api_key: str, cryptomus_merchant_id: str, class_, **method_kwargs) -> dict:
    class_instance = class_(cryptomus_api_key, cryptomus_merchant_id)
    return asyncio.run(class_instance.execute(**method_kwargs))


# cryptomus_api_key = 'xbPjwvsT6qiypVVwYHvUsjp5giSH2WUQ75oBDuiHSM7Wi5Zu2t9h8R02R7WC1ptF6FLfeDq1gyYTcHP9Rf4N2dwNcNTWA1PlaAaY666VGxs9foah4UXuYfTLXQfsAebW'
# cryptomus_merchant_id = 'b493112a-350e-4c57-ad74-91b608a36af9'
# print(client(cryptomus_api_key, cryptomus_merchant_id, InvoiceInfo, order_id='3ccd202f', uuid=None))