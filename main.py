from fastapi import FastAPI, Request, Depends, HTTPException, Cookie, Response, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from . import schemas, crud, private
from .database import SessionLocal
import jwt, uuid
from.auth import SECRET_KEY, REFRESH_SECRET_KEY, create_access_token, create_refresh_token
from .zarinPalAPI import SendInformation, InformationData

verification_codes = {}

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

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
            new_price = add_count.count * add_count.v2ray_config.price
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
            new_price = subtract.count * subtract.v2ray_config.price
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


async def iran_initialization_payment(db, user_id, action, amount, id_holder=None, currency='IRT'):
    try:
        payment_nstance = SendInformation(private.merchent_id)
        send_information: InformationData = await payment_nstance.execute(
            merchent_id=private.merchent_id, amount=amount, currency=currency, description=action,
            callback_url=private.callback_url
        )

        if not send_information: return False

        invoice = schemas.CreateIranInvoiceBeforPay(
            action=action, id_holder=id_holder, authority=send_information.authority, amount=amount, currency=currency,
            callback_url=private.callback_url, description=action, meta_data=None, is_final=False,
            fee_type=send_information.fee_type, fee=send_information.fee, owner_id=user_id
        )

        crud.create_iran_invoice_before_pay(db, invoice)
        return send_information

    except Exception as e:
        return False

def crypto_initialization_payment(price, user):
    currency = 'USD'
    lifetime = 3600
    order_id = uuid.uuid4().hex

    sqlite_manager.insert('Cryptomus', rows={'amount': str(dollar_price),
                                             'currency': currency,
                                             'lifetime': lifetime,
                                             'order_id': order_id,
                                             'chat_id': int(user["id"])})


    create_api = cryptomusApi.client(cryptomus_api_key, cryptomus_merchant_id, cryptomusApi.CreateInvoice,
                                     amount=str(dollar_price), currency=currency,
                                     order_id=order_id, lifetime=lifetime, additional_data=json.dumps(additional_data))

    if create_api:
        invoice_link = create_api[0].get('result', {}).get('url')
        if not invoice_link:
            raise ValueError(f'cryptomus url does not exist. result -> {create_api}')
    else:
        raise ValueError(f'cryptomus is empty. result -> {create_api}')


    return dollar_price, invoice_link, order_id

@app.post('/payment/')
async def payment( request: Request, payment_method: str = Form(...), db: Session = Depends(get_db)):
    try:
        user_id = jwt.decode(request.cookies.get("access_token"), SECRET_KEY, algorithms=["HS256"]).get('user_id')
        db_cart = crud.get_cart(db, user_id)
        price = await calculate_total_price(db_cart.v2ray_config_associations)

        if payment_method == 'iran_payment_getway':
            get_data = await iran_initialization_payment(
                db=db, user_id=user_id, action='cart_payment', amount=price, id_holder=db_cart.cart_id
            )
            if not get_data: return {'status': 'the invoice was not created'}
            return RedirectResponse(f'https://payment.zarinpal.com/pg/StartPay/{get_data.authority}')
        else:
            return {'status': 'soon'}

    except Exception as e:
        print(e)
        return {'status': 'error', 'reason': str(e)}
