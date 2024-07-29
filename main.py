from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from . import models, schemas, crud
from .database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount('/statics', StaticFiles(directory='statics'), name='static')

@app.get('/')
async def home(request: Request):
    return templates.TemplateResponse(request=request, name='index/index.html')

@app.get('/login/')
async def login(request: Request):
    return templates.TemplateResponse(request=request, name='login/index.html', context={'test': ''})

@app.post('/create_user/', response_model=schemas.User)
async def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(400, 'email already registred')
    r = crud.create_user(db, user)
    print(r)
    return r


