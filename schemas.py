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
    email : str
    name: str = None
    active : bool = False

    def __init__(self, **data):
        super().__init__(**data)
        if self.name is None:
            self.name = self.email

class UserCreate(UserBase):
    password: str

class User(UserBase):
    user_id: int
    class Config: orm_mode = True


class ClientConfigBase(BaseModel):
    traffic : int
    period : int
    product_id : int
    config_id : int
    active : bool = False

class ClientConfigReq(ClientConfigBase):
    pass

class ClientConfigID(BaseModel):
    config_id: int

class CreateConfigInDB(BaseModel):
    plan_name: str
    config_key: str | None
    config_email: str | None
    traffic_gb: int
    period_day: int
    price: int
    active: float = False
    product_id: int
    owner_id: int | None
    update: bool | None = None
    client_address: str | None = None

class ClientConfig(ClientConfigBase):
    config_id: int
    class Config: orm_mode = True

class CreateIranInvoiceBeforPay(BaseModel):
    action: str
    id_holder: int
    authority: str
    amount: int
    currency: str
    callback_url: str
    description: str
    meta_data: str | None = None
    is_final: bool | None = False
    fee_type: str
    fee: int
    owner_id: int


class CreateCryptomusInvoiceBeforPay(BaseModel):
    amount: str
    action: str
    id_holder: int
    currency: str
    lifetime: int
    order_id: str
    callback_url: str
    is_payment_multiple: bool = True
    additional_data: str
    is_refresh: bool
    is_final: bool = False
    owner_id: int