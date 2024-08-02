from .database import Base
from sqlalchemy import Integer, String, Column, Boolean, Float, ForeignKey, DateTime, BigInteger
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


class V2RayConfig(Base):
    __tablename__ = 'v2ray_config'

    config_id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String, unique=True, nullable=False)
    config_email = Column(String, unique=True, nullable=False)
    traffic_mb = Column(Float)
    period_day = Column(Integer)
    active = Column(Boolean, default=True)
    register_date = Column(DateTime, default=datetime.now())

    product_id = Column(Integer, ForeignKey('Product.product_id'))
    product = relationship("Product", back_populates="v2ray_config")
    owner_id = Column(Integer, ForeignKey('UserDetail.user_id'))
    owner = relationship("User", back_populates="config")
