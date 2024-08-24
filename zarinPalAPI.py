import asyncio
import aiohttp

class ZarinPal:
    def __init__(self, merchent_id: str):
        self._merchent_id = merchent_id

class SendRequest:
    @staticmethod
    async def send_request(method, url, params=None, json=None, data=None, header=None, session_header=None):
        async with aiohttp.ClientSession(headers=session_header) as session:
            async with session.request(method, url, params=params, json=json, data=data, headers=header) as response:
                print(await response.json())
                response.raise_for_status()
                return await response.json()

class InformationData:
    amount: int
    currency: str
    description: str
    callback_url: str
    metadata: str
    code: int
    authority: str
    fee_type: str
    fee: int

class SendInformation(ZarinPal):

    @staticmethod
    async def check_code(code):
        if code == 100: return True

    async def analysis_information_data(self, returned_jason, data):
        if await self.check_code(returned_jason.get('data').get("code", 101)):
            information_data_instance = InformationData()
            information_data_instance.authority = returned_jason.get('data').get('authority')
            information_data_instance.fee_type = returned_jason.get('data').get('fee_type')
            information_data_instance.fee = returned_jason.get('data').get('fee')
            information_data_instance.code = returned_jason.get('data').get('code')
            information_data_instance.amount = data.get('amount', '')
            information_data_instance.currency = data.get('currency', '')
            information_data_instance.description = data.get('description', '')
            information_data_instance.callback_url = data.get('callback_url', '')
            information_data_instance.metadata = data.get('metadata', '')

            return information_data_instance

    async def execute(self, **kwargs):
        url = 'https://payment.zarinpal.com/pg/v4/payment/request.json'
        make_request = SendRequest()
        kwargs.setdefault('merchant_id', self._merchent_id)
        response = await make_request.send_request('post', url, json=kwargs)
        if response:
            return await self.analysis_information_data(response, kwargs)
        raise ValueError('Response is empty!')

def create_invoice(merchent_id, **args):
    payment = SendInformation(merchent_id)
    return asyncio.run(payment.execute(**args))
