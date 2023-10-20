import os
import csv
import time
import json
import gzip
import psutil
import base64
import qrcode
import random
import requests
import threading
import subprocess
from lxml import html
import monero_usd_price
import PySimpleGUI as sg
from datetime import datetime, timezone
import platform
import clipboard

import config as cfg

# CHECK FUNCTIONS ( Return True/False ) ################################################################################
def check_if_monero_wallet_address_is_valid_format(wallet_address):
    # Check if the wallet address starts with the number 4
    if wallet_address[0] != "4":
        return False

    # Check if the wallet address is exactly 95 or 106 characters long
    if len(wallet_address) not in [95, 106]:
        return False

    # Check if the wallet address contains only valid characters
    valid_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    for char in wallet_address:
        if char not in valid_chars:
            return False

    # If it passed all these checks
    return True


def check_if_wallet_exists(daemon_rpc_url):
    if not os.path.isfile(f"{cfg.wallet_name}.keys") or not os.path.isfile(cfg.wallet_name):
        # If either file doesn't exist
        start_block_height = get_current_block_height(daemon_rpc_url=daemon_rpc_url)
        create_wallet(wallet_name=cfg.wallet_name)
        return start_block_height

    else:
        # If both files exist, do nothing
        print('Wallet exists already.')
        return None


def check_if_node_works(node):
    url = f'http://{node}/json_rpc'
    headers = {'Content-Type': 'application/json'}
    payload = {
        'jsonrpc': '2.0',
        'id': '0',
        'method': 'get_info',
        'params': {}
    }

    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
        result = response.json()

        if 'result' in result and 'status' in result['result'] and result['result']['status'] == 'OK':
            return True
        else:
            return False

    except requests.exceptions.RequestException as e:
        print(e)
        return False


def check_if_payment_id_is_valid(payment_id):
    if len(payment_id) != 16:
        return False

    valid_chars = set('0123456789abcdef')
    for char in payment_id:
        if char not in valid_chars:
            return False

    # If it passed all these checks
    return True


# WALLET "RETURN SOMETHING" FUNCTIONS ##################################################################################
def make_integrated_address(payment_id, merchant_public_wallet_address):
    headers = {'Content-Type': 'application/json'}
    data = {
        "jsonrpc": "2.0",
        "id": "0",
        "method": "make_integrated_address",
        "params": {
            "standard_address": merchant_public_wallet_address,
            "payment_id": payment_id
        }
    }

    response = requests.post(f"{cfg.local_rpc_url}", headers=headers, data=json.dumps(data))
    result = response.json()

    if 'error' in result:
        print('Error:', result['error']['message'])

    else:
        integrated_address = result['result']['integrated_address']
        return integrated_address


def get_current_block_height(daemon_rpc_url):
    # Set up the JSON-RPC request
    headers = {'content-type': 'application/json'}
    data = {
        "jsonrpc": "2.0",
        "id": "0",
        "method": "get_info"
    }

    # Send the JSON-RPC request to the daemon
    response = requests.post(daemon_rpc_url, data=json.dumps(data), headers=headers)

    # Parse the response to get the block height
    if response.status_code == 200:
        response_data = response.json()
        block_height = response_data["result"]["height"]
        print(f'Block Height: {block_height}')
        return block_height
    else:
        return None


def get_wallet_balance():
    headers = {"content-type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": "0",
        "method": "get_balance"
    }

    try:
        # get balance
        response = requests.post(cfg.local_rpc_url, headers=headers, data=json.dumps(payload), auth=(cfg.rpc_username, cfg.rpc_password))
        response.raise_for_status()
        result = response.json().get("result")

        if result is None:
            raise ValueError("Failed to get wallet balance")

        xmr_balance = monero_usd_price.calculate_monero_from_atomic_units(atomic_units=result["balance"])
        xmr_unlocked_balance = monero_usd_price.calculate_monero_from_atomic_units(atomic_units=result["unlocked_balance"])

        #print(cfg.xmr_unlocked_balance)

        try:
            usd_balance = format(monero_usd_price.calculate_usd_from_monero(monero_amount=float(xmr_balance), print_price_to_console=False, monero_price=cfg.current_monero_price), ".2f")
        except:
            usd_balance = '---.--'

        #print(usd_balance)

        return xmr_balance, usd_balance, xmr_unlocked_balance

    except Exception as e:
        print(f'get_wallet_balance error: {e}')
        return '--.------------', '---.--'


def get_wallet_balance_in_xmr_minus_amount(amount_in_usd=1):
    # This returns the UNLOCKED monero amount in the wallet minus a USD amount. Default $1. (or 0 if there is less than $1 in the wallet)

    # Get our current balances. Some extra is needed for transaction fees. Less than $0.01, but leaving $1 to future-proof.
    cfg.wallet_balance_xmr, cfg.wallet_balance_usd, cfg.xmr_unlocked_balance = get_wallet_balance()

    # Get amount of Monero that is worth the same USD amount.
    monero_amount_worth_amount_in_usd = monero_usd_price.calculate_monero_from_usd(usd_amount=amount_in_usd, print_price_to_console=False, monero_price=cfg.current_monero_price)

    wallet_balance_minus_amount_usd = cfg.xmr_unlocked_balance - monero_amount_worth_amount_in_usd
    #print(wallet_balance_minus_amount_usd)

    if wallet_balance_minus_amount_usd > 0:
        return wallet_balance_minus_amount_usd
    else:
        return 0


def get_wallet_address():
    headers = {"content-type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": "0",
        "method": "get_address"
    }

    response = requests.post(cfg.local_rpc_url, headers=headers, data=json.dumps(payload), auth=(cfg.rpc_username, cfg.rpc_password))
    response.raise_for_status()
    result = response.json().get("result")

    if result is None:
        raise ValueError("Failed to get wallet address")

    address = result["address"]
    print(address)
    return address


def get_all_transactions():
    headers = {"content-type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": "0",
        "method": "get_transfers",
        "params": {
            "in": True,
            "out": True,
            "pending": True,
            "failed": True,
        }
    }

    response = requests.post(cfg.local_rpc_url, headers=headers, data=json.dumps(payload), auth=(cfg.rpc_username, cfg.rpc_password))
    response_data = response.json()

    #print('WE GOT:')
    #print(response_data)

    if "error" in response_data:
        raise ValueError(f"RPC Error {response_data['error']['code']}: {response_data['error']['message']}")

    result_data = response_data.get("result", {})
    all_transfers = []

    # Iterate over each direction and aggregate the transactions
    for direction in ["in", "out", "pending", "failed"]:
        transactions = result_data.get(direction, [])
        all_transfers.extend(transactions)

    return all_transfers


def filter_transactions(transfers, direction):
    """
    Filter transactions based on the specified direction.

    Parameters:
    - transfers (list of dict): List of transactions.
    - direction (str): The direction to filter by. Options are "in", "out", "pending", "failed"

    Returns:
    - list of dict: Filtered transactions.
    """

    # Use a list comprehension to filter the transactions based on direction
    filtered_transfers = [transaction for transaction in transfers if transaction.get("type") == direction]

    return filtered_transfers


# WALLET "DO SOMETHING" FUNCTIONS ######################################################################################
def send_monero(destination_address, amount, payment_id=None):
    # this needs to measure in atomic units, not xmr, so this converts it.
    amount = monero_usd_price.calculate_atomic_units_from_monero(monero_amount=amount)

    if check_if_monero_wallet_address_is_valid_format(wallet_address=destination_address):
        print('Address is valid. Trying to send Monero')

        # Changes the wallet address to use an integrated wallet address ONLY if a payment id was specified.
        if payment_id:
            # generate the integrated address to pay (an address with the payment ID baked into it)
            destination_address = make_integrated_address(payment_id=payment_id, merchant_public_wallet_address=destination_address)

        headers = {"content-type": "application/json"}
        payload = {
            "jsonrpc": "2.0",
            "id": "0",
            "method": "transfer",
            "params": {
                "destinations": [{"amount": amount, "address": destination_address}],
                "priority": 1,
                "get_tx_key": True
            }
        }

        response = requests.post(cfg.local_rpc_url, headers=headers, data=json.dumps(payload), auth=(cfg.rpc_username, cfg.rpc_password))
        response.raise_for_status()
        result = response.json().get("result")

        print('Trying to send Monero')

        #if result is None:
        #    print('Failed to send Monero transaction')

        response_data = response.json()
        if "result" in response_data:
            print('Monero transaction successful.')
        elif "error" in response_data:
            print(f"Error: {response_data['error']['message']} (Code: {response_data['error']['code']})")
        else:
            print('Unexpected response format.')

    else:
        print('Wallet is not a valid monero wallet address.')


# FUNCTIONS TO FIX #####################################################################################################
# SHOULD UPDATE THIS TO USE RPC BUT IT IS WORKING, SO I HAVE NOT MESSED WITH IT
def create_wallet(wallet_name):  # Using CLI Wallet
    # Remove existing wallet if present
    try:
        os.remove(cfg.wallet_name)
    except:
        pass

    try:
        os.remove(f'{cfg.wallet_name}.keys')
    except:
        pass

    command = f"{cfg.monero_wallet_cli_path} --generate-new-wallet {os.path.join(cfg.wallet_file_path, cfg.wallet_name)} --mnemonic-language English --command exit"
    process = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Sending two newline characters, pressing 'Enter' twice
    process.stdin.write('\n')
    process.stdin.write('\n')
    process.stdin.flush()

    # Getting the output and error messages
    stdout, stderr = process.communicate()
    #print(stdout)
    #print(stderr)

    worked_check = process.returncode
    if worked_check == 0:
        output_text = stdout
        wallet_address = output_text.split('Generated new wallet: ')[1].split('View key: ')[0].strip()
        view_key = output_text.split('View key: ')[1].split('*********************')[0].strip()
        seed = output_text.split(' of your immediate control.')[1].split('********')[0].strip().replace('\n', '')
        print(f'wallet_address: {wallet_address}')
        print(f'view_key: {view_key}')
        print(f'seed: {seed}')

        with open(file=f'{cfg.wallet_name}_seed.txt', mode='a', encoding='utf-8') as f:
            f.write(f'Wallet Address:\n{wallet_address}\nView Key:\n{view_key}\nSeed:\n{seed}\n\nThe above wallet should not be your main source of funds. This is ONLY to be a side account for recording and auto-forwarding payments. If anyone gets access to this seed, they can steal all your funds. Please use responsibly.\n\n\n\n')

        return seed, wallet_address, view_key
    else:
        print(stderr)