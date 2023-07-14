# This is where all the swap-service related functions go.
# We may need seperate functions for getting the rates, and performing the swap.

import requests
from fp.fp import FreeProxy


# SWAP FUNCTIONS #######################################################################################################
def at_best_rate():
    # A function that should be able to determine the swap service that gives the best rate, and uses it.
    # Users should be able to set certain swap services to avoid (if desired). By default, all are used.
    # (unless complex setup is required like Kraken)
    pass


def with_sideshift():
    # Documentation: https://sideshift.ai/api/
    pass


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
