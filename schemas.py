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
    active : bool = False

class ClientConfigCreate(ClientConfigBase):
    pass

class ClientConfigCreateCrud(ClientConfigBase):
    owner_id: int

class ClientConfig(ClientConfigBase):
    config_id: int
    class Config: orm_mode = True

