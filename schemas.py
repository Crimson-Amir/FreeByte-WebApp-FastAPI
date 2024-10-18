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
    private_token = str

class User(UserBase):
    user_id: int
    class Config: orm_mode = True


class PurchaseBase(BaseModel):
    traffic : int
    period : int
    product_id : int
    purchase_id : int
    active : bool = False

class PurchaseRequirement(PurchaseBase):
    pass

class PurchaseRequirementCustom(BaseModel):
    traffic: int
    period: int

class PurchaseID(BaseModel):
    purchase_id: int

class CreateConfigInDB(BaseModel):
    username: str
    active: bool
    status: str
    traffic: int
    period: int
    service_uuid: str | None
    subscription_url: str | None
    product_id: int
    owner_id: int

class ClientConfig(PurchaseBase):
    db_purchase_id: int
    class Config: orm_mode = True

class UpgradeCustomService(BaseModel):
    username: str
    traffic: int
    period: int

class CheckAnyProductMatch(BaseModel):
    country: str
    iran_domain_address: str
    encryption: str | None
    security: str
    network_type: str
    header_type: str
    header_host: str

class CryptomusPaymentWebhook(BaseModel):
    type: str
    uuid: str
    order_id: str
    amount: str
    payment_amount_usd: str
    is_final: bool
    status: str
    sign: str
    additional_data: str

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

class add_service_to_cart_for_renew(BaseModel):
    config_id: int