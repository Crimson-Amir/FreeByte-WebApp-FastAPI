from .database import Base
from sqlalchemy import Integer, String, Column, Boolean, ForeignKey, DateTime, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime


class User(Base):
    __tablename__ = 'UserDetail'

    user_id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    phone_number = Column(BigInteger, unique=True, default=None)
    name = Column(String)
    hashed_password = Column(String)
    active = Column(Boolean, default=True)
    register_date = Column(DateTime, default=datetime.now())

    config = relationship("V2RayConfig", back_populates="owner")
    cart = relationship("Cart", back_populates="owner")

    iran_payments = relationship("IranPaymentGewayInvoice", back_populates="owner")
    cryptomus_payments = relationship("CryptomusPaymentGewayInvoice", back_populates="owner")

class Product(Base):
    __tablename__ = 'Product'

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    server_address = Column(String, nullable=False)
    server_port = Column(Integer, nullable=False)
    protocol = Column(String, nullable=False)
    encryption = Column(String, default='none')
    security = Column(String, default='none')
    network_type = Column(String, default='tcp')
    header_type = Column(String, default='http')
    header_host = Column(String, default='')
    active = Column(Boolean, default=True)
    register_date = Column(DateTime, default=datetime.now())

    v2ray_config = relationship("V2RayConfig", back_populates="product")

class Cart(Base):
    __tablename__ = 'Cart'

    cart_id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey('UserDetail.user_id'))
    owner = relationship("User", back_populates="cart")

    v2ray_config_associations = relationship("CartV2RayConfigAssociation", back_populates="cart")

class V2RayConfig(Base):
    __tablename__ = 'v2ray_config'

    config_id = Column(Integer, primary_key=True, autoincrement=True)
    plan_name = Column(String)
    config_key = Column(String, unique=True)
    config_email = Column(String, unique=True)
    traffic_gb = Column(Integer)
    period_day = Column(Integer)
    price = Column(Integer)
    active = Column(Boolean, default=True)
    register_date = Column(DateTime, default=datetime.now())

    product_id = Column(Integer, ForeignKey('Product.product_id'))
    product = relationship("Product", back_populates="v2ray_config")

    owner_id = Column(Integer, ForeignKey('UserDetail.user_id'), nullable=True)
    owner = relationship("User", back_populates="config")

    cart_associations = relationship("CartV2RayConfigAssociation", back_populates="v2ray_config")

class CartV2RayConfigAssociation(Base):
    __tablename__ = 'cart_v2ray_config_association'
    cart_id = Column(Integer, ForeignKey('Cart.cart_id'), primary_key=True)
    config_id = Column(Integer, ForeignKey('v2ray_config.config_id'), primary_key=True)
    count = Column(Integer, default=1)

    cart = relationship("Cart", back_populates="v2ray_config_associations")
    v2ray_config = relationship("V2RayConfig", back_populates="cart_associations")


class IranPaymentGewayInvoice(Base):
    __tablename__ = 'iran_payment_geway_invoice'

    invoice_id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String)
    id_holder = Column(Integer, nullable=False)
    authority = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String, default='IRT')
    callback_url = Column(String, nullable=False)
    description = Column(String, nullable=False)
    meta_data = Column(String, nullable=True)
    is_final = Column(Boolean)
    fee_type = Column(String)
    fee = Column(Integer)

    owner_id = Column(Integer, ForeignKey('UserDetail.user_id'))
    owner = relationship("User", back_populates="iran_payments")


class CryptomusPaymentGewayInvoice(Base):
    __tablename__ = 'cryptomus_payment_geway_invoice'

    invoice_id = Column(Integer, primary_key=True, autoincrement=True)
    amount = Column(Integer, nullable=False)
    action = Column(String)
    id_holder = Column(Integer, nullable=False)
    currency = Column(String)
    lifetime = Column(Integer)
    order_id = Column(String, nullable=False)
    callback_url = Column(String, nullable=False)
    is_payment_multiple = Column(Boolean, default=True)
    additional_data = Column(String)
    is_refresh = Column(Boolean, default=True)
    is_final = Column(Boolean)

    owner_id = Column(Integer, ForeignKey('UserDetail.user_id'))
    owner = relationship("User", back_populates="cryptomus_payments")