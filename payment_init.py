import logging
import crud, private
import jwt, uuid, json, pytz, requests
from API.zarinPalAPI import SendInformation
from API.cryptomusAPI import CreateInvoice, InvoiceInfo
from API.convert_irt_to_usd import convert_irt_to_usd_by_teter
from utilities import SendRequest


async def create_invoice(database, user_id, action, amount, cart_id, gateway):
    try:
        amount_in_usd = 0
        if gateway == 'iran_payment_getway':
            currency = 'IRT'
            gateway_callback_url = private.iran_callback_url
            payment_nstance = SendInformation(private.zarinpal_merchent_id)
            create_zarinpal_invoice = await payment_nstance.execute(
                merchent_id=private.zarinpal_merchent_id, amount=amount, currency=currency, description=action,
                callback_url=gateway_callback_url
            )
            if not create_zarinpal_invoice: return False
            authority = create_zarinpal_invoice.authority
            invoice_link = f'https://payment.zarinpal.com/pg/StartPay/{authority}'

        elif gateway == 'crypto_payment_getway':
            currency = 'USD'
            authority = uuid.uuid4().hex
            amount_in_usd = str(convert_irt_to_usd_by_teter(amount))
            gateway_callback_url = private.cryptomus_callback_url
            class_instance = CreateInvoice(private.cryptomus_api_key, private.cryptomus_merchant_id)
            create_cryptomus_invoice = await class_instance.execute(amount=amount_in_usd, currency=currency, order_id=authority,
                                                                    lifetime=3600, url_callback=gateway_callback_url)
            invoice_link = create_cryptomus_invoice['result']['url']
        else:
            currency = 'IRT'
            authority, gateway_callback_url = uuid.uuid4().hex, None
            invoice_link = f'/pay_by_wallet/{authority}'

        crud.create_financial_report(
            database, 'spend', user_id, amount, action, cart_id, 'not paid',
            payment_getway=gateway,
            authority=authority,
            currency=currency,
            url_callback=gateway_callback_url,
            additional_data=json.dumps({'amount_in_usd': amount_in_usd})
        )

        return invoice_link

    except Exception as e:
        logging.error(f'error in create invoice:\n{e}')
        return


async def verify_iran_payment(authority: str, amount: int):
    url = 'https://payment.zarinpal.com/pg/v4/payment/verify.json'
    # return {'data': {'code': 100}}
    json_payload = {
        'merchant_id': private.zarinpal_merchent_id,
        'amount': amount,
        'authority': authority
    }
    make_request = SendRequest()
    response = await make_request.send_request('post', url, json_data=json_payload)

    return response

async def verify_cryptomus_payment(order_id: str, uuid_: str | None):
    check_invoic = await InvoiceInfo(private.cryptomus_api_key, private.cryptomus_merchant_id).execute(order_id, uuid_)

    if check_invoic:
        payment_status = check_invoic.get('result', {}).get('payment_status')
        if payment_status in ('paid', 'paid_over'): return check_invoic[0]

    # return False