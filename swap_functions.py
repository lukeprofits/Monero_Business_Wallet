# This is where all the swap-service related functions go.
# We may need different functions for getting the rates, and performing the swap.

import json
import time
import monero_usd_price
import requests
from datetime import datetime, timedelta
from fp.fp import FreeProxy

import wallet_functions as wallet
import config as cfg

# GLOBAL VARIABLES #####################################################################################################
# Sideshift
sideshift_api_endpoint = 'https://sideshift.ai/api/v2/'
sideshift_affiliate_id = 'ql4wc8Y44'  # Required, but I set the commission rate to 0, so that I don't make anything.

# Trocador
trocador_api_endpoint = 'https://trocador.app/en/api/'
trocador_api_key = 'j3uhif80j37OpnZoEwD29w1HqR84A0'  # if my account gets used too much or banned, get your own api key
trocador_ref = 'z1kEXtwvF'

# Localmonero

# Kraken

# IBKR

# ChangeNow
changenow_api_endpoint = 'https://api.changenow.io/v2/'
changenow_api_key = '58aff9c5d295ff13c885e8fcd3373402c3ab8e5752964d9c3e7ff991da831a2f'  # if my account gets used too much or banned, get your own api key

# Supported Coins & Networks
supported_network_names = {
    "Ethereum": ["ethereum", "ERC20", "ERC-20", "eth", ],
    "Polygon": ["polygon", "MATIC", "matic"],
    #"Solana": ["solana", "SOL"],
    #"Avalance C-Chain": ["Avalance C-Chain", "avax", "AVAXC", "Avax-c"],
    "Arbitrum": ["arbitrum", "Arbitrum"],
    #"Optimism": ["optimism", "op"],
    #"Binance Smart Chain": ["Binance Smart Chain", "bsc", "BEP20", "BEP-20"],
    #"Tron": ["tron", "TRC20", "TRC-20", "trx"],
    #"Algorand": ["algorand", "algo"]
}
supported_networks = list(supported_network_names.keys())
supported_coins = ['USDC', 'USDT', 'DAI']  # Add any coin tickers the monero business wallet should support here


# GET COIN FUNCTIONS ###################################################################################################
def get_networks_for_coin_from_sideshift(coin_to_check, proxy=None):
    api_link = f'{sideshift_api_endpoint}coins'
    response = requests.get(api_link, proxies={"http": proxy, "https": proxy})
    response = response.json()
    networks = []
    for item in response:
        # if item['coin'] in coins_supported:
        if item['coin'].lower() == coin_to_check.lower():
            #print(item)
            for i in item['networks']:
                networks.append(i)

    print(f'Sideshift Networks for {coin_to_check}: {networks}')
    return networks


def get_networks_for_coin_from_trocador(coin_to_check, proxy=None):
    api_link = f'{trocador_api_endpoint}coins/?api_key={trocador_api_key}&ref={trocador_ref}'
    response = requests.get(api_link, proxies={"http": proxy, "https": proxy})
    response = response.json()
    networks = []
    for item in response:
        # if item['coin'] in coins_supported:
        if item['ticker'].lower() == coin_to_check.lower():
            #print(item)
            networks.append(item['network'])

    print(f'Trocador Networks for {coin_to_check}: {networks}')
    return networks


def get_networks_for_coin_from_changenow(coin_to_check, proxy=None):
    api_link = f'{changenow_api_endpoint}exchange/currencies?active=&flow=standard&buy=&sell='
    headers = {
        'x-changenow-api-key': changenow_api_key
    }
    response = requests.get(api_link, headers=headers, proxies={"http": proxy, "https": proxy})
    #print(response)
    response = response.json()
    #print(response)
    networks = []
    for item in response:
        if item['ticker'].lower() == coin_to_check.lower():
            #print(item)
            networks.append(item['network'])

    print(f'Changenow Networks for {coin_to_check}: {networks}')
    return networks


# SWAP FUNCTIONS #######################################################################################################
def with_sideshift(shift_to_coin, to_wallet, on_network, amount_to_convert, proxy=None):
    # Documentation: https://sideshift.ai/api/

    converting_from = 'xmr'
    # Confirm that coin and network are still supported (and get min/max swap amounts)
    pass

    # Use supported_network_names to convert on_network to the correct "word" for this platform.
    # (makes all items in both lists lowercase, and then uses "&" to find the intersection)
    on_network = set(n.lower() for n in supported_network_names[on_network]) & set(nn.lower() for nn in get_networks_for_coin_from_sideshift(shift_to_coin))
    on_network = on_network.pop()
    print(on_network)

    # Create variable-rate swap
    response = create_shift_with_sideshift(converting_from=converting_from, shift_to_coin=shift_to_coin, to_wallet=to_wallet, on_network=on_network)
    print(response)

    # Example
    """{'id': '95b520d9ccd01b23c6c5', 'createdAt': '2023-07-27T06:16:24.524Z', 'depositCoin': 'XMR', 'settleCoin': 'USDC',
    'depositNetwork': 'monero', 'settleNetwork': 'polygon', 'depositAddress': '4Bh68jCUZGHbVu45zCVvtcMYesHuduwgajoQcdYRjUQcY6MNa8qd67vTfSNWdtrc33dDECzbPCJeQ8HbiopdeM7Ej3qLTv2mWCwMgFHsyQ',
    'settleAddress': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D', 'depositMin': '0.018337408314',
    'depositMax': '30.56234719', 'type': 'variable', 'expiresAt': '2023-08-03T06:16:24.524Z', 'status': 'waiting', 
    'averageShiftSeconds': '28.21795'}"""

    shift_id = response['id']
    created_at = response['createdAt']  #
    deposit_coin = response['depositCoin']  #
    settle_coin = response['settleCoin']  #
    settle_network = response['settleNetwork']  #
    send_to_wallet = response['depositAddress']
    settle_address = response['settleAddress']  #
    send_min = response['depositMin']
    send_max = response['depositMax']
    swap_type = response['status']  #
    expires_at = response['expiresAt']
    status = response['status']
    average_time_to_complete = response['averageShiftSeconds']

    print('Shift ID:', shift_id,
          '\nSend To Wallet:', send_to_wallet,
          '\nMinumum:', send_min,
          '\nMaximum:', send_max,
          '\nExpires At:', expires_at,
          '\nStatus:', status,
          '\nAverage Time To Complete:', average_time_to_complete)

    # Confirm that everything in the swap matches what we want.
    is_at_least_ten_minutes_before = datetime.utcnow() + timedelta(minutes=10) <= datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%S.%fZ")
    if (
        deposit_coin.lower() == converting_from.lower() and
        settle_coin.lower() == shift_to_coin.lower() and
        settle_network.lower() == on_network.lower() and
        settle_address == to_wallet and
        is_at_least_ten_minutes_before and
        float(average_time_to_complete) <= float(60 * 60 * 24) and  # 24hrs
        send_min <= amount_to_convert
        ):

        # If we made it here, proceed with the swap
        if amount_to_convert >= send_max:
            print('This is too much to convert!')
            smaller_amount = amount_to_convert
            attempt_count = 0

            while smaller_amount >= send_max and attempt_count < 20:  # arbitrary 20 attempts at cutting it in half.
                print('...trying with less')
                smaller_amount /= 2  # Halve the smaller_amount

                if smaller_amount < send_max:
                    print(f'Converting! This may take up to: {average_time_to_complete} to complete.')
                    wallet.send_monero(destination_address=send_to_wallet, amount=smaller_amount)
                    break  # Exit the loop since we found an acceptable amount

                attempt_count += 1  # Increment the counter

            swap_info = {'sent_xmr_amount': smaller_amount, 'to_wallet': send_to_wallet, 'swap_id': shift_id, 'service': 'sideshift'}
            return swap_info

        else:  # We can convert this amount because it is above min and below max.
            print(f'Converting! This may take up to: {average_time_to_complete} to complete.')
            wallet.send_monero(destination_address=send_to_wallet, amount=amount_to_convert)
            swap_info = {'sent_xmr_amount': amount_to_convert, 'to_wallet': send_to_wallet, 'swap_id': shift_id, 'service': 'sideshift'}
            return swap_info

    # There is a problem. DO NOT SWAP!
    else:
        print('DO NOT SWAP')
        return dict()


def with_trocador():
    # Documentation: https://trocador.app/en/docs/
    # (Would be cool to add tor and i2p in the future at some point)
    pass


def with_localmonero():
    # Documentation: https://agoradesk.com/api-docs/v1#section/Introduction
    pass


def with_kraken():
    # Documentation: https://docs.kraken.com/rest/
    pass


def with_ibkr():
    # Documentation: https://www.interactivebrokers.com/api/doc.html
    # Not sure if we really want to add this one or not, but it was suggested (I've never heard of them).
    pass


def with_changenow():
    # Documentation: https://gitlab.com/changenow-s-library-catalogue/changenow-api-python
    pass


def at_best_rate():
    # A function that should be able to determine the swap service that gives the best rate, and uses it.
    # Users should be able to set certain swap services to avoid (if desired). By default, all are used.
    # (unless complex setup is required like Kraken)
    pass


# SUPPLEMENTAL FUNCTIONS ###############################################################################################
def check_if_ip_address_works_with_sideshift(proxy=None):
    sideshift_check_url = "https://sideshift.ai/api/v2/permissions"

    response = requests.get(url=sideshift_check_url, proxies={"http": proxy, "https": proxy})
    if response.status_code == 200:
        data = response.json()
        working = data.get("createShift")
        return bool(working)
    else:
        #print("Request failed with status code:", response.status_code)
        return False


def find_working_proxy_for_sideshift():
    result = False
    while not result:
        try:
            print('No working proxy yet. Getting a random one.')
            proxy = FreeProxy(rand=True, timeout=1,).get()
            print('Checking: ' + proxy)
            result = check_if_ip_address_works_with_sideshift(proxy=proxy)
        except:
            pass
    print(f'\nWe bypassed SideShifts location restrictions with proxy {proxy}')
    return proxy


def create_shift_with_sideshift(converting_from, shift_to_coin, to_wallet, on_network):
    while True:
        try:
            # check if we are blocked on the current IP
            if not check_if_ip_address_works_with_sideshift():
                # we are blocked, the user probably has a VPN on, so use a proxy
                print('looking for a proxy that will work')
                proxy = find_working_proxy_for_sideshift()
                #proxy = 'http://20.44.206.138:80'  #'http://52.221.130.124:80'
                time.sleep(5)
            else:
                print('Not using a proxy')
                proxy = None

            api_link = f'{sideshift_api_endpoint}shifts/variable'
            headers = {
                'Content-Type': 'application/json'
            }
            data = {
                "settleAddress": to_wallet,
                # "refundAddress": refund_address,  # leaving this out to stay anonymous
                "depositCoin": converting_from,
                "settleCoin": shift_to_coin,
                "settleNetwork": on_network,
                "affiliateId": sideshift_affiliate_id,
                "commissionRate": 0.0  # set the commissionRate to 0
            }
            print('sending request/waiting for response...')
            response = requests.post(api_link, headers=headers, data=json.dumps(data), proxies={"http": proxy, "https": proxy})

            if response.status_code == 201:  # it was successful
                print('Created Shift!')
                return response.json()
            else:
                print(response)
        except Exception as e:
            print(e)
            time.sleep(2)


# TESTING ##############################################################################################################
#get_networks_for_coin_from_changenow('DAI')
#get_networks_for_coin_from_sideshift('DAI')
#get_networks_for_coin_from_trocador('DAI')

#with_sideshift(shift_to_coin='USDC', to_wallet='0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D', on_network='Polygon', amount_to_convert=111)
