import sqlalchemy.exc
from fastapi import FastAPI, Request, Depends, HTTPException, Cookie, Response, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from . import schemas, crud, private, cryptomusApi, get_teter_price, api_clean, models
from .database import SessionLocal
import jwt, uuid, json, aiohttp, pytz, random, string, requests
from datetime import datetime, timedelta
from.auth import SECRET_KEY, REFRESH_SECRET_KEY, create_access_token, create_refresh_token
from .zarinPalAPI import SendInformation, InformationData
from urllib.parse import urlparse, parse_qs
from .private import ADMIN_CHAT_IDs, telegram_bot_token
from sqlalchemy import delete

verification_codes = {}
price_per_gb, price_per_day = 1500, 500


def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

class ConnectToServer:
    api_operation = api_clean.XuiApiClean(get_db)
    last_update = None

    def refresh_token(self):
        now = datetime.now()
        if self.last_update:
            if (self.last_update + timedelta(minutes=5)) < now:
                self.api_operation.refresh_connecion()
                self.last_update = now
        else:
            self.api_operation.refresh_connecion()
            self.last_update = now

connect_to_server_instance = ConnectToServer()

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount('/statics', StaticFiles(directory='statics'), name='static')

class TokenBlackList:
    def __init__(self): self.black_list = set()
    def add(self, token): self.black_list.add(token)
    def is_blacklisted(self, token): return token in self.black_list

token_black_list = TokenBlackList()

@app.post("/refresh-token")
def refresh_token(request: Request, response: Response, refresh_token_attr: str = Cookie(None)):
    if not refresh_token_attr:
        raise HTTPException(status_code=401, detail="Refresh token is missing")

    try:
        payload = jwt.decode(refresh_token_attr, REFRESH_SECRET_KEY, algorithms=["HS256"])
        email= payload.get("email"),
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        new_access_token = create_access_token(data={"email": email, "name": payload.get("name"), "user_id": payload.get("user_id")})
        request.state.user = payload
        response.set_cookie(key="access_token", value=new_access_token, httponly=True, secure=True, max_age=3600)
        return {"access_token": new_access_token}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.middleware("http")
async def authenticate_request(request: Request, call_next):
    exception_paths = ["/sign-up/"]

    if request.url.path in exception_paths:
        response = await call_next(request)
        return response

    token = request.cookies.get("access_token")
    request.state.user = None

    async def generate_new_token():
        get_refresh_token = request.cookies.get("refresh_token")
        if get_refresh_token:
            try:
                refresh_payload = jwt.decode(get_refresh_token, REFRESH_SECRET_KEY, algorithms=["HS256"])
                new_access_token = create_access_token(data={"email": refresh_payload.get("email"),
                                                             "name": refresh_payload.get("name"),
                                                             "user_id": refresh_payload.get("user_id")})
                request.state.user = new_access_token.encode()
                new_response = await call_next(request)
                new_response.set_cookie(key="access_token", value=new_access_token, httponly=True, secure=True, max_age=3600)
                return new_response

            except jwt.ExpiredSignatureError:
                return RedirectResponse('/sign-up/')

            except jwt.InvalidTokenError:
                return RedirectResponse('/sign-up/')

    if token and token not in token_black_list.black_list:
        try:
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.state.user = token.encode()
        except jwt.ExpiredSignatureError:
            response = await generate_new_token()
            if response: return response
        except jwt.InvalidTokenError:
            return RedirectResponse('/sign-up/')

    else:
        response = await generate_new_token()
        if response: return response

    response = await call_next(request)
    return response


async def decode_access_token(request, all_=False):
    if not request.state.user:
        return

    decode_data = jwt.decode(request.state.user, SECRET_KEY, algorithms=["HS256"])
    if not all_: return decode_data.get('user_id')
    return decode_data

@app.get('/')
async def root(): return RedirectResponse('/home')

@app.api_route('/home', methods=['POST', 'GET'])
async def home(request: Request):
    all_data = await decode_access_token(request, True)

    return templates.TemplateResponse(request=request, name='index/index.html', context={'user_data': all_data})

@app.get('/sign-up/')
async def sign_up(request: Request):
    return templates.TemplateResponse(request=request, name='authentication/sign_in.html')

@app.post('/sign-up/', response_model=schemas.User)
async def create_user(user: schemas.UserCreate, response: Response, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, user.email)
    if db_user: raise HTTPException(400, 'email already registred.')

    create_user_db = crud.create_user(db, user)
    crud.create_cart(db, create_user_db.user_id )

    user_data = {"email": create_user_db.email, "name": create_user_db.name, "user_id": create_user_db.user_id}

    access_token = create_access_token(data=user_data)
    cr_refresh_token = create_refresh_token(data=user_data)

    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, max_age=3600)
    response.set_cookie(key="refresh_token", value=cr_refresh_token, httponly=True, secure=True, max_age=2_592_000)

    return create_user_db


@app.api_route('/loggin', methods=['GET', 'POST'], response_model=schemas.User)
async def loggin(request: Request, response: Response, user: schemas.UserCreate = None, db: Session = Depends(get_db)):
    if request.method == 'GET':
        return templates.TemplateResponse(request=request, name='authentication/loggin.html')

    db_user = crud.get_user_by_email(db, user.email)
    if not db_user: raise HTTPException(400, 'email does not exist.')

    request_hashed_password = crud.hash_password_md5(user.password)
    if request_hashed_password != db_user.hashed_password: raise HTTPException(400, 'password is not correct.')

    user_data = {"email": db_user.email, "name": db_user.name, "user_id": db_user.user_id}

    access_token = create_access_token(data=user_data)
    cr_refresh_token = create_refresh_token(data=user_data)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, max_age=3600)
    response.set_cookie(key="refresh_token", value=cr_refresh_token, httponly=True, secure=True, max_age=2_592_000)

    return db_user

@app.post('/logout')
async def loggin(request: Request):
    token = request.cookies.get('access_token')
    redirect = RedirectResponse('/home/')
    if token:
        token_black_list.add(token)
        redirect.delete_cookie(key='access_token', httponly=True)
        redirect.delete_cookie(key="refresh_token", httponly=True)
    return redirect

async def calculate_total_price(v2ray_config_associations):
    try:
        return sum([config.v2ray_config.price * config.count for config in v2ray_config_associations])
    except Exception as e:
        print(e)


@app.get('/cart')
async def cart(request: Request, db: Session = Depends(get_db)):
    user_id = await decode_access_token(request)
    db_cart = crud.get_cart(db, user_id)
    list_len = len(db_cart.v2ray_config_associations)
    price = await calculate_total_price(db_cart.v2ray_config_associations)
    return templates.TemplateResponse(request=request, name='cart/cart.html',
                                      context={'db_cart': db_cart, 'list_len': list_len, 'price': price})


@app.post('/add_to_cart/')
async def add_to_cart(config: schemas.ClientConfigReq, request: Request, db: Session = Depends(get_db)):
    try:
        user_id = await decode_access_token(request)
        cart_id = crud.get_cart(db, user_id)
        check_in_cart = crud.is_config_available_in_cart(db, cart_id.cart_id, config.config_id)
        if check_in_cart:
            crud.add_config_count_in_cart(db, cart_id.cart_id, config.config_id)
        else:
            crud.add_to_cart(db, cart_id.cart_id, config.config_id)
        return {'status': 'ok'}
    except Exception as e:
        print(e)
        return {'status': 'error', 'reason': str(e)}

@app.post('/add_config_count/')
async def add_config_count(config: schemas.ClientConfigID, request: Request, db: Session = Depends(get_db)):
    try:
        user_id = await decode_access_token(request)
        cart_id = crud.get_cart(db, user_id)
        check_in_cart = crud.is_config_available_in_cart(db, cart_id.cart_id, config.config_id)
        if check_in_cart:
            add_count = crud.add_config_count_in_cart(db, cart_id.cart_id, config.config_id)
            new_price = await calculate_total_price(add_count.cart.v2ray_config_associations)
            return {'status': 'ok', 'new_price': new_price}
        return {'status': 'nok'}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}

@app.patch('/subtract_config_count/')
async def subtract_config_count(config: schemas.ClientConfigID, request: Request, db: Session = Depends(get_db)):
    try:
        user_id = await decode_access_token(request)
        cart_id = crud.get_cart(db, user_id)
        check_in_cart = crud.is_config_available_in_cart(db, cart_id.cart_id, config.config_id)
        if check_in_cart:
            subtract = crud.subtract_config_count_in_cart(db, cart_id.cart_id, config.config_id)
            new_price = await calculate_total_price(subtract.cart.v2ray_config_associations)
            return {'status': 'ok', 'new_price': new_price}
        return {'status': 'nok'}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}

@app.patch('/create-v2ray-config/')
async def create_v2ray_config(config: schemas.CreateConfigInDB, db: Session = Depends(get_db)):
    return crud.create_config(db, config)

@app.post('/create-product/')
async def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    return crud.create_product(db, product)

@app.delete('/remove_from_cart/{cart_id}/{config_id}')
async def remove_from_cart(cart_id: int, config_id: int, db: Session = Depends(get_db)):
    try:
        remove = crud.remove_from_cart(db, cart_id, config_id)
        new_price = await calculate_total_price(remove.cart.v2ray_config_associations)
        return {'status': 'ok', 'config_id': cart_id, 'new_item_count': len(remove.cart.v2ray_config_associations), 'new_price': new_price}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}


async def iran_initialization_payment(database, user_id, action, amount, id_holder=None, currency='IRT'):
    try:
        payment_nstance = SendInformation(private.zarinpal_merchent_id)
        send_information: InformationData = await payment_nstance.execute(
            merchent_id=private.zarinpal_merchent_id, amount=amount, currency=currency, description=action,
            callback_url=private.iran_callback_url
        )

        if not send_information: return False

        invoice = schemas.CreateIranInvoiceBeforPay(
            action=action, id_holder=id_holder, authority=send_information.authority, amount=amount, currency=currency,
            callback_url=private.iran_callback_url, description=action, meta_data=None, is_final=False,
            fee_type=send_information.fee_type, fee=send_information.fee, owner_id=user_id
        )

        crud.create_iran_invoice_before_pay(database, invoice)
        return send_information

    except Exception as e:
        print(e)
        return False

async def crypto_initialization_payment(database, user_id, amount, action, id_holder):
    currency = 'USD'
    lifetime = 3600
    dollar_price_now = get_teter_price.get_teter_price_in_rial()
    if dollar_price_now == 0:
        dollar_price_now = 60000

    amount = str(amount / dollar_price_now)
    order_id = uuid.uuid4().hex

    additional_data = json.dumps({
        'order_id': order_id,
        'user_id': user_id,
        'action': action,
        'id_holder': id_holder,
        'amount': amount
    })

    invoice = schemas.CreateCryptomusInvoiceBeforPay(
        amount=amount, action=action, id_holder=id_holder, currency=currency, lifetime=lifetime, order_id=order_id,
        callback_url=private.cryptomus_callback_url, is_payment_multiple=True, additional_data=additional_data,
        is_refresh=False, is_final=False, owner_id=user_id
    )

    crud.create_cryptomus_invoice_before_pay(database, invoice)

    home_url, my_product_url = f'{private.app_url}/home/', f'{private.app_url}/my_product/'

    class_instance = cryptomusApi.CreateInvoice(private.cryptomus_api_key, private.cryptomus_merchant_id)
    create_api = await class_instance.execute(amount=amount, currency=currency, order_id=order_id, lifetime=lifetime,
                                              additional_data=additional_data, url_success= my_product_url,
                                              url_return=home_url, url_callback=private.cryptomus_callback_url)

    if create_api:
        invoice_link = create_api['result']['url']
        return invoice_link

    raise ValueError(f'cryptomus result is empty. result: {create_api}')


@app.post('/payment/')
async def payment(request: Request, payment_method: str = Form(...), db: Session = Depends(get_db)):
    try:
        action = 'cart_payment'
        user_id = await decode_access_token(request)
        db_cart = crud.get_cart(db, user_id)
        amount = await calculate_total_price(db_cart.v2ray_config_associations)

        if payment_method == 'iran_payment_getway':
            get_data = await iran_initialization_payment(
                database=db, user_id=user_id, action=action, amount=amount, id_holder=db_cart.cart_id
            )
            if not get_data: return {'status': 'the invoice was not created'}
            return RedirectResponse(f'https://payment.zarinpal.com/pg/StartPay/{get_data.authority}')
        else:
            if amount < 10000:
                return {'error', 'crypto getway available for cart with amount than $0.20'}
            link = await crypto_initialization_payment(
                database=db, user_id=user_id, amount=amount, action=action, id_holder=db_cart.cart_id
            )
            if not link: return {'status': 'the invoice was not created'}
            return templates.TemplateResponse(request=request, name='cart/send_user_to_payment_getway.html', context={'link': link})

    except Exception as e:
        print(e)
        return {'status': 'error'}

class SendRequest:
    @staticmethod
    async def send_request(method, url, params=None, json_data=None, data=None, header=None, session_header=None):
        async with aiohttp.ClientSession(headers=session_header) as session:
            async with session.request(method, url, params=params, json=json_data, data=data, headers=header) as response:
                return await response.json()

async def verify_iran_payment(authority: str, amount: int):
    url = 'https://payment.zarinpal.com/pg/v4/payment/verify.json'
    json_payload = {
        'merchant_id': private.zarinpal_merchent_id,
        'amount': amount,
        'authority': authority
    }
    make_request = SendRequest()
    response = await make_request.send_request('post', url, json_data=json_payload)

    return response

async def verify_cryptomus_payment(order_id: str, uuid_: str | None):
    check_invoic = await cryptomusApi.InvoiceInfo(private.cryptomus_api_key, private.cryptomus_merchant_id).execute(order_id, uuid_)

    if check_invoic:
        payment_status = check_invoic.get('result', {}).get('payment_status')
        if payment_status in ('paid', 'paid_over'): return check_invoic[0]

    # return False


def second_to_ms(date, time_to_ms: bool = True):
    if time_to_ms:
        return int(date.timestamp() * 1000)
    else:
        seconds = date / 1000
        return datetime.fromtimestamp(seconds)

def traffic_to_gb(traffic, byte_to_gb:bool = True):
    if byte_to_gb:
        return traffic / (1024 ** 3)
    else:
        return int(traffic * (1024 ** 3))


def generate_random_string(length=5):
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string

async def report_status_to_admin(text , user_id):
    try:
        text = (f'{text}'
                f'\nUser Chat ID: {user_id}')

        telegram_bot_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
        requests.post(telegram_bot_url, data={'chat_id': ADMIN_CHAT_IDs[0], 'text': text})
    except Exception as e:
        print(f'Failed to send message to ADMIN {e}')

async def upgrade_service_in_server(service, database, user_id):
    connect_to_server_instance.refresh_token()

    inbound_id = service.inbound_id
    client_email = service.config_email
    get_server_domain = service.product.server_address
    traffic_db = service.traffic_gb
    period = service.period_day
    price = service.price
    now = datetime.now(pytz.timezone('Asia/Tehran'))

    ret_conf = connect_to_server_instance.api_operation.get_inbound(inbound_id, get_server_domain)
    client_list = json.loads(ret_conf['obj']['settings'])['clients']

    for client in client_list:
        if client['email'] == client_email:
            client_id = client['id']
            get_client_status = connect_to_server_instance.api_operation.get_client(client_email, get_server_domain)

            if get_client_status['obj']['enable']:
                tra = client['totalGB']
                traffic = int((traffic_db * (1024 ** 3)) + tra)
                expiry_timestamp = client['expiryTime']
                expiry_datetime = datetime.fromtimestamp(expiry_timestamp / 1000)
                new_expiry_datetime = expiry_datetime + timedelta(days=period)
                my_data = int(new_expiry_datetime.timestamp() * 1000)
            else:
                traffic = int(traffic_db * (1024 ** 3))
                my_data = now + timedelta(days=period)
                my_data = int(my_data.timestamp() * 1000)
                print(connect_to_server_instance.api_operation.reset_client_traffic(inbound_id, client_email, get_server_domain))

            data = {
                "id": inbound_id,
                "settings": "{{\"clients\":[{{\"id\":\"{0}\",\"alterId\":0,"
                            "\"email\":\"{1}\",\"limitIp\":0,\"totalGB\":{2},\"expiryTime\":{3},"
                            "\"enable\":true,\"tgId\":\"\",\"subId\":\"\"}}]}}".format(
                    client_id, client_email, traffic, my_data)}

            update_client = connect_to_server_instance.api_operation.update_client(client_id, data, get_server_domain)

            print(update_client)
            crud.renew_service_suuccessfull(database, service.config_id, traffic_to_gb(traffic), second_to_ms(my_data, False).day)

            await report_status_to_admin(
                text=f'🕸️ User Upgrade Service [WEB SERVER]'
                     f'\nService ID: {service.config_id}'
                     f'\nService Name: {client_email}'
                     f'\nTraffic: {traffic_db}GB'
                     f'\nPeriod: {period}day'
                     f'\nAmount: {price:,}',
                user_id=user_id)

            break


async def create_new_service_for_user(service, database, user_id):
    config_key = uuid.uuid4().hex
    connect_to_server_instance.refresh_token()

    period = service.period_day
    traffic_to_gigabyte = traffic_to_gb(service.traffic_gb, False)
    now_data_add_day = datetime.now(pytz.timezone('Asia/Tehran')) + timedelta(days=period)
    time_to_ms = second_to_ms(now_data_add_day)

    create_config_schema = schemas.CreateConfigInDB(
        plan_name=service.plan_name, config_key=config_key, config_email=None, traffic_gb=service.traffic_gb,
        period_day=service.period_day, price=service.price, active=True, product_id=service.product_id,
        owner_id=user_id, client_address=None, inbound_id=service.inbound_id, update=True
    )

    create_config_db = models.V2RayConfig(**create_config_schema.dict())
    database.add(create_config_db)
    database.flush()
    config_email = f'{create_config_db.config_id}_{generate_random_string()}'

    create_config_db.config_email = config_email

    data = {
        "id": service.inbound_id,
        "settings": "{{\"clients\":[{{\"id\":\"{0}\",\"alterId\":0,\"start_after_first_use\":true,"
                    "\"email\":\"{1}\",\"limitIp\":0,\"totalGB\":{2},\"expiryTime\":{3},"
                    "\"enable\":true,\"tgId\":\"\",\"subId\":\"\"}}]}}".format(
            config_key, config_email, traffic_to_gigabyte, time_to_ms)
    }
    connect_to_server_instance.api_operation.add_client(data, service.product.server_address)

    check_servise_available = connect_to_server_instance.api_operation.get_client(
        config_email, domain=service.product.server_address)

    if not check_servise_available['obj']:
        return

    client_address = connect_to_server_instance.api_operation.get_client_url(
        config_email, service.inbound_id, domain=service.product.iran_domain_address,
        server_domain=service.product.server_address, host=service.product.header_host, header_type=service.product.header_type)

    create_config_db.client_address = client_address
    database.add(create_config_db)

    await report_status_to_admin(
        text=f'🕸️ User Buy Service [WEB APP]'
             f'\nService ID: {service.config_id}'
             f'\nService Name: {service.plan_name}'
             f'\nTraffic: {service.traffic_gb}GB'
             f'\nPeriod: {service.period_day}day'
             f'\nAmount: {service.price:,}',
        user_id=user_id)

    return create_config_db


@app.get('/iran_recive_payment_result/')
async def recive_payment_result(Authority: str, Status: str, request: Request, db: Session = Depends(get_db)):
    if Status == 'OK':
        try:

            with db.begin():
                get_from_data = crud.get_payment_detail_by_authority(db, Authority)

                if not get_from_data:
                    return templates.TemplateResponse(request=request, name='cart/fail_pay.html',
                                                      context={
                                                          'error_reason': f'تراکنش مورد نظر در دیتابیس ما وجود ندارد. آیدی تراکنش {Authority}',
                                                          'error_code': 403})
                user_id: int = get_from_data.owner_id
                get_cart = crud.get_cart(db, user_id)

                amount = get_from_data.amount
                cart_id: int = get_from_data.id_holder

                response = await verify_iran_payment(Authority, amount)
                response = {'data': {"code": 100, 'ref_id': 214214214}}

                if response.get('data', {}).get('code', 100) == 100:

                    for service in get_cart.v2ray_config_associations:
                        if service.v2ray_config.update:
                            await upgrade_service_in_server(service.v2ray_config, db, user_id)

                        service_count = service.count

                        for _ in range(service_count):
                            create = await create_new_service_for_user(service.v2ray_config, db, user_id)
                            if not create:
                                raise ValueError('config is not available in server')

                    db.query(models.CartV2RayConfigAssociation).filter(models.CartV2RayConfigAssociation.cart_id == cart_id).delete()
                    return RedirectResponse('/dashboard/?payment_status=1')

        except Exception as e:

            db.rollback()
            try:
                get_cart = crud.get_cart(db, user_id)
                price = await calculate_total_price(get_cart.v2ray_config_associations)
                crud.add_credit_to_user(db, user_id, price)
            except NameError:
                price = 0

            await report_status_to_admin(
                text=f'🕸️ User Service Buy Faild And Return Credit To wallet [WEB APP ZarinPal]'
                     f'\nAuthority: {Authority}'
                     f'\nError: {type(e)}\n{str(e)}',
                user_id=user_id)
            return RedirectResponse('/dashboard/?payment_status=2')


@app.post('/crypto_recive_payment_result/')
async def crypto_recive_payment_result(data: schemas.CryptomusPaymentWebhook, db: Session = Depends(get_db)):

    if data.status in ['paid', 'paid_over']:

        with db.begin():

            get_from_db = crud.get_crypto_payment_detail_by_order_id(db, data.order_id)
            print(get_from_db.owner_id)
            if not get_from_db: return

            user_id: int = get_from_db.owner_id
            get_cart = crud.get_cart(db, user_id)

            print(get_cart.cart_id)

        try:
            cart_id: int = get_from_db.id_holder
            response = await verify_cryptomus_payment(get_from_db.order_id, None)

            if response:
                # ref_id = response.get('data').get('ref_id')

                db.query(models.CartV2RayConfigAssociation).filter(models.CartV2RayConfigAssociation.cart_id == cart_id).delete()

                for service in get_cart.v2ray_config_associations:
                    print(service.v2ray_config.plan_name)
                    if service.v2ray_config.update:
                        await upgrade_service_in_server(service.v2ray_config, db, user_id)

                    service_count = service.count

                    for _ in range(service_count):
                        create = await create_new_service_for_user(service.v2ray_config, db, user_id)
                        if not create: raise ValueError('config is not available in server')

                db.query(models.CartV2RayConfigAssociation).filter(models.CartV2RayConfigAssociation.cart_id == cart_id).delete()
                return {'ok': 'ok'}

        except Exception as e:
            db.rollback()
            price = await calculate_total_price(get_cart.v2ray_config_associations)
            crud.add_credit_to_user(db, user_id, price)
            await report_status_to_admin(
                text=f'🕸️ User Service Buy Faild And Return Credit To wallet [WEB APP Cryptomus]'
                     f'\ndata: \n{data}'
                     f'\nError: {type(e)}\n{str(e)}',
                user_id=user_id)

            return {'ok': 'nok'}


async def get_server_details(all_services):
    if len(all_services) <= 3:
        final_result = dict()
        connect_to_server_instance.refresh_token()
        for service in all_services:
            print(service.config_email)
            get_service_detail = connect_to_server_instance.api_operation.get_client(
                service.config_email,
                service.product.server_address
            )

            if get_service_detail.get('success', False):
                obj = get_service_detail.get('obj', {})
                if not obj:
                    final_result[service.config_email] = {'usage_percent': 0, 'left_day': 0, 'left_traffic': 0, 'error': 'config is not availabale in server'}
                    continue

                final_result[obj.get('email')] = obj
                final_result[obj.get('email')]['usage_percent'] = int(((obj.get('up', 0) + obj.get('down', 0)) / obj.get('total', 1)) * 100)
                final_result[obj.get('email')]['left_day'] = max((second_to_ms(obj.get('expiryTime'), False) - datetime.now(pytz.timezone('Asia/Tehran')).replace(tzinfo=None)).days, 0)
                final_result[obj.get('email')]['left_traffic'] = round(traffic_to_gb(obj.get('total', 0) - (obj.get('up', 0) + obj.get('down', 1)), True), 2)


        return final_result
    return {}

@app.get('/dashboard/')
async def dashboard(request: Request, payment_status: int = None, db: Session = Depends(get_db)):
    user_id = await decode_access_token(request)
    all_services = crud.get_user_configs(db, user_id)
    all_data = await decode_access_token(request, True)

    return templates.TemplateResponse(request=request, name='dashboard/my_product.html', context={
        'user_data': all_data,
        'all_services': all_services,
        'service_detail_from_server': await get_server_details(all_services),
        'payment_status': payment_status
    })

@app.get('/dashboard/service_detail/{service_id}')
async def dashboard(request: Request, service_id: int, db: Session = Depends(get_db)):
    user_id = await decode_access_token(request)
    get_service_detail = [crud.get_config(db, service_id, user_id)]
    all_data = await decode_access_token(request, True)

    return templates.TemplateResponse(request=request, name='dashboard/my_product.html', context={
        'user_data': all_data,
        'service_detail_from_server': await get_server_details(get_service_detail),
        'all_services': get_service_detail
    })


async def remove_service_from_db(service):
    connect_to_server_instance.refresh_token()
    connect_to_server_instance.api_operation.del_client(service.inbound_id, service.config_key, service.product.server_address)


@app.delete('/remove-user-service/{config_id}')
async def remove_user_service(config_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = await decode_access_token(request)
    try:
        service = crud.remove_config(db, config_id, user_id)
        await remove_service_from_db(service)
        return {'status': 'ok'}
    except Exception as e:
        return HTTPException(500, {'error': e})


@app.patch('/add-service-to-cart-for-renew/')
async def add_service_to_cart_for_renew(data: schemas.add_service_to_cart_for_renew, request: Request, db: Session = Depends(get_db)):
    try:
        user_id = await decode_access_token(request)
        cart_id = crud.get_cart(db, user_id)
        check_in_cart = crud.is_config_available_in_cart(db, cart_id.cart_id, data.config_id)
        if check_in_cart:
            return {'status': 'nok', 'message': 'service already in cart'}

        # crud.make_service_upgradable(db, data.config_id)
        crud.add_to_cart(db, cart_id.cart_id, data.config_id)

        return {'status': 'ok'}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}


@app.post('/add_custom_service_to_cart/')
async def add_custom_service_to_cart(config: schemas.ClientConfigReqCustom, request: Request, db: Session = Depends(get_db)):
    try:
        custom_service_inbound_id, custom_service_product_id = 1, 1
        calcuate_price = (price_per_gb * config.traffic) + (price_per_day * config.period)
        user_id = await decode_access_token(request)
        cart_id = crud.get_cart(db, user_id)
        check_same_config = crud.does_same_config_available_in_cart(db, config.period, config.traffic)

        if not check_same_config:

            create_config_schema = schemas.CreateConfigInDB(
                plan_name='دلخواه', config_key=None, config_email=None, traffic_gb=config.traffic,
                period_day=config.period, price=calcuate_price, active=False, product_id=custom_service_product_id,
                owner_id=user_id, client_address=None, inbound_id=custom_service_inbound_id
            )
            service = crud.create_config(db, create_config_schema)
            crud.add_to_cart(db, cart_id.cart_id, service.config_id)

        else:
            check_in_cart = crud.is_config_available_in_cart(db, cart_id.cart_id, check_same_config.config_id)
            if check_in_cart:
                crud.add_config_count_in_cart(db, cart_id.cart_id, check_same_config.config_id)
            else:
                crud.add_to_cart(db, cart_id.cart_id, check_same_config.config_id)

        return {'status': 'ok'}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}


@app.post('/upgrade-foreign-service/')
async def upgrade_foreign_service(config: schemas.UpgradeCustomService, request: Request, db: Session = Depends(get_db)):
    try:
        with db.begin():
            user_id = await decode_access_token(request)
            cart_id = crud.get_cart(db, user_id)

            traffic, period = config.traffic, config.period
            print(traffic, period)
            calcuate_price = (price_per_gb * config.traffic) + (price_per_day * config.period)
            parsed_url = urlparse(config.config_address)

            key = parsed_url.username
            host = parsed_url.hostname
            country = config.country
            query_params = parse_qs(parsed_url.query)
            email = str(parsed_url.fragment).split(' ')[-1]

            encryption = query_params.get('encryption', [None])[0]
            security = query_params.get('security', [None])[0]
            network_type = query_params.get('type', [None])[0]
            header_type = query_params.get('headerType', [None])[0]
            header_host = query_params.get('host', [None])[0]


            create_schema = schemas.CheckAnyProductMatch(
                country=country, iran_domain_address=host, encryption=encryption, security=security,
                network_type=network_type, header_type=header_type, header_host=header_host
            )

            match_product = crud.check_any_product_match(db, create_schema)

            if not match_product:
                return {'status': 'notExist', 'message': 'there is no match product'}

            get_service_detail = connect_to_server_instance.api_operation.get_client(
                email,
                match_product.server_address
            )
            if get_service_detail.get('success', False):
                obj = get_service_detail.get('obj', {})
                if obj:
                    inbound_id = obj.get('inboundId')
                    if inbound_id:
                        service = crud.get_config_by_email(db, email, user_id)
                        if service:
                            crud.update_config_traffic_and_period(db, service.config_id, traffic, period, calcuate_price)
                        else:
                            create_config_schema = schemas.CreateConfigInDB(
                                plan_name='خارجی', config_key=key, config_email=email, traffic_gb=traffic,
                                period_day=period, price=calcuate_price, active=False, product_id=match_product.product_id,
                                owner_id=user_id, client_address=config.config_address, inbound_id=inbound_id, update=True
                            )
                            service = crud.create_config(db, create_config_schema, commit=False)
                            db.flush()

                        crud.add_to_cart(db, cart_id.cart_id, service.config_id, commit=False)

                        return {'status': 'ok'}

    except sqlalchemy.exc.IntegrityError:
        return {'status': 'alreadyExist'}

    except Exception as e:
        return {'status': 'error', 'reason': str(e)}