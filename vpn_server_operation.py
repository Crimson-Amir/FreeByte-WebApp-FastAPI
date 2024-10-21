import logging
import crud, private
import uuid, pytz, random, string, requests
from datetime import datetime, timedelta
from utilities import connect_to_server_instance, traffic_to_gb, report_status_to_admin, second_to_ms
from panel_api import marzban_api


async def get_server_details(all_services):
    if len(all_services) <= 3:
        final_result = dict()
        connect_to_server_instance.refresh_token()

        for purchase in all_services:
            try:

                get_service_detail = await connect_to_server_instance.api_operation.get_user(
                    purchase.product.main_server.server_ip,
                    purchase.username
                )
                final_result[purchase.username] = {}
                final_result[purchase.username]['usage_percent'] = int(get_service_detail.get('used_traffic', 0) / get_service_detail.get('data_limit', 0)) * 100
                final_result[purchase.username]['left_day'] = max((second_to_ms(get_service_detail.get('expire'), False) - datetime.now(pytz.timezone('Asia/Tehran')).replace(tzinfo=None)).days, 0)
                final_result[purchase.username]['left_traffic'] = round(traffic_to_gb(get_service_detail.get('data_limit', 0) - get_service_detail.get('used_traffic', 0), True), 2)

            except Exception as e:
                final_result[purchase.username] = {'usage_percent': 0, 'left_day': 0, 'left_traffic': 0, 'error': 'config is not availabale in server'}
                logging.error(f'error occurred in get_purchase_detail:\n{e}')

        return final_result
    return {}



async def create_json_config(username, expiration_in_day, traffic_in_byte, service_uuid, status="active"):
    return {
        "username": username,
        "proxies": {
            "vless": {
                "id": service_uuid
            },
            "vmess": {
                "id": service_uuid
            },
            "trojan": {
                "password": service_uuid
            },
            "shadowsocks": {
                "password": service_uuid
            },
        },
        "inbounds": {
            "vless": [
                "VLESS TCP",
                "VLESS TCP REALITY",
                "VLESS GRPC REALITY"
            ],
            "vmess": [
                "VMess TCP",
                "VMess Websocket",
            ],
            "trojan": [
                "Trojan Websocket TLS",
            ],
            "shadowsocks": [
                "Shadowsocks TCP",
            ],
        },
        "expire": expiration_in_day,
        "data_limit": traffic_in_byte,
        "data_limit_reset_strategy": "no_reset",
        "status": status,
        "note": "",
        "on_hold_timeout": "2023-11-03T20:30:00",
        "on_hold_expire_duration": 0
    }


async def create_service_in_servers(session, purchase, user_id):

    if not purchase:
        raise ValueError('Purchase is empty!')

    username = (
        f"{''.join(random.choices(string.ascii_lowercase, k=5))}"
    )
    calcuate_price = (private.price_per_gb * purchase.traffic) + (private.price_per_day * purchase.period)
    traffic_to_byte = int(purchase.traffic * (1024 ** 3))
    now = datetime.now(pytz.timezone('Asia/Tehran'))
    date_in_timestamp = (now + timedelta(days=purchase.period)).timestamp()
    service_uuid = uuid.uuid4().hex

    json_config = await create_json_config(username, date_in_timestamp, traffic_to_byte, service_uuid=service_uuid)
    create_user = await marzban_api.add_user(purchase.product.main_server.server_ip, json_config)

    create_new_puchase = crud.create_purchase(
        session, purchase.product_id,
        username=username,
        user_id=user_id,
        traffic=purchase.traffic,
        period=purchase.period,
        active=True,
        update=True,
        plan_name=purchase.plan_name,
        subscription_url=create_user['subscription_url'],
        status='active',
        register_date=datetime.now(pytz.timezone('Asia/Tehran')),
        service_uuid=service_uuid,
        price=calcuate_price
    )
    session.refresh(create_new_puchase)

    msg = (f'User Buy Service'
           f'\nService ID: {purchase.purchase_id}'
           f'\nService username: {create_new_puchase.username}'
           f'\nTraffic: {purchase.traffic}GB'
           f'\nPeriod: {purchase.period}day'
           f'\nproduct Name: {purchase.product.product_name}'
           f'\nproduct ID: {purchase.product.product_id}'
           f'\nAmount: {calcuate_price:,}')
    await report_status_to_admin(msg, 'success', purchase.owner)

    return create_new_puchase


async def upgrade_service_for_user(db, purchase, amount):
    main_server_ip = purchase.product.main_server.server_ip

    try:
        user = await marzban_api.get_user(main_server_ip, purchase.username)

        if user['status'] == 'active':
            traffic_to_byte = int((purchase.traffic * (1024 ** 3)) + user['data_limit'])
            expire_date = datetime.fromtimestamp(user['expire'])
        else:
            await marzban_api.reset_user_data_usage(main_server_ip, purchase.username)
            traffic_to_byte = int(purchase.traffic * (1024 ** 3))
            expire_date = datetime.now(pytz.timezone('Asia/Tehran'))

        date_in_timestamp = (expire_date + timedelta(days=purchase.period)).timestamp()

        json_config = await create_json_config(
            purchase.username, date_in_timestamp, traffic_to_byte,
            service_uuid=purchase.service_uuid if purchase.service_uuid else uuid.uuid4().hex
        )
        await marzban_api.modify_user(main_server_ip, purchase.username, json_config)

        calcuate_price = (private.price_per_gb * purchase.traffic) + (private.price_per_day * purchase.period)

        crud.update_purchase(
            db,
            purchase.purchase_id,
            price=calcuate_price,
            status='active',
            register_date=datetime.now(pytz.timezone('Asia/Tehran')),
        )

        db.refresh(purchase)

        msg = (f'User Upgrade Service'
               f'\nService ID: {purchase.purchase_id}'
               f'\nService username: {purchase.username}'
               f'\nAdd Traffic: {purchase.traffic}GB'
               f'\nAdd Period: {purchase.period}day'
               f'\nproduct Name: {purchase.product.product_name}'
               f'\nproduct ID: {purchase.product.product_id}'
               f'\nAmount: {amount:,}')
        await report_status_to_admin(msg, 'success', purchase.owner)

        return purchase

    except Exception as e:
        await handle_http_error(purchase, main_server_ip, purchase.purchase_id, e)


async def handle_http_error(purchase, main_server_ip, purchase_id, original_error):
    """
    Handles HTTP errors during the upgrade process and attempts to deactivate the user's service.
    """
    try:
        traffic_to_byte = int(purchase.traffic * (1024 ** 3))
        expire_date = purchase.register_date
        date_in_timestamp = (expire_date + timedelta(days=purchase.period)).timestamp()
        json_config = await create_json_config(purchase.username, date_in_timestamp, traffic_to_byte, service_uuid=purchase.service_uuid)
        await marzban_api.modify_user(main_server_ip, purchase.username, json_config)
    except requests.exceptions.HTTPError as e:
        logging.error(f'failed to rollback user service!\n{str(e)}\nid: {purchase_id}')

        error_message = (
            f'Failed to rollback user service after HTTP error in upgrade!'
            f'\nService username: {purchase.username}'
            f'\nService ID: {purchase_id}'
        )
        await report_status_to_admin(error_message, 'error', purchase.owner)
        raise e from original_error

    raise original_error