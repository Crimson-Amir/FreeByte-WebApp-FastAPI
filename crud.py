from sqlalchemy.orm import Session
from sqlalchemy import update, insert, delete
from hashlib import md5
import models, schemas

def hash_password_md5(password: str) -> str:
    password_bytes = password.encode()
    md5_hash = md5()
    md5_hash.update(password_bytes)
    return md5_hash.hexdigest()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


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


def reduce_credit_from_user(db: Session, user_id: int, credit: int):
    reduce_credit = (
        update(models.User)
        .where(models.User.user_id == user_id)
        .values(credit=models.User.credit - credit)
        .returning(models.User)
    )
    result = db.execute(reduce_credit)
    db.commit()

    return result.scalar()

def get_purchase(db: Session, purchase_id: int, user_id: int):
    return (db.query(models.Purchase)
            .where(models.Purchase.purchase_id == purchase_id)
            .where(models.Purchase.owner_id == user_id)
            .all())

def get_all_main_servers(db: Session):
    return (db.query(models.MainServer)
            .where(models.MainServer.active == True)
            .all())

def get_purchase_by_username(db: Session, username: str):
    return (db.query(models.Purchase)
            .where(models.Purchase.username == username)
            .first())

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

def add_to_cart(db: Session, cart_id: int, purchase_id: int, commit=True):
    add_relation = insert(models.CartPurchaseAssociation).values(cart_id=cart_id, purchase_id=purchase_id)
    db.execute(add_relation)
    if commit: db.commit()
    return add_relation


def update_config_traffic_and_period(db: Session, purchase_id: int, traffic: int, period: int, price: int):
    update_stmt = (
        update(models.Purchase)
        .where(models.Purchase.purchase_id == purchase_id)
        .values(traffic=traffic)
        .values(period=period)
        .values(price=price)
    )
    db.execute(update_stmt)


def add_config_count_in_cart(db: Session, cart_id: int, purchase_id: int):
    add_relation = (
        update(models.CartPurchaseAssociation)
        .where(models.CartPurchaseAssociation.cart_id == cart_id)
        .where(models.CartPurchaseAssociation.purchase_id == purchase_id)
        .values(count=models.CartPurchaseAssociation.count + 1)
        .returning(models.CartPurchaseAssociation)
    )
    result = db.execute(add_relation)
    db.commit()

    return result.scalar()

def subtract_config_count_in_cart(db: Session, cart_id: int, purchase_id: int):
    update_stmt = (
        update(models.CartPurchaseAssociation)
        .where(models.CartPurchaseAssociation.cart_id == cart_id)
        .where(models.CartPurchaseAssociation.purchase_id == purchase_id)
        .where(models.CartPurchaseAssociation.count > 1)
        .values(count=models.CartPurchaseAssociation.count - 1)
        .returning(models.CartPurchaseAssociation)
    )

    result = db.execute(update_stmt)
    db.commit()
    return result.scalar()

def remove_from_cart(db: Session, cart_id: int, purchase_id: int):
    remove_relation = (delete(models.CartPurchaseAssociation)
                       .where(models.CartPurchaseAssociation.cart_id == cart_id)
                       .where(models.CartPurchaseAssociation.purchase_id == purchase_id)
                       .returning(models.CartPurchaseAssociation))

    execute = db.execute(remove_relation)
    db.commit()
    result = execute.scalar()
    return result


def get_product(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Product).offset(skip).limit(limit).all()

def get_first_product(db: Session):
    return db.query(models.Product).first()


def get_payment_detail_by_authority(db: Session, authority: str):
    return db.query(models.FinancialReport).filter(models.FinancialReport.authority == authority).first()

def get_cart(db: Session, user_id: int):
    return db.query(models.Cart).filter(user_id == models.Cart.owner_id).first()

def get_user_purchases(db: Session, user_id: int):
    return (db.query(models.Purchase)
            .filter(user_id == models.Purchase.owner_id)
            .filter(models.Purchase.active == True)
            .all())

def is_config_available_in_cart(db: Session, cart_id: int, purchase_id: int):
    return (db.query(models.CartPurchaseAssociation)
            .filter(models.CartPurchaseAssociation.cart_id == cart_id)
            .filter(models.CartPurchaseAssociation.purchase_id == purchase_id)
            .first())

def does_same_config_available_in_cart(db: Session, period: int, traffic: int):
    return (db.query(models.Purchase)
            .filter(models.Purchase.traffic == traffic)
            .filter(models.Purchase.period == period)
            .filter(models.Purchase.active == False)
            .first())

def check_any_purchase_match(db: Session, username: str):
    query = db.query(models.Purchase).filter(models.Purchase.username == username).first()
    return query


def create_product(db: Session, item: schemas.ProductCreate):
    db_item = models.Product(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def create_config(db: Session, config: schemas.CreateConfigInDB, commit=True):
    db_config = models.Purchase(**config.dict())
    db.add(db_config)
    if commit:
        db.commit()
        db.refresh(db_config)
    return db_config

def remove_purchase(db: Session, purchase_id: int, owner_id: int):
    remove_config_db = (delete(models.Purchase)
                        .where(models.Purchase.purchase_id == purchase_id)
                        .where(models.Purchase.owner_id == owner_id)
                        .returning(models.Purchase))
    execute = db.execute(remove_config_db)
    db.commit()
    result = execute.scalar()
    return result


def create_financial_report(db: Session, operation, user_id, amount, action, cart_id, payment_status, **kwargs):
    financial = models.FinancialReport(
        operation=operation,
        amount=amount,
        owner_id=user_id,
        action=action,
        id_holder=cart_id,
        payment_status=payment_status,
        **kwargs
    )

    db.add(financial)
    db.commit()
    return financial


def update_purchase(db, purchase_id:int, **kwargs):
    stmt = (
        update(models.Purchase)
        .where(models.Purchase.purchase_id == purchase_id)
        .values(
            **kwargs
        ).returning(models.Purchase)
    )
    result = db.execute(stmt)
    updated_purchase_id = result.scalar()
    return updated_purchase_id

def create_purchase(session, product_id, user_id, traffic, period, **kwargs):
    purchase = models.Purchase(
        product_id=product_id,
        owner_id=user_id,
        traffic=int(traffic),
        period=int(period),
        **kwargs
    )
    session.add(purchase)
    session.flush()
    return purchase


def update_financial_report_status(session, financial_id: int, new_status):
    stmt = (
        update(models.FinancialReport)
        .where(models.FinancialReport.financial_id == financial_id)
        .values(
            payment_status = new_status
        )
    )

    session.execute(stmt)