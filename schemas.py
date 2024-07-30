from pydantic import BaseModel

class ProductBase(BaseModel):
    server_address: str
    server_port: int
    protocol: str
    encryption: str | None = None
    security: str | None = None
    network_type: str = 'tcp'
    header_type: str = 'http'
    header_host: str | None = None
    active: bool = False

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    product_id: int
    class Config: orm_mode = True




class UserBase(BaseModel):
    email : str = None
    phone_number: int = None
    active : bool = False

class UserCreate(UserBase):
    password: str


class User(BaseModel):
    user_id: int
    class Config: orm_mode = True




class ClientConfigBase(BaseModel):
    config_email : str
    traffic_mb : int
    period_day : int
    active : bool
    product_id : int
    owner_id : int

class ClientConfigCreate(ClientConfigBase):
    config_key: str


class ClientConfig(ClientConfigBase):
    config_id: int
    class Config: orm_mode = True