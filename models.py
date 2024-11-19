from database import Base
from sqlalchemy import Integer, String, Column, Boolean, ForeignKey, DateTime, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime


class User(Base):
    __tablename__ = 'user_detail'

    user_id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    phone_number = Column(BigInteger, unique=True, default=None)
    name = Column(String)
    hashed_password = Column(String)
    active = Column(Boolean, default=True)
    register_date = Column(DateTime, default=datetime.now())

    credit = Column(Integer, default=0)

    purchases = relationship("Purchase", back_populates="owner", cascade="all, delete-orphan")
    cart = relationship("Cart", back_populates="owner", cascade="all, delete-orphan")
    financial_reports = relationship("FinancialReport", back_populates="owner", cascade="all, delete-orphan")


class Cart(Base):
    __tablename__ = 'cart'

    cart_id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey('user_detail.user_id'))
    owner = relationship("User", back_populates="cart")

    purchase_associations = relationship("CartPurchaseAssociation", back_populates="cart", cascade="all, delete-orphan")


class CartPurchaseAssociation(Base):
    __tablename__ = 'cart_purchase_association'
    cart_id = Column(Integer, ForeignKey('cart.cart_id'), primary_key=True)
    purchase_id = Column(Integer, ForeignKey('purchase.purchase_id', ondelete='CASCADE'), primary_key=True)
    count = Column(Integer, default=1)

    cart = relationship("Cart", back_populates="purchase_associations")
    purchase = relationship("Purchase", back_populates="cart_associations")


class FinancialReport(Base):
    __tablename__ = 'financial_report'

    financial_id = Column(Integer, primary_key=True)
    operation = Column(String, default='spend')

    amount = Column(Integer, nullable=False)
    action = Column(String, nullable=False)
    id_holder = Column(Integer)

    payment_getway = Column(String)
    authority = Column(String)
    currency = Column(String)
    url_callback = Column(String)
    additional_data = Column(String)
    payment_status = Column(String)

    register_date = Column(DateTime, default=datetime.now())

    owner_id = Column(BigInteger, ForeignKey('user_detail.user_id'))
    owner = relationship("User", back_populates="financial_reports")

class MainServer(Base):
    __tablename__ = 'main_server'
    server_id = Column(Integer, primary_key=True)
    active = Column(Boolean)
    server_ip = Column(String)
    server_protocol = Column(String)
    server_port = Column(Integer)
    server_username = Column(String)
    server_password = Column(String)
    products = relationship("Product", back_populates="main_server")

class Product(Base):
    __tablename__ = 'product'

    product_id = Column(Integer, primary_key=True)
    active = Column(Boolean)
    product_name = Column(String)
    register_date = Column(DateTime, default=datetime.now())
    purchase = relationship("Purchase", back_populates="product")

    main_server_id = Column(Integer, ForeignKey('main_server.server_id'))
    main_server = relationship("MainServer", back_populates="products")


class Purchase(Base):
    __tablename__ = 'purchase'

    purchase_id = Column(Integer, primary_key=True)
    plan_name = Column(String)
    username = Column(String)
    active = Column(Boolean)
    status = Column(String)
    traffic = Column(Integer)
    period = Column(Integer)
    service_uuid = Column(String)
    subscription_url = Column(String)

    update = Column(Boolean, default=False)
    price = Column(Integer)

    product_id = Column(Integer, ForeignKey('product.product_id'))
    product = relationship("Product", back_populates="purchase")
    owner_id = Column(BigInteger, ForeignKey('user_detail.user_id'))
    owner = relationship("User", back_populates="purchases")

    register_date = Column(DateTime, default=datetime.now())

    cart_associations = relationship("CartPurchaseAssociation", back_populates="purchase")