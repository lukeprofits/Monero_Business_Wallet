import os
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
from datetime import datetime
import platform
import clipboard

import Swap_Service_Integrations as swap
# EXAMPLE: swap.with_sideshift()



# OVERALL FUNCTIONS ####################################################################################################
def kill_everything():
    global stop_flag

    print('\n\n Please close this terminal window and relaunch the Monero Business Wallet')

    stop_flag.set()  # Stop threads gracefully

    # Kill the program
    current_process = psutil.Process(os.getpid())  # Get the current process ID
    current_process.terminate()  # Terminate the current process and its subprocesses




# MAKE FUNCTIONS #######################################################################################################
def make_payment_id():
    payment_id = ''.join([random.choice('0123456789abcdef') for _ in range(16)])
    return payment_id


def make_integrated_address(payment_id, merchant_public_wallet_address):
    global local_rpc_url

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

    response = requests.post(f"{local_rpc_url}", headers=headers, data=json.dumps(data))
    result = response.json()

    if 'error' in result:
        print('Error:', result['error']['message'])

    else:
        integrated_address = result['result']['integrated_address']
        return integrated_address


def create_wallet(wallet_name):  # Using CLI Wallet
    global monero_wallet_cli_path, wallet_file_path

    # Remove existing wallet if present
    try:
        os.remove(wallet_name)
    except:
        pass

    try:
        os.remove(f'{wallet_name}.keys')
    except:
        pass

    command = f"{monero_wallet_cli_path} --generate-new-wallet {os.path.join(wallet_file_path, wallet_name)} --mnemonic-language English --command exit"
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

        with open(file=f'{wallet_name}_seed.txt', mode='a', encoding='utf-8') as f:
            f.write(f'Wallet Address:\n{wallet_address}\nView Key:\n{view_key}\nSeed:\n{seed}\n\nThe above wallet should not be your main source of funds. This is ONLY to be a side account for recording and auto-forwarding payments. If anyone gets access to this seed, they can steal all your funds. Please use responsibly.\n\n\n\n')

        return seed, wallet_address, view_key
    else:
        print(stderr)


def generate_monero_qr(wallet_address):
    if check_if_monero_wallet_address_is_valid_format(wallet_address):
        # Generate the QR code
        qr = qrcode.QRCode(version=1, box_size=3, border=4)
        qr.add_data("monero:" + wallet_address)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color=monero_orange, back_color=ui_overall_background)
        # Save the image to a file
        filename = "wallet_qr_code.png"
        with open(filename, "wb") as f:
            qr_img.save(f, format="PNG")
        return filename

    else:
        print('Monero Address is not valid')
        return None


# CHECK FUNCTIONS ######################################################################################################
def check_if_wallet_exists():
    global wallet_name

    if not os.path.isfile(f"{wallet_name}.keys") or not os.path.isfile(wallet_name):
        # If either file doesn't exist
        start_block_height = get_current_block_height()
        create_wallet(wallet_name=wallet_name)
        return start_block_height

    else:
        # If both files exist, do nothing
        print('Wallet exists already.')
        return None


def check_if_amount_is_proper_format(amount):
    if type(amount) == int:
        return True

    elif type(amount) == float:
        if round(amount, 12) == amount:
            return True
        else:
            return False

    else:
        return False


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


# RPC FUNCTIONS ########################################################################################################
def kill_monero_wallet_rpc():
    
    global rpc_is_ready
    # Check which platform we are on and get the process list accordingly
    if platform.system() == 'Windows':
        process = subprocess.Popen("tasklist", stdout=subprocess.PIPE)
        rpc_path = 'monero-wallet-rpc.exe'
    else:
        process = subprocess.Popen("ps", stdout=subprocess.PIPE)
        rpc_path = 'monero-wallet-r'
    out, err = process.communicate()

    for line in out.splitlines():
        if rpc_path.encode() in line:
            if platform.system() == 'Windows': # Check if we are on Windows and get the PID accordingly
                pid = int(line.split()[1].decode("utf-8"))
            else:
                pid = int(line.split()[0].decode("utf-8"))
            os.kill(pid, 9)
            print(f"Successfully killed monero-wallet-rpc with PID {pid}")
            rpc_is_ready = False
            break

        else:
            print("monero-wallet-rpc process not found")


def start_local_rpc_server_thread():
    global wallet_name, host, port, rpc_is_ready, start_block_height, rpc_bind_port
    
    if platform.system() == 'Windows':
        cmd = f'monero-wallet-rpc --wallet-file {wallet_name} --password "" --rpc-bind-port {rpc_bind_port} --disable-rpc-login --confirm-external-bind --daemon-host {host} --daemon-port {port}'
    else:
        cmd = f'{os.getcwd()}/monero-wallet-rpc --wallet-file {wallet_name} --password "" --rpc-bind-port {rpc_bind_port} --disable-rpc-login --confirm-external-bind --daemon-host {host} --daemon-port {port}'
    
    if start_block_height:
        command = f'{monero_wallet_cli_path} --wallet-file {os.path.join(wallet_file_path, wallet_name)} --password "" --restore-height {start_block_height} --command exit'
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        blocks_synced = False

        while not blocks_synced:
            output = proc.stdout.readline().decode("utf-8").strip()

            print(f'SYNCING BLOCKS:{output}')

            if "Opened wallet:" in output:
                blocks_synced = True
                break

            if proc.poll() is not None:
                break

    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    while True:
        output = process.stdout.readline().decode("utf-8").strip()
        print(f'RPC STARTING:{output}')

        if "Starting wallet RPC server" in output:
            rpc_is_ready = True
            break

        if process.poll() is not None:
            break


def start_local_rpc_server():
    kill_monero_wallet_rpc()
    rpc_server_thread = threading.Thread(target=start_local_rpc_server_thread)
    rpc_server_thread.start()


def get_current_block_height():
    global daemon_rpc_url

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
    global local_rpc_url, rpc_username, rpc_password

    headers = {"content-type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": "0",
        "method": "get_balance"
    }

    try:
        # get balance
        response = requests.post(local_rpc_url, headers=headers, data=json.dumps(payload), auth=(rpc_username, rpc_password))
        response.raise_for_status()
        result = response.json().get("result")

        if result is None:
            raise ValueError("Failed to get wallet balance")

        xmr_balance = monero_usd_price.calculate_monero_from_atomic_units(atomic_units=result["balance"])
        xmr_unlocked_balance = monero_usd_price.calculate_monero_from_atomic_units(atomic_units=result["unlocked_balance"])

        #print(xmr_unlocked_balance)

        try:
            usd_balance = format(monero_usd_price.calculate_usd_from_monero(float(xmr_balance)), ".2f")
        except:
            usd_balance = '---.--'

        #print(usd_balance)

        return xmr_balance, usd_balance, xmr_unlocked_balance

    except Exception as e:
        print(f'get_wallet_balance error: {e}')
        return '--.------------', '---.--'


def get_wallet_address():
    global local_rpc_url, rpc_username, rpc_password

    headers = {"content-type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": "0",
        "method": "get_address"
    }

    response = requests.post(local_rpc_url, headers=headers, data=json.dumps(payload), auth=(rpc_username, rpc_password))
    response.raise_for_status()
    result = response.json().get("result")

    if result is None:
        raise ValueError("Failed to get wallet address")

    address = result["address"]
    print(address)
    return address


def send_monero(destination_address, amount, payment_id=None):
    global local_rpc_url, rpc_username, rpc_password

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
                #"ring_size": 11,
                "get_tx_key": True
            }
        }

        response = requests.post(local_rpc_url, headers=headers, data=json.dumps(payload), auth=(rpc_username, rpc_password))
        response.raise_for_status()
        result = response.json().get("result")

        print('Sent Monero')

        if result is None:
            print('Failed to send Monero transaction')

    else:
        print('Wallet is not a valid monero wallet address.')


# GUI FUNCTIONS ########################################################################################################
def update_gui_balance():
    global wallet_balance_xmr, wallet_balance_usd, wallet_address

    while not stop_flag.is_set():
        try:
            # Get the wallet balance info
            wallet_balance_xmr, wallet_balance_usd, xmr_unlocked_balance = get_wallet_balance()

            # Update the GUI with the new balance info
            if not wallet_balance_usd == '---.--':
                window['wallet_balance_in_usd'].update(f'        Balance:  ${wallet_balance_usd} USD')

            window['wallet_balance_in_xmr'].update(f'        XMR: {wallet_balance_xmr:.12f}')

            # Wait before updating again
            time.sleep(5)

        except Exception as e:
            print(f'Exception in thread "update_gui_balance: {e}"')


def make_transparent():
    # Make the main window transparent
    window.TKroot.attributes('-alpha', 0.00)


def make_visible():
    # Make the main window transparent
    window.TKroot.attributes('-alpha', 1.00)


def get_random_monero_node():
    response = requests.get('https://monero.fail/')
    tree = html.fromstring(response.content)
    urls = tree.xpath('//span[@class="nodeURL"]/text()')
    random.shuffle(urls)  # mix them up so we get a random one instead of top to bottom.

    for url in urls:
        if '://' in url:
            url = url.split('://')[1]

        if ':' in url:  # make sure that it has the port
            print(url)
            if check_if_node_works(url):
                print(f'WORKS: {url}')
                return url


def refresh_gui():
    global window
    window.close()
    window = create_window()  # recreate the window to refresh the GUI


def make_node_window_layout():
    layout = [[sg.Column([
        [sg.Text("Add A Monero Node:", font=(font, 24), text_color=monero_orange, background_color=ui_overall_background)],
        [sg.Text("     For maximum privacy: Add your own node, or one run by someone you trust     \n", font=(font, 16), text_color=ui_sub_font, background_color=ui_overall_background)],
        [sg.Input(default_text='node.sethforprivacy.com:18089', key='custom_node', justification='center', size=(30, 2), font=(font, 18)), sg.Button('Add Node', key='add_node', font=(font, 12), size=(12, 1), button_color=(ui_button_a_font, ui_button_a))],
        [sg.Text('', font=(font, 4))],
        [sg.Text("...or add a random node (NOT RECOMMENDED)\n", font=(font, 12), text_color=ui_sub_font, background_color=ui_overall_background)],
        [sg.Button('          Add A Random Node          ', key='add_random_node', font=(font, 12), button_color=(ui_button_b_font, ui_button_b))],
        [sg.Text('')],
        [sg.Text("Random nodes pulled from: https://Monero.fail\n", font=(font, 10), text_color=monero_orange, background_color=ui_overall_background)],
        ], element_justification='c', justification='center')
    ]]

    return layout


def make_convert_forward_window_layout():
    layout = [[sg.Column([
        [sg.Text("What Should Be Done With Received Funds?", font=(font, 24), text_color=monero_orange, background_color=ui_overall_background)],
        #[sg.Text("     For maximum privacy: Add your own node, or one run by someone you trust     \n", font=(font, 16), text_color=ui_sub_font, background_color=ui_overall_background)],
        [sg.Text('', font=(font, 4))],
        [sg.Button('   Keep As Monero & Forward To Cold Storage   ', key='forward', font=(font, 12), size=(80, 1), button_color=(ui_button_a_font, ui_button_a))],
        [sg.Text('', font=(font, 1))],
        [sg.Button('       Convert To USD & Send To Exchange      ', key='convert', font=(font, 12), size=(80, 1), button_color=(ui_button_b_font, ui_button_b))],
        [sg.Text('')],
        ], element_justification='c', justification='center')
    ]]

    return layout


def prompt_for_forward_to_cold_storage():
    # Define the window's layout
    layout = [[sg.Column([
        [sg.Text("Enter A Monero Wallet Address To Forward Funds To:", font=(font, 24), text_color=monero_orange, background_color=ui_overall_background)],
        [sg.Text("     This software (a hot wallet) is not a good place to store funds longterm. They should be kept in cold storage.      \n", font=(font, 16), text_color=ui_sub_font, background_color=ui_overall_background)],
        #[sg.Text('', font=(font, 4))],
        [sg.Text("Auto-Forwarding To:", font=(font, 14), background_color=ui_overall_background, text_color=ui_sub_font), sg.Input(size=(102, 1), key="cold_storage_wallet"), sg.Button('   Submit   ', key='submit', font=(font, 12), size=(12, 1), button_color=(ui_button_a_font, ui_button_a))],
        [sg.Text('')],
    ], element_justification='c', justification='center')
    ]]

    # Create the window
    window = sg.Window('Convert Or Forward', layout, keep_on_top=True, no_titlebar=True, grab_anywhere=True)

    # Event loop
    while True:
        event, values = window.read()
        if event == 'submit':
            print('you clicked submmit')
            cold_storage_wallet_address = values["cold_storage_wallet"]
            print(cold_storage_wallet_address)

            if check_if_monero_wallet_address_is_valid_format(cold_storage_wallet_address):
                # write to file
                with open(cold_wallet_filename, 'w') as f:
                    f.write(cold_storage_wallet_address + '\n')
                global cold_wallet
                cold_wallet = cold_storage_wallet_address
            break

        if event == sg.WIN_CLOSED:
            break

    window.close()


def prompt_for_convert_to_usd():
    ###################### LEFT OFF WORKING HERE. COPY/PASTE UPDATING THE DATA IN THIS FUNCTION ###################################################################################################################
    # Define the window's layout
    layout = [[sg.Column([
        [sg.Text("Auto-Convert To USD:", font=(font, 24), text_color=monero_orange, background_color=ui_overall_background)],
        [sg.Text('      Make sure to select the correct coin and network for your wallet, or it will result in loss of funds.      ', font=(font, 12), background_color=ui_overall_background, text_color=ui_sub_font)],
        [sg.Text('')],
        #[sg.Text("     (For lowest fees, use the defaults)      ", font=(font, 16), text_color=ui_sub_font, background_color=ui_overall_background)],
        #[sg.Text('', font=(font, 4))],
        [sg.Text("Convert To Coin:", font=(font, 14), background_color=ui_overall_background, text_color=ui_sub_font), sg.Combo(swap.supported_coins, default_value="USDC", key="coin", font=(font, 12), size=(6, 1)),
         sg.Text("On Network:", font=(font, 14), background_color=ui_overall_background, text_color=ui_sub_font), sg.Combo(swap.supported_networks, default_value="Polygon", key="network", font=(font, 12), size=(16, 1)), sg.Text('     ', background_color=ui_overall_background)],
        [sg.Text('')],
        [sg.Text("     Wallet Address:", font=(font, 14), background_color=ui_overall_background, text_color=ui_sub_font), sg.Input(size=(45, 1), key="wallet", default_text='[ Enter a wallet address ]', justification='center')],
        [sg.Text('')],
        [sg.Button('      Submit      ', key='submit', font=(font, 12), size=(28, 1), button_color=(ui_button_a_font, ui_button_a))],
        [sg.Text('')],
    ], element_justification='c', justification='center')
    ]]

    # Create the window
    window = sg.Window('Convert Or Forward', layout, keep_on_top=True, no_titlebar=True, grab_anywhere=True)

    # Event loop
    while True:
        event, values = window.read()
        if event == 'submit':
            print('you clicked submmit')
            cold_storage_wallet_address = values["wallet"]
            print(cold_storage_wallet_address)

            if check_if_monero_wallet_address_is_valid_format(cold_storage_wallet_address):
                # write to file
                with open(cold_wallet_filename, 'w') as f:
                    f.write(cold_storage_wallet_address + '\n')
                global cold_wallet
                cold_wallet = cold_storage_wallet_address
            break

        if event == sg.WIN_CLOSED:
            break

    window.close()


def prompt_for_convert_forward_selection():
    # Define the window's layout
    layout = make_convert_forward_window_layout()

    # Create the window
    window = sg.Window('Convert Or Forward', layout, keep_on_top=True, no_titlebar=True, grab_anywhere=True)

    # Event loop
    while True:
        event, values = window.read()
        if event == 'forward':
            print('you clicked forward')
            prompt_for_forward_to_cold_storage()
            break

        elif event == 'convert':
            print('you clicked convert')
            prompt_for_convert_to_usd()
            break

        if event == sg.WIN_CLOSED:
            break

    window.close()



# THEME VARIABLES ######################################################################################################

# Hex Colors
ui_title_bar = '#222222'
ui_overall_background = '#1D1D1D'
ui_button_a = '#00A9AF'  # Updated to be a blue-green with grey
ui_button_a_font = '#F0FFFF'
ui_button_b = '#716F74'
ui_button_b_font = '#FFF9FB'
ui_main_font = '#F4F6EE'
ui_sub_font = '#A7B2C7'
ui_lines = '#696563'
ui_outline = '#2E2E2E'
ui_barely_visible = '#373737'
ui_regular = '#FCFCFC'
monero_grey = '#4c4c4c'
monero_orange = '#00F6FF'  # Updated to be a blue-green
monero_white = '#FFFFFF'
monero_grayscale_top = '#7D7D7D'
monero_grayscale_bottom = '#505050'

# Set Theme
icon = 'icon.ico'
font = 'Nunito Sans'
title_bar_text = ''
sg.theme('DarkGrey2')
# Modify the colors you want to change
sg.theme_background_color(ui_overall_background)  # MAIN BACKGROUND COLOR
sg.theme_button_color((ui_button_a_font, ui_button_a))  # whiteish, blackish
sg.theme_text_color(monero_orange)  # HEADING TEXT AND DIVIDERS
main_text = ui_main_font  # this lets separators be orange but text stay white
subscription_text_color = ui_sub_font
subscription_background_color = ui_overall_background  # ui_title_bar
sg.theme_text_element_background_color(ui_title_bar)  # Text Heading Boxes
sg.theme_element_background_color(ui_title_bar)  # subscriptions & transactions box color
sg.theme_element_text_color(ui_sub_font)  # My Subscriptions Text Color
sg.theme_input_background_color(ui_title_bar)
sg.theme_input_text_color(monero_orange)
sg.theme_border_width(0)
sg.theme_slider_border_width(0)

# VARIABLES ############################################################################################################
if platform.system() == 'Windows':
    monero_wallet_cli_path = "" + 'monero-wallet-cli.exe'  # Update path to the location of the monero-wallet-cli executable if your on WINDOWS
else:
    monero_wallet_cli_path = os.getcwd() + '/' + 'monero-wallet-cli'  # Update path to the location of the monero-wallet-cli executable if your on other platforms
wallet_name = "business_wallet"
if platform.system() == 'Windows':
    wallet_file_path = ""
else:
    wallet_file_path = f'{os.getcwd()}/'  # Update this path to the location where you want to save the wallet file

monero_transactions_file = 'monero_transactions.csv'
rpc_bind_port = '18088'
local_rpc_url = f"http://127.0.0.1:{rpc_bind_port}/json_rpc"
rpc_username = "monero"
rpc_password = "monero"

stop_flag = threading.Event()  # Define a flag to indicate if the threads should stop

welcome_popup_text = '''
           Welcome to the Monero Business Wallet!

We're thrilled that you've chosen to use our Free and Open Source Software (FOSS). Before you get started, there are a few important things you should know:

1. Monero Business Wallet is currently in alpha. Your feedback is valuable to us in making this software better. Please let us know if you encounter any issues or, if you are a developer, help resolve them! All the code is on GitHub.

2. Monero Business Wallet is an internet-connected hot wallet, its security is only as robust as your computer's is.

3. By using this software, you understand and agree that you're doing so at your own risk. The developers cannot be held responsible for any lost funds.

Enjoy using the Monero Business Wallet, thank you for your support, and if you are a Python developer, please consider helping us improve the project!

https://github.com/lukeprofits/Monero_Business_Wallet
'''

# ADD DAEMON/NODE ######################################################################################################
node_filename = "node_to_use.txt"

if os.path.exists(node_filename):
    with open(node_filename, 'r') as f:
        node = f.readline().strip()  # read first line into 'node'
else:
    # welcome popup
    sg.popup(welcome_popup_text, icon=icon, no_titlebar=True, background_color=ui_overall_background, grab_anywhere=True)

    # Define the window's layout
    layout = make_node_window_layout()

    # Create the window
    window = sg.Window('Node Input', layout, keep_on_top=True, no_titlebar=True, grab_anywhere=True)

    # Event loop
    while True:
        event, values = window.read()
        if event == 'add_node':
            node = values['custom_node']

            if '://' in node:
                node = node.split('://')[1]

            print(node)

            if check_if_node_works(node):
                window['custom_node'].update(value="Success!")

                # Save the node to the file
                with open(node_filename, 'w') as f:
                    f.write(node + '\n')
                break

            else:
                window['custom_node'].update(value="Node did not respond. Try Another.")

        elif event == 'add_random_node':
            print('Adding a random node. Please wait. \nThe software will seem to be frozen until a node is found.')
            node = get_random_monero_node()
            # Save the node to the file
            with open(node_filename, 'w') as f:
                f.write(node + '\n')
            break

        if event == sg.WIN_CLOSED:
            break

    window.close()

host = node.split(':')[0]
port = node.split(':')[1]

daemon_rpc_url = f"http://{host}:{port}/json_rpc"
# END NODE SECTION


# CONVERT OR FORWARD SECTION
# Note: cold_storage takes priority over convert. If both are specified, it should forward to cold storage only.
cold_wallet_filename = 'cold_wallet.txt'
convert_wallet_filename = 'conversion_wallet.txt'
cold_wallet = ''
convert_wallet = ''
convert_coin = ''
convert_network = ''


convert = False
forward = False

if os.path.exists(cold_wallet_filename):
    with open(cold_wallet_filename, 'r') as f:
        cold_wallet = f.readline().strip()  # read first line into 'node'
        if check_if_monero_wallet_address_is_valid_format(cold_wallet):
            forward = True

elif os.path.exists(convert_wallet_filename):
    with open(convert_wallet_filename, 'r') as f:
        data = f.readline().strip()  # read first line into 'node'
        # Should be in this format: wallet_address:coin_ticker:network_name
        data = data.split(':')
        convert_wallet = data[0]
        convert_coin = data[1]
        convert_network = data[2]
        if convert_wallet and convert_coin and convert_network:
            convert = True
            #forward_wallet = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'
            #forward_wallet_type = 'USDC'
            #network = 'Polygon'

if not forward and not convert:
    prompt_for_convert_forward_selection()
# END CONVERT OR FORWARD SECTION


# ADD A WALLET #########################################################################################################



# START PREREQUISITES ##################################################################################################
start_block_height = check_if_wallet_exists()  # auto-create one if it doesn't exist

rpc_is_ready = False
start_local_rpc_server()

# Set up the PySimpleGUI "please wait" popup window
layout = [
    [sg.Text("Please Wait: Monero RPC Server Is Starting", key="wait_text", font=(font, 18), background_color=ui_overall_background)],
    [sg.Text("                                   This may take a few minutes on first launch.", key="wait_text2", font=(font, 10), background_color=ui_overall_background)]
          ]

window = sg.Window("Waiting", layout, finalize=True, keep_on_top=True, no_titlebar=True, grab_anywhere=True)

while not rpc_is_ready:
    # Check for window events
    event, values = window.read(timeout=100)  # Read with a timeout so the window is updated

print('\n\nRPC Server has started')

wallet_balance_xmr = '--.------------'
wallet_balance_usd = '---.--'
wallet_address = get_wallet_address()

try:
    wallet_balance_xmr, wallet_balance_usd, xmr_unlocked_balance = get_wallet_balance()
except:
    pass


# GUI LAYOUT ###########################################################################################################
def create_window():  # Creates the main window and returns it

    # Define the window layout
    layout = [
        [sg.Text("Monero Business Wallet", font=(font, 24), expand_x=True, justification='center', relief=sg.RELIEF_RIDGE, size=(None, 1), pad=(0, 0), text_color=main_text, background_color=ui_overall_background)],
        [sg.Text("Incoming payments will be recorded and forwarded automatically if the wallet remains open", font=(font, 10), expand_x=True, justification='center', background_color=ui_overall_background, pad=(0, 0))],
        [sg.Text("", font=(font, 8))],
            [
                sg.Column(
                    [
                        ########
                        [sg.Text(f'        Balance:  ${wallet_balance_usd} USD', size=(25, 1), font=(font, 18), key='wallet_balance_in_usd', text_color=ui_sub_font, background_color=ui_overall_background)],
                        [sg.Text(f'        XMR: {wallet_balance_xmr}', size=(25, 1), font=(font, 18), key='wallet_balance_in_xmr', background_color=ui_overall_background)],
                        [sg.Text('')],
                        [sg.Button("   Copy Wallet Address   ", size=(24, 1), key='copy_address', pad=(10, 10))],
                        ########

                    ], element_justification='center', expand_x=True, expand_y=True
                ),
                #sg.VerticalSeparator(pad=(0, 10)),
                #sg.Column(
                    #[
                        ########
                        #[sg.Text('Deposit XMR:', size=(20, 1), font=(font, 18), justification='center', text_color=ui_sub_font, background_color=ui_overall_background)],
                        #[sg.Column([
                        #    [sg.Image(generate_monero_qr(wallet_address), size=(147, 147), key='qr_code', pad=(10, 0))],  # Placeholder for the QR code image
                        #    ],
                        #    element_justification='center', pad=(0, 0))],
                        ########
                    #], expand_x=True, expand_y=True, element_justification='c'
                #)
            ],
            [sg.Text("", font=(font, 8), expand_x=True, justification='center', size=(None, 1), pad=(0, 0), text_color=main_text, background_color=ui_overall_background)],

            ########
            [sg.Column([
                [sg.Text(f'      Forwarding To:', size=(15, 1), font=(font, 14), pad=(10, 10), text_color=ui_sub_font, background_color=ui_overall_background),
                sg.Text(f'{forward_wallet} ({forward_wallet_type})      ', size=(48, 1), font=(font, 14), pad=(10, 10), text_color=monero_orange, background_color=ui_overall_background),
                #sg.InputText(default_text='[ Enter a wallet address ]', key='withdraw_to_wallet', pad=(10, 10), justification='center', size=(46, 1)),
                #sg.InputText(default_text=' [ Enter an amount ]', key='withdraw_amount', pad=(10, 10), justification='center', size=(20, 1)),
                #sg.Button("Send", size=(8, 1), key='send', pad=(10, 10), button_color=(ui_button_b_font, ui_button_b))
                ]], element_justification='c', justification='center'),
                sg.Text('', pad=(15, 15))],
            ########

            [sg.Text("", font=(font, 8), expand_x=True, justification='center', size=(None, 1), pad=(0, 0), text_color=main_text, background_color=ui_overall_background)],
    ]
    if platform.system() == 'Darwin':
        return sg.Window('Monero Business Wallet', layout, margins=(20, 20), titlebar_icon='', titlebar_background_color=ui_overall_background, use_custom_titlebar=False, grab_anywhere=True, icon="./icon.png", finalize=True)
    elif platform.system() == 'Linux':
        return sg.Window('Monero Business Wallet', layout, margins=(20, 20), titlebar_icon='', titlebar_background_color=ui_overall_background, use_custom_titlebar=False, grab_anywhere=True, icon="./icon.png", finalize=True)
    else:
        return sg.Window(title_bar_text, layout, margins=(20, 20), titlebar_icon='', titlebar_background_color=ui_overall_background, use_custom_titlebar=True, grab_anywhere=True, icon=icon, finalize=True)


window.close()

# Start a thread to update balance every 5 seconds
threading.Thread(target=update_gui_balance).start()

# Create the window
window = create_window()

# MAIN EVENT LOOP ######################################################################################################
while True:
    event, values = window.read()

    if event == sg.WIN_CLOSED:
        break

    elif event == 'copy_address':
        clipboard.copy(wallet_address)
        print(f'COPIED: {wallet_address}')

    elif event == 'send':
        try:
            withdraw_to_wallet = values['withdraw_to_wallet']
            if values['withdraw_amount'] == '':
                withdraw_amount = None
            else:
                withdraw_amount = float(values['withdraw_amount'])
            print(withdraw_to_wallet)
            print(withdraw_amount)
            if withdraw_amount == None:
                choice = sg.popup(f"Are you sure you want to send all your XMR to this address?\n", text_color=ui_sub_font, title='', custom_text=("    Yes, I am sure!    ", "    No, CANCEL!    "), no_titlebar=True, background_color=ui_title_bar, modal=True, grab_anywhere=True, icon=icon)
                if "No, CANCEL!" in choice:
                    print("Cancelled wallet sweep!")
                    pass
                elif "Yes, I am sure!" in choice:
                    send_monero(destination_address=withdraw_to_wallet, amount=xmr_unlocked_balance)
                    print("The wallet has been swept!")
            else:
                send_monero(destination_address=withdraw_to_wallet, amount=withdraw_amount)

        except Exception as e:
            print(e)
            print('failed to send')
            window['withdraw_to_wallet'].update('Error: Enter a valid wallet address and XMR amount.')

                
window.close()
