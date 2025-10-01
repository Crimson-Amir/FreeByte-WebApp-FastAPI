import logging
import sqlalchemy.exc
from fastapi import FastAPI, Request, Depends, HTTPException, Cookie, Response, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import schemas, crud, private, models
import jwt, pytz, requests
from datetime import datetime
from auth import SECRET_KEY, REFRESH_SECRET_KEY, create_access_token, create_refresh_token, verify_api_token
from utilities import (decode_access_token, connect_to_server_instance, get_db, token_black_list,
                        calculate_total_price, report_status_to_admin, remove_service_from_server)
from payment_init import create_invoice, verify_iran_payment, verify_cryptomus_payment
from vpn_server_operation import get_server_details, upgrade_service_for_user, create_service_in_servers


verification_codes = {}

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount('/statics', StaticFiles(directory='statics'), name='static')


@app.post("/refresh-token")
def refresh_token(request: Request, response: Response, refresh_token_attr: str = Cookie(None)):
    if not refresh_token_attr:
        raise HTTPException(status_code=401, detail="Refresh token is missing")

    try:
        payload = jwt.decode(refresh_token_attr, REFRESH_SECRET_KEY, algorithms=["HS256"])
        email= payload.get("email"),
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        new_access_token = create_access_token(data={"email": email, "name": payload.get("name"), "user_id": payload.get("user_id")})
        request.state.user = payload
        response.set_cookie(key="access_token", value=new_access_token, httponly=True, secure=True, max_age=3600)
        return {"access_token": new_access_token}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.middleware("http")
async def authenticate_request(request: Request, call_next):
    exception_paths = ["/sign-up/"]

    if request.url.path in exception_paths:
        response = await call_next(request)
        return response

    token = request.cookies.get("access_token")
    request.state.user = None

    async def generate_new_token():
        get_refresh_token = request.cookies.get("refresh_token")
        if get_refresh_token:
            try:
                refresh_payload = jwt.decode(get_refresh_token, REFRESH_SECRET_KEY, algorithms=["HS256"])
                new_access_token = create_access_token(data={"email": refresh_payload.get("email"),
                                                             "name": refresh_payload.get("name"),
                                                             "user_id": refresh_payload.get("user_id")})
                request.state.user = new_access_token.encode()
                new_response = await call_next(request)
                new_response.set_cookie(key="access_token", value=new_access_token, httponly=True, secure=True, max_age=3600)
                return new_response

            except jwt.ExpiredSignatureError:
                return RedirectResponse('/sign-up/')

            except jwt.InvalidTokenError:
                return RedirectResponse('/sign-up/')

    if token and token not in token_black_list.black_list:
        try:
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.state.user = token.encode()
        except jwt.ExpiredSignatureError:
            response = await generate_new_token()
            if response: return response
        except jwt.InvalidTokenError:
            return RedirectResponse('/sign-up/')

    else:
        response = await generate_new_token()
        if response: return response

    response = await call_next(request)
    return response

@app.get('/')
async def root(): return RedirectResponse('/home')

@app.api_route('/home', methods=['POST', 'GET'])
async def home(request: Request):
    all_data = await decode_access_token(request, True)

    return templates.TemplateResponse(request=request, name='index/index.html', context={'user_data': all_data})

@app.get('/sign-up/')
async def sign_up(request: Request):
    return templates.TemplateResponse(request=request, name='authentication/sign_in.html')

@app.post('/sign-up/', response_model=schemas.User)
async def create_user(user: schemas.UserCreate, response: Response, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, user.email)
    if db_user: raise HTTPException(400, 'email already registred.')

    if not await verify_api_token(user.private_token):
        return {'error': 'token not match!'}

    create_user_db = crud.create_user(db, user)
    crud.create_cart(db, create_user_db.user_id )

    user_data = {"email": create_user_db.email, "name": create_user_db.name, "user_id": create_user_db.user_id}

    access_token = create_access_token(data=user_data)
    cr_refresh_token = create_refresh_token(data=user_data)

    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, max_age=3600)
    response.set_cookie(key="refresh_token", value=cr_refresh_token, httponly=True, secure=True, max_age=2_592_000)

    return create_user_db


@app.api_route('/loggin', methods=['GET', 'POST'], response_model=schemas.User)
async def loggin(request: Request, response: Response, user: schemas.UserLoggin = None, db: Session = Depends(get_db)):

    if request.method == 'GET':
        return templates.TemplateResponse(request=request, name='authentication/loggin.html')

    db_user = crud.get_user_by_email(db, user.email)
    if not db_user: raise HTTPException(400, 'email does not exist.')

    request_hashed_password = crud.hash_password_md5(user.password)
    if request_hashed_password != db_user.hashed_password: raise HTTPException(400, 'password is not correct.')

    user_data = {"email": db_user.email, "name": db_user.name, "user_id": db_user.user_id}

    access_token = create_access_token(data=user_data)
    cr_refresh_token = create_refresh_token(data=user_data)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, max_age=3600)
    response.set_cookie(key="refresh_token", value=cr_refresh_token, httponly=True, secure=True, max_age=2_592_000)

    return db_user

@app.post('/logout')
async def loggin(request: Request):
    token = request.cookies.get('access_token')
    redirect = RedirectResponse('/home/')
    if token:
        token_black_list.add(token)
        redirect.delete_cookie(key='access_token', httponly=True)
        redirect.delete_cookie(key="refresh_token", httponly=True)
    return redirect


@app.get('/cart')
async def cart(request: Request, db: Session = Depends(get_db)):
    user_id = await decode_access_token(request)
    db_cart = crud.get_cart(db, user_id)
    list_len = len(db_cart.purchase_associations)
    price = await calculate_total_price(db_cart.purchase_associations)
    return templates.TemplateResponse(request=request, name='cart/cart.html',
                                      context={'db_cart': db_cart, 'list_len': list_len, 'price': price})


@app.post('/add_to_cart/')
async def add_to_cart(purchase: schemas.PurchaseBase, request: Request, db: Session = Depends(get_db)):
    try:
        user_id = await decode_access_token(request)
        cart_id = crud.get_cart(db, user_id)
        check_in_cart = crud.is_config_available_in_cart(db, cart_id.cart_id, purchase.purchase_id)
        if check_in_cart:
            crud.add_config_count_in_cart(db, cart_id.cart_id, purchase.purchase_id)
        else:
            crud.add_to_cart(db, cart_id.cart_id, purchase.purchase_id)
        return {'status': 'ok'}
    except Exception as e:
        logging.error(f'error occurred in add_to_cart:\n{e}')
        return {'status': 'error', 'reason': str(e)}

@app.post('/add_purchase_count_in_cart/')
async def add_purchase_count_in_cart(purchase: schemas.PurchaseID, request: Request, db: Session = Depends(get_db)):
    try:
        user_id = await decode_access_token(request)
        cart_id = crud.get_cart(db, user_id)
        check_in_cart = crud.is_config_available_in_cart(db, cart_id.cart_id, purchase.purchase_id)
        if check_in_cart:
            add_count = crud.add_config_count_in_cart(db, cart_id.cart_id, purchase.purchase_id)
            new_price = await calculate_total_price(add_count.cart.purchase_associations)
            return {'status': 'ok', 'new_price': new_price}
        return {'status': 'nok'}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}

@app.patch('/subtract_purchase_count_in_cart/')
async def subtract_config_count(purchase: schemas.PurchaseID, request: Request, db: Session = Depends(get_db)):
    try:
        user_id = await decode_access_token(request)
        cart_id = crud.get_cart(db, user_id)
        check_in_cart = crud.is_config_available_in_cart(db, cart_id.cart_id, purchase.purchase_id)
        if check_in_cart:
            subtract = crud.subtract_config_count_in_cart(db, cart_id.cart_id, purchase.purchase_id)
            new_price = await calculate_total_price(subtract.cart.purchase_associations)
            return {'status': 'ok', 'new_price': new_price}
        return {'status': 'nok'}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}


@app.delete('/remove_from_cart/{cart_id}/{purchase_id}')
async def remove_from_cart(cart_id: int, purchase_id: int, db: Session = Depends(get_db)):
    try:
        remove = crud.remove_from_cart(db, cart_id, purchase_id)
        new_price = await calculate_total_price(remove.cart.purchase_associations)
        return {'status': 'ok', 'config_id': cart_id, 'new_item_count': len(remove.cart.purchase_associations), 'new_price': new_price}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}


@app.post('/payment/')
async def payment(request: Request, payment_gateway: str = Form(...), db: Session = Depends(get_db)):
    try:
        action = 'webapp_cart_payment'
        user_id = await decode_access_token(request)
        db_cart = crud.get_cart(db, user_id)
        amount = await calculate_total_price(db_cart.purchase_associations)

        nvoice_link = await create_invoice(
            database=db, user_id=user_id, action=action, amount=amount, cart_id=db_cart.cart_id, gateway=payment_gateway
        )

        if not nvoice_link: return {'status': 'the invoice was not created'}

        if payment_gateway in ['iran_payment_getway', 'pay_by_wallet']:
            return RedirectResponse(nvoice_link)
        else:
            return templates.TemplateResponse(request=request, name='cart/send_user_to_payment_getway.html', context={'link': nvoice_link})

    except Exception as e:
        logging.error(f'error uccurred in payment.\n{e}')
        return {'status': 'error'}

import traceback


@app.post('/pay_by_wallet/{authority}')
async def pay_by_wallet(authority: str, request: Request, db: Session = Depends(get_db)):
    db.begin()
    user_id = await decode_access_token(request)
    financial = crud.get_payment_detail_by_authority(db, authority)

    if not financial or financial.payment_status in ['paid', 'refund'] or financial.owner_id != user_id:
        return templates.TemplateResponse(request=request, name='cart/fail_pay.html', context={
            'error_reason': f'تراکنش مورد نظر تایید نشده است. آیدی تراکنش {authority}',
            'error_code': 403})

    if financial.owner.credit < financial.amount:
        return templates.TemplateResponse(request=request, name='cart/fail_pay.html', context={
            'error_reason': f'اعتبار شما برای پرداخت این فاکتور کافی نیست!',
            'error_code': 403})

    try:
        connect_to_server_instance.refresh_token()
        await handle_successful_payment(db, financial)
        crud.reduce_credit_from_user(db, financial.owner_id, financial.amount)
        db.commit()
        return RedirectResponse('/dashboard/?payment_status=1')

    except Exception as e:
        logging.error(f'error uccurred in pay_by_wallet: {e}')
        db.rollback()
        return RedirectResponse('/dashboard/?payment_status=2')


@app.get('/iran_recive_payment_result/')
async def recive_payment_result(Authority: str, Status: str, request: Request, db: Session = Depends(get_db)):
    db.begin()
    financial = crud.get_payment_detail_by_authority(db, Authority)

    if Status != 'OK' or not financial:
        return templates.TemplateResponse(request=request, name='cart/fail_pay.html', context={
            'error_reason': f'تراکنش مورد نظر تایید نشده است. آیدی تراکنش {Authority}',
            'error_code': 403})

    try:
        connect_to_server_instance.refresh_token()
        response = await verify_iran_payment(Authority, financial.amount)

        if response.get('data', {}).get('code', 101) == 100:
            await handle_successful_payment(db, financial)
            db.commit()
            return RedirectResponse('/dashboard/?payment_status=1')

    except Exception as e:
        db.rollback()
        await handle_failed_payment(db, financial, e)
        return RedirectResponse('/dashboard/?payment_status=2')

@app.post('/crypto_recive_payment_result/')
async def crypto_recive_payment_result(data: schemas.CryptomusPaymentWebhook, db: Session = Depends(get_db)):
    if data.status in ['paid', 'paid_over']:
        db.begin()
        financial = crud.get_payment_detail_by_authority(db, data.order_id)
        if not financial or financial.payment_status in ['paid', 'refund']: return
        connect_to_server_instance.refresh_token()

        try:
            response = await verify_cryptomus_payment(financial.authority, None)
            if response:
                await handle_successful_payment(session=db, financial=financial)
                db.commit()
        except Exception as e:
            db.rollback()
            await handle_failed_payment(db, financial, e)
            return {'ok': 'nok'}

async def handle_successful_payment(session, financial):
    """Processes the successful payment."""
    user_cart = crud.get_cart(session, financial.owner_id)

    for service in user_cart.purchase_associations:
        if service.purchase.update:
            await upgrade_service_for_user(session, service.purchase, financial.amount)
            continue

        service_count = service.count

        for _ in range(service_count):
            create = await create_service_in_servers(session, service.purchase, financial.owner_id)
            if not create:
                raise ValueError('config is not available in server')

    crud.update_financial_report_status(session, financial.financial_id, 'paid')
    session.query(models.CartPurchaseAssociation).filter(models.CartPurchaseAssociation.cart_id == financial.id_holder).delete()
    await handle_successful_report(financial)

async def handle_successful_report(financial):
    """Reports successful payment."""

    msg = (
        f'Action: {financial.action.replace("_", " ")}\n'
        f'Authority: {financial.authority}\n'
        f'Amount: {financial.amount:,}\n'
        f'Gateway: {financial.payment_getway}\n'
        f'Cart ID: {financial.id_holder}\n'
    )

    await report_status_to_admin(msg, 'success', financial.owner)


async def handle_failed_payment(session, financial, exception):
    """Handles payment failure and refunds if necessary."""
    crud.add_credit_to_user(session, financial.owner_id, financial.amount)
    crud.update_financial_report_status(session, financial.financial_id, 'refund')
    tb = traceback.format_exc()

    error_msg = (
        'Amount refunded to user wallet! Payment was not successful!'
        f'\n\nAuthority: {financial.authority}'
        f'\nUser ID: {financial.owner_id}'
        f'\nAmount: {financial.amount:,}'
        f'\n\nError: {str(exception)}'
        f'\n\nTraceBack:\n{tb}'
    )

    await report_status_to_admin(error_msg, 'error', financial.owner)


@app.api_route('/dashboard/', methods=['POST', 'GET'])
async def dashboard(request: Request, payment_status: int = None, db: Session = Depends(get_db)):
    user_id = await decode_access_token(request)
    all_services = crud.get_user_purchases(db, user_id)
    all_data = await decode_access_token(request, True)

    return templates.TemplateResponse(request=request, name='dashboard/my_product.html', context={
        'user_data': all_data,
        'all_services': all_services,
        'service_detail_from_server': await get_server_details(all_services),
        'payment_status': payment_status,
    })

@app.get('/dashboard/service_detail/{service_id}')
async def dashboard(request: Request, service_id: int, db: Session = Depends(get_db)):
    user_id = await decode_access_token(request)
    get_service_detail = crud.get_purchase(db, service_id, user_id)
    all_data = await decode_access_token(request, True)

    return templates.TemplateResponse(request=request, name='dashboard/my_product.html', context={
        'user_data': all_data,
        'service_detail_from_server': await get_server_details(get_service_detail),
        'all_services': get_service_detail
    })

@app.delete('/remove-user-service/{config_id}')
async def remove_user_service(config_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = await decode_access_token(request)
    try:
        purchase = crud.remove_purchase(db, config_id, user_id)
        await remove_service_from_server(purchase)

        error_msg = (
            'User Remove Service!'
            f'\n\nPurchase username: {purchase.username}'
            f'\nPurchase ID: {purchase.purchase_id}'
            f'\nService Plane: {purchase.plan_name}'
            f'\nPurchase Price: {purchase.price:,}'
            f'\nTraffic: {purchase.traffic}'
            f'\nPeriod: {purchase.period}'
        )

        await report_status_to_admin(error_msg, 'success', purchase.owner)

        return {'status': 'ok'}
    except Exception as e:
        return HTTPException(500, {'error': e})


@app.patch('/add-service-to-cart-for-renew/')
async def add_service_to_cart_for_renew(data: schemas.add_service_to_cart_for_renew, request: Request, db: Session = Depends(get_db)):
    try:
        user_id = await decode_access_token(request)
        cart_id = crud.get_cart(db, user_id)
        check_in_cart = crud.is_config_available_in_cart(db, cart_id.cart_id, data.config_id)
        if check_in_cart:
            return {'status': 'nok', 'message': 'service already in cart'}

        crud.add_to_cart(db, cart_id.cart_id, data.config_id)

        return {'status': 'ok'}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}

class SeriveAlreadyExistInDashboard(Exception):
    pass


@app.post('/upgrade-foreign-service/')
async def upgrade_foreign_service(config: schemas.UpgradeCustomService, request: Request, db: Session = Depends(get_db)):
    try:
        with db.begin():
            user_id = await decode_access_token(request)
            cart_id = crud.get_cart(db, user_id)
            connect_to_server_instance.refresh_token()
            traffic, period = config.traffic, config.period
            calcuate_price = (private.price_per_gb * config.traffic) + (private.price_per_day * config.period)
            username = config.username

            default_product = crud.get_first_product(db)
            check_in_server = await connect_to_server_instance.api_operation.get_user(default_product.main_server.server_ip, username)

            if check_in_server:
                service = crud.get_purchase_by_username(db, check_in_server['username'])
                if service:
                    if service.active and service.owner_id == user_id:
                        raise SeriveAlreadyExistInDashboard()

                    crud.update_config_traffic_and_period(db, service.purchase_id, traffic, period, calcuate_price)
                else:
                    service = crud.create_purchase(
                        db, default_product.product_id,
                        username=username,
                        user_id=user_id,
                        traffic=traffic,
                        period=period,
                        active=False,
                        update=True,
                        subscription_url=check_in_server['subscription_url'],
                        register_date=datetime.now(pytz.timezone('Asia/Tehran')),
                        service_uuid=check_in_server.get('proxies', {}).get('vless', {}).get('id'),
                        price=calcuate_price
                    )
                    db.flush()

                crud.add_to_cart(db, cart_id.cart_id, service.purchase_id, commit=False)

                return {'status': 'ok'}

    except SeriveAlreadyExistInDashboard:
        return {'status': 'ServiceIsActive'}

    except sqlalchemy.exc.IntegrityError:
        return {'status': 'alreadyExist'}

    except Exception as e:
        if "404 Client Error" in str(e):
          return {'status': 'notExist'}
        return {'status': 'error', 'reason': str(e)}
