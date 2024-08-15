from sqlalchemy.orm import Session
from sqlalchemy import update
from hashlib import md5
from . import models, schemas

def hash_password_md5(password: str) -> str:
    password_bytes = password.encode()
    md5_hash = md5()
    md5_hash.update(password_bytes)
    return md5_hash.hexdigest()

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.user_id == user_id).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()


def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = hash_password_md5(user.password)
    db_user = models.User(name=user.name, email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_cart(db: Session, user_id: int):
    db_cart = models.Cart(owner_id=user_id)
    db.add(db_cart)
    db.commit()
    db.refresh(db_cart)
    return db_cart

def add_to_cart(db: Session, cart_id: int, config_id: int):
    add_relation = models.cart_v2ray_config_association.insert().values(cart_id=cart_id, config_id=config_id)
    db.execute(add_relation)
    db.commit()
    return add_relation

def get_product(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Product).offset(skip).limit(limit).all()

def get_cart(db: Session, user_id: int):
    return db.query(models.Cart).filter(user_id == models.Cart.owner_id).first()


def create_product(db: Session, item: schemas.ProductCreate):
    db_item = models.Product(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def create_config(db: Session, config: schemas.CreateConfigInDB):
    db_config = models.V2RayConfig(**config.dict())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config