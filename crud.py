from sqlalchemy.orm import Session
from sqlalchemy import update, insert, delete
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

def add_credit_to_user(db: Session, user_id: int, credit: int):
    add_credit = (
        update(models.User)
        .where(models.User.user_id == user_id)
        .values(credit=models.User.credit + credit)
        .returning(models.User)
    )
    result = db.execute(add_credit)
    db.commit()

    return result.scalar()

def get_all_server(db: Session):
    return db.query(models.Product).distinct().all()

def get_config(db: Session, config_id: int):
    return db.query(models.V2RayConfig).where(models.V2RayConfig.config_id == config_id).first()

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
    add_relation = insert(models.CartV2RayConfigAssociation).values(cart_id=cart_id, config_id=config_id)
    db.execute(add_relation)
    db.commit()
    return add_relation


def make_service_upgradable(db: Session, config_id: int):
    add_relation = (
        update(models.V2RayConfig)
        .where(models.V2RayConfig.config_id == config_id)
        .values(update=True)
        .returning(models.V2RayConfig)
    )
    result = db.execute(add_relation)
    db.commit()
    return result.scalar()

def add_config_count_in_cart(db: Session, cart_id: int, config_id: int):
    add_relation = (
        update(models.CartV2RayConfigAssociation)
        .where(models.CartV2RayConfigAssociation.cart_id == cart_id)
        .where(models.CartV2RayConfigAssociation.config_id == config_id)
        .values(count=models.CartV2RayConfigAssociation.count + 1)
        .returning(models.CartV2RayConfigAssociation)
    )
    result = db.execute(add_relation)
    db.commit()

    return result.scalar()

def subtract_config_count_in_cart(db: Session, cart_id: int, config_id: int):
    update_stmt = (
        update(models.CartV2RayConfigAssociation)
        .where(models.CartV2RayConfigAssociation.cart_id == cart_id)
        .where(models.CartV2RayConfigAssociation.config_id == config_id)
        .where(models.CartV2RayConfigAssociation.count > 1)
        .values(count=models.CartV2RayConfigAssociation.count - 1)
        .returning(models.CartV2RayConfigAssociation)
    )

    result = db.execute(update_stmt)
    db.commit()
    return result.scalar()

def remove_from_cart(db: Session, cart_id: int, config_id: int):
    remove_relation = (delete(models.CartV2RayConfigAssociation)
                       .where(models.CartV2RayConfigAssociation.cart_id == cart_id)
                       .where(models.CartV2RayConfigAssociation.config_id == config_id)
                       .returning(models.CartV2RayConfigAssociation))

    execute = db.execute(remove_relation)
    db.commit()
    result = execute.scalar()
    return result


def get_product(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Product).offset(skip).limit(limit).all()

def get_payment_detail_by_authority(db: Session, authority: str):
    return db.query(models.IranPaymentGewayInvoice).filter(models.IranPaymentGewayInvoice.authority == authority).first()

def get_cart(db: Session, user_id: int):
    return db.query(models.Cart).filter(user_id == models.Cart.owner_id).first()

def get_user_configs(db: Session, user_id: int):
    return db.query(models.V2RayConfig).filter(user_id == models.V2RayConfig.owner_id).all()

def clear_cart(db: Session, cart_id: int):
    clear_cart_db = delete(models.CartV2RayConfigAssociation).where(models.CartV2RayConfigAssociation.cart_id == cart_id)
    execute = db.execute(clear_cart_db)
    db.commit()
    result = execute.scalar()
    return result

def is_config_available_in_cart(db: Session, cart_id: int, config_id: int):
    return (db.query(models.CartV2RayConfigAssociation)
            .filter(models.CartV2RayConfigAssociation.cart_id == cart_id)
            .filter(models.CartV2RayConfigAssociation.config_id == config_id)
            .first())


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

def remove_config(db: Session, config_id: int, owner_id: int):
    remove_config_db = (delete(models.V2RayConfig)
                        .where(models.V2RayConfig.config_id == config_id)
                        .where(models.V2RayConfig.owner_id == owner_id)
                        .returning(models.V2RayConfig))
    execute = db.execute(remove_config_db)
    db.commit()
    result = execute.scalar()
    return result

def create_iran_invoice_before_pay(db: Session, invoice: schemas.CreateIranInvoiceBeforPay):
    db_invoice = models.IranPaymentGewayInvoice(**invoice.dict())
    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)
    return db_invoice

def create_cryptomus_invoice_before_pay(db: Session, invoice: schemas.CreateCryptomusInvoiceBeforPay):
    db_invoice = models.CryptomusPaymentGewayInvoice(**invoice.dict())
    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)
    return db_invoice