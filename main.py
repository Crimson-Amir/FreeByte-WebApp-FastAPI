from fastapi import FastAPI, Request, Depends, HTTPException, Cookie, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from . import models, schemas, crud
from .database import SessionLocal, engine
import jwt
from.auth import SECRET_KEY, REFRESH_SECRET_KEY, create_access_token, create_refresh_token

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

@app.get('/cart')
async def cart(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    user_id = payload.get('user_id')
    db_cart = crud.get_cart(db, user_id)
    list_len = len(db_cart.v2ray_configs)
    price = sum([config.price for config in db_cart.v2ray_configs])
    return templates.TemplateResponse(request=request, name='cart/cart.html', context={'db_cart': db_cart, 'list_len': list_len, 'price': price})


@app.post('/add_to_cart/')
async def add_to_cart(config: schemas.ClientConfigReq, request: Request, db: Session = Depends(get_db)):
    try:
        user_id = jwt.decode(request.cookies.get("access_token"), SECRET_KEY, algorithms=["HS256"]).get('user_id')
        cart_id = crud.get_cart(db, user_id)
        crud.add_to_cart(db, cart_id.cart_id, config.config_id)
        return {'status': 'ok'}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}


@app.post('/create-v2ray-config/')
async def create_v2ray_config(config: schemas.CreateConfigInDB, db: Session = Depends(get_db)):
    return crud.create_config(db, config)


@app.post('/create-product/')
async def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    return crud.create_product(db, product)


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
