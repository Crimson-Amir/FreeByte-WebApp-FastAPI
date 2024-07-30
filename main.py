from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from . import models, schemas, crud
from .database import SessionLocal, engine
import string, random
from email_utils import send_email

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


@app.post('/register/')
async def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, user.email)
    if db_user and db_user.active: raise HTTPException(400, 'email already registred.')
    if not user.phone_number and not user.email: raise HTTPException(400, 'email or phone number is required.')

    code = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    verification_codes[user.email] = code

    email_body = f"Your verification code is: {code}"
    await send_email(subject="Verify your email", recipient=user.email, body=email_body)

    if not db_user.active: crud.create_user(db, user)

    return {"message": "Verification code sent to your email"}


@app.post('/sign-up/')
async def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, user.email)
    if db_user: raise HTTPException(400, 'email already registred.')
    if not user.phone_number and not user.email: raise HTTPException(400, 'email or phone number is required.')
    create_user_db = crud.create_user(db, user)
    return create_user_db

@app.post('/create_product/', response_model=schemas.Product)
async def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    create_product_db = crud.create_product(db, product)
    return create_product_db
