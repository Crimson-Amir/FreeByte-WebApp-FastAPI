from fastapi import FastAPI, Request, Depends, HTTPException, Cookie, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from . import models, schemas, crud
from .database import SessionLocal, engine
# import string, random
# from .email_utils import send_email
import jwt
from.auth import SECRET_KEY, REFRESH_SECRET_KEY, create_access_token, create_refresh_token

models.Base.metadata.create_all(bind=engine)
verification_codes = {}

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount('/statics', StaticFiles(directory='statics'), name='static')

@app.get('/')
async def home(request: Request):
    return templates.TemplateResponse(request=request, name='index/sign_in.html')

@app.get('/sign-up/')
async def sign_up(request: Request):
    return templates.TemplateResponse(request=request, name='authentication/sign_in.html', context={'test': ''})


# @app.post('/register/')
# async def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
#     db_user = crud.get_user_by_email(db, user.email)
#     if db_user and db_user.active: raise HTTPException(400, 'email already registred.')
#     if not user.phone_number and not user.email: raise HTTPException(400, 'email or phone number is required.')
#
#     code = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
#     verification_codes[user.email] = code
#
#     email_body = f"Your verification code is: {code}"
#     await send_email(subject="Verify your email", recipient=user.email, body=email_body)
#
#     if not db_user.active: crud.create_user(db, user)
#
#     return {"message": "Verification code sent to your email"}

@app.post("/refresh-token")
def refresh_token(refresh_token_attr: str = Cookie(None)):
    if not refresh_token_attr:
        raise HTTPException(status_code=401, detail="Refresh token is missing")

    try:
        payload = jwt.decode(refresh_token_attr, REFRESH_SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        new_access_token = create_access_token(data={"sub": username})
        return {"access_token": new_access_token}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.middleware("http")
async def authenticate_request(request: Request, call_next):
    token = request.cookies.get("access_token")
    request.state.user = {"role": "guest"}

    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.state.user = payload
        except jwt.ExpiredSignatureError:
            get_refresh_token = request.cookies.get("refresh_token")
            if get_refresh_token:
                try:
                    payload = jwt.decode(get_refresh_token, REFRESH_SECRET_KEY, algorithms=["HS256"])
                    new_access_token = create_access_token(data={"sub": payload["sub"]})
                    response = await call_next(request)
                    response.set_cookie(key="access_token", value=new_access_token, httponly=True, secure=True, max_age=3600)
                    request.state.user = payload
                    return response
                except jwt.ExpiredSignatureError:
                    pass
                except jwt.InvalidTokenError:
                    pass
        except jwt.InvalidTokenError:
            pass

    response = await call_next(request)
    return response

@app.post('/sign-up/')
async def create_user(user: schemas.UserCreate, response: Response, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, user.email)
    if db_user: raise HTTPException(400, 'email already registred.')
    if not user.phone_number and not user.email: raise HTTPException(400, 'email or phone number is required.')
    create_user_db = crud.create_user(db, user)

    user_data = {"sub": create_user_db.email}

    access_token = create_access_token(data=user_data)
    cr_refresh_token = create_refresh_token(data=user_data)

    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, max_age=3600)
    response.set_cookie(key="refresh_token", value=cr_refresh_token, httponly=True, secure=True, max_age=604800)

    return create_user_db

@app.post('/create_product/', response_model=schemas.Product)
async def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    create_product_db = crud.create_product(db, product)
    return create_product_db
