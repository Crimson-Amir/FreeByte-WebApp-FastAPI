import random

from fastapi import FastAPI, Request, Depends, HTTPException, Cookie, Response, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from . import schemas, crud, private, cryptomusApi, get_teter_price, api_clean, models
from .database import SessionLocal
import jwt, uuid, json, aiohttp, pytz
from datetime import datetime, timedelta
from.auth import SECRET_KEY, REFRESH_SECRET_KEY, create_access_token, create_refresh_token
from .zarinPalAPI import SendInformation, InformationData

verification_codes = {}

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
    request.state.user = {"role": "guest"}

    async def generate_new_token():
        get_refresh_token = request.cookies.get("refresh_token")
        if get_refresh_token:
            try:
                refresh_payload = jwt.decode(get_refresh_token, REFRESH_SECRET_KEY, algorithms=["HS256"])
                new_access_token = create_access_token(data={"email": refresh_payload.get("email"),
                                                             "name": refresh_payload.get("name"),
                                                             "user_id": refresh_payload.get("user_id")})
                request.state.user = refresh_payload
                new_response = await call_next(request)
                new_response.set_cookie(key="access_token", value=new_access_token, httponly=True, secure=True, max_age=3600)
                return new_response
            except jwt.ExpiredSignatureError:
                return RedirectResponse('/sign-up/')
            except jwt.InvalidTokenError:
                return RedirectResponse('/sign-up/')

    if token and token not in token_black_list.black_list:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.state.user = payload
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

@app.api_route('/home', methods=['POST', 'GET'])
async def home(request: Request):
    return templates.TemplateResponse(request=request, name='index/index.html')

@app.get('/')
async def root(): return RedirectResponse('/home')

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
    token = request.cookies.get("access_token")
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    user_id = payload.get('user_id')
    db_cart = crud.get_cart(db, user_id)
    list_len = len(db_cart.v2ray_config_associations)
    price = await calculate_total_price(db_cart.v2ray_config_associations)
    return templates.TemplateResponse(request=request, name='cart/cart.html',
                                      context={'db_cart': db_cart, 'list_len': list_len, 'price': price})


@app.post('/add_to_cart/')
async def add_to_cart(config: schemas.ClientConfigReq, request: Request, db: Session = Depends(get_db)):
    try:
        user_id = jwt.decode(request.cookies.get("access_token"), SECRET_KEY, algorithms=["HS256"]).get('user_id')
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
        user_id = jwt.decode(request.cookies.get("access_token"), SECRET_KEY, algorithms=["HS256"]).get('user_id')
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
        user_id = jwt.decode(request.cookies.get("access_token"), SECRET_KEY, algorithms=["HS256"]).get('user_id')
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
async def payment( request: Request, payment_method: str = Form(...), db: Session = Depends(get_db)):
    try:
        action = 'cart_payment'
        user_id = jwt.decode(request.cookies.get("access_token"), SECRET_KEY, algorithms=["HS256"]).get('user_id')
        db_cart = crud.get_cart(db, user_id)
        amount = await calculate_total_price(db_cart.v2ray_config_associations)

        if payment_method == 'iran_payment_getway':
            get_data = await iran_initialization_payment(
                database=db, user_id=user_id, action=action, amount=amount, id_holder=db_cart.cart_id
            )
            if not get_data: return {'status': 'the invoice was not created'}
            return RedirectResponse(f'https://payment.zarinpal.com/pg/StartPay/{get_data.authority}')
        else:
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
    async def send_request(method, url, params=None, json=None, data=None, header=None, session_header=None):
        async with aiohttp.ClientSession(headers=session_header) as session:
            async with session.request(method, url, params=params, json=json, data=data, headers=header) as response:
                return await response.json()

async def verify_iran_payment(authority: str, amount: int):
    url = 'https://payment.zarinpal.com/pg/v4/payment/verify.json'
    json_payload = {
        'merchant_id': private.zarinpal_merchent_id,
        'amount': amount,
        'authority': authority
    }
    make_request = SendRequest()
    response = await make_request.send_request('post', url, json=json_payload)

    return response

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

def create_new_service_for_user(service, database, ref_id, user_id):
    config_key, config_email = uuid.uuid4().hex, f'{random.randint(1, 1000000)}_{ref_id}'
    connect_to_server_instance.refresh_token()

    period = service.period_day
    traffic_to_gigabyte = traffic_to_gb(service.traffic_gb, False)
    now_data_add_day = datetime.now(pytz.timezone('Asia/Tehran')) + timedelta(days=period)
    time_to_ms = second_to_ms(now_data_add_day)

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

    create_config_schema = schemas.CreateConfigInDB(
        plan_name=service.plan_name, config_key=config_key, config_email=config_email, traffic_gb=service.traffic_gb,
        period_day=service.period_day, price=service.price, active=True, product_id=service.product_id,
        owner_id=user_id, client_address=client_address, inbound_id=service.inbound_id
    )

    create_config_db = models.V2RayConfig(**create_config_schema.dict())
    database.add(create_config_db)

    return create_config_db


@app.get('/iran_recive_payment_result/')
async def recive_payment_result(Authority: str, Status: str, request: Request, db: Session = Depends(get_db)):

    if Status == 'OK':
        try:
            with db.begin():

                get_from_data = crud.get_payment_detail_by_authority(db, Authority)

                if not get_from_data:
                    return templates.TemplateResponse(request=request, name='cart/fail_pay.html',
                                                      context={'error_reason': f'تراکنش مورد نظر در دیتابیس ما وجود ندارد. آیدی تراکنش {Authority}', 'error_code': 403})

                amount, payment_action = get_from_data.amount, get_from_data.action
                user_id: int = get_from_data.owner_id
                cart_id: int = get_from_data.id_holder

                # response = await verify_iran_payment(Authority, amount)
                response = {'data': {"code": 100, 'ref_id': 214214214}}

                if response.get('data', {}).get('code', 101) == 100:
                    ref_id = response.get('data').get('ref_id')
                    get_cart = crud.get_cart(db, user_id)


                    cart_item = db.query(models.CartV2RayConfigAssociation).filter(
                        models.CartV2RayConfigAssociation.cart_id == cart_id).first()

                    if cart_item:
                        db.delete(cart_item)

                    for service in get_cart.v2ray_config_associations:
                        if service.v2ray_config.update:
                            continue

                        service_count = service.count
                        print(service_count)

                        for _ in range(service_count):
                            create = create_new_service_for_user(service.v2ray_config, db, ref_id, user_id)
                            if not create: raise ValueError('config is not available in server')

                    message = 'You Pay was successfull'
                    return templates.TemplateResponse(request=request, name='dashboard/my_product.html', context={'message': message})

        except Exception as e:
            db.rollback()
            price = await calculate_total_price(get_cart.v2ray_config_associations)
            crud.add_credit_to_user(db, user_id, price)
            message = 'You Pay was Failed'
            raise e
            return templates.TemplateResponse(request=request, name='dashboard/my_product.html', context={'message': message})


@app.get('/dashboard/')
async def dashboard(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request=request, name='dashboard/my_product.html')
