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

import swap_functions as swap
import wallet_functions as wallet
import gui_functions as gui
import config as cfg

# OPEN STUFF FUNCTIONS #################################################################################################
def start_local_rpc_server_thread():
    if platform.system() == 'Windows':
        cmd = f'monero-wallet-rpc --wallet-file {cfg.wallet_name} --password "" --rpc-bind-port {cfg.rpc_bind_port} --disable-rpc-login --confirm-external-bind --daemon-host {host} --daemon-port {port}'
    else:
        cmd = f'{os.getcwd()}/monero-wallet-rpc --wallet-file {cfg.wallet_name} --password "" --rpc-bind-port {cfg.rpc_bind_port} --disable-rpc-login --confirm-external-bind --daemon-host {host} --daemon-port {port}'

    if start_block_height:
        command = f'{cfg.monero_wallet_cli_path} --wallet-file {os.path.join(cfg.wallet_file_path, cfg.wallet_name)} --password "" --restore-height {start_block_height} --command exit'
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
            cfg.rpc_is_ready = True
            break

        if process.poll() is not None:
            break


# CLOSE STUFF FUNCTIONS ################################################################################################
def kill_everything():
    print('\n\n Please close this terminal window and relaunch the Monero Business Wallet')

    cfg.stop_flag.set()  # Stop threads gracefully

    # Kill the program
    current_process = psutil.Process(os.getpid())  # Get the current process ID
    current_process.terminate()  # Terminate the current process and its subprocesses


def kill_monero_wallet_rpc():
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
            if platform.system() == 'Windows':  # Check if we are on Windows and get the PID accordingly
                pid = int(line.split()[1].decode("utf-8"))
            else:
                pid = int(line.split()[0].decode("utf-8"))
            os.kill(pid, 9)
            print(f"Successfully killed monero-wallet-rpc with PID {pid}")
            cfg.rpc_is_ready = False
            break

        else:
            print("monero-wallet-rpc process not found")


# OTHER RANDOM FUNCTIONS ###############################################################################################
def convert_or_forward():
    # I'm super freaking tired. I think this works but review it later and delete this comment assuming it does.
    if cfg.convert:
        swap_info = swap.with_sideshift(shift_to_coin=cfg.convert_coin, to_wallet=cfg.convert_wallet, on_network=cfg.convert_network, amount_to_convert=xmr_wallet_balance_to_forward)
        if swap_info:
            print(swap_info)
            write_swap_to_csv(swap_info=swap_info)  # Maybe also add a thing to include the IP we used.
            # Optionally add a "check for success" but not sure if there is really a point.

        else:
            print('There was a problem, so we did not swap anything.')

    elif cfg.forward:
        # Transfer what we have
        wallet.send_monero(destination_address=cfg.cold_wallet, amount=xmr_wallet_balance_to_forward)
        pass

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
            if wallet.check_if_node_works(url):
                print(f'WORKS: {url}')
                return url


def make_payment_id():  # ADD TO MoneroSub pip package at some point
    payment_id = ''.join([random.choice('0123456789abcdef') for _ in range(16)])
    return payment_id


def generate_monero_qr(wallet_address):
    if wallet.check_if_monero_wallet_address_is_valid_format(wallet_address):
        # Generate the QR code
        qr = qrcode.QRCode(version=1, box_size=3, border=4)
        qr.add_data("monero:" + wallet_address)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color=cfg.monero_orange, back_color=cfg.ui_overall_background)
        # Save the image to a file
        filename = "wallet_qr_code.png"
        with open(filename, "wb") as f:
            qr_img.save(f, format="PNG")
        return filename

    else:
        print('Monero Address is not valid')
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


# WRITE FILE FUNCTIONS #################################################################################################
def write_swap_to_csv(swap_info, filename=cfg.swap_file):
    # Check if file exists
    file_exists = os.path.isfile(filename)

    # If file doesn't exist, write headers first
    if not file_exists:
        with open(filename, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # Add 'timestamp' to the beginning of the headers
            headers = ['timestamp'] + list(swap_info.keys())
            writer.writerow(headers)

    # Write (or append) the data
    with open(filename, 'a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        # Get current timestamp in RFC3339 format
        current_timestamp = datetime.now(timezone.utc).isoformat()
        # Add timestamp to the beginning of the data
        data = [current_timestamp] + list(swap_info.values())
        writer.writerow(data)


def write_transactions_to_csv(transactions, filename=cfg.received_transactions_file):
    # List to store existing transactions
    existing_txids = []

    # Column names as variables (so they can be changed in one place)
    transaction_id_name = 'Transaction ID'
    usd_amount_name = 'USD Amount'
    xmr_amount_name = 'XMR Amount'
    atomic_units_amount_name = 'Atomic Units Amount'
    timestamp_name = 'Timestamp'
    wallet_address_name = 'Wallet Address'

    # Columns to exclude
    exclude_columns = ["amounts", "double_spend_seen", "fee", "locked", "subaddr_index", "subaddr_indices", "suggested_confirmations_threshold", "unlock_time"]

    # Columns to rename
    rename_columns = {
        "amount": atomic_units_amount_name,
        "confirmations": "Confirmations When Recorded",
        "height": "Block Height",
        "timestamp": timestamp_name,
        "type": "Payment Direction",
        "payment_id": "Payment ID",
        "note": "Note",
        "txid": transaction_id_name,
        "address": wallet_address_name,
    }

    # Order of columns
    desired_order = [timestamp_name, usd_amount_name, xmr_amount_name, atomic_units_amount_name, "Payment ID", "Note", "Transaction ID", "Confirmations When Recorded", wallet_address_name]

    # If the file exists, read it to get the existing txids
    if os.path.exists(filename):
        with open(filename, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                existing_txids.append(row[transaction_id_name])

    # Filter transactions based on whether their transaction ID is already recorded
    new_transactions = [tx for tx in transactions if tx["txid"] not in existing_txids]

    # Remove unwanted columns and rename columns as necessary
    for tx in new_transactions:
        for col in exclude_columns:
            if col in tx:
                del tx[col]
        for old_name, new_name in rename_columns.items():
            if old_name in tx:
                tx[new_name] = tx.pop(old_name)

        # Do Currency Conversions
        tx[xmr_amount_name] = monero_usd_price.calculate_monero_from_atomic_units(atomic_units=tx[atomic_units_amount_name])
        tx[usd_amount_name] = monero_usd_price.calculate_usd_from_atomic_units(atomic_units=tx[atomic_units_amount_name], print_price_to_console=False, monero_price=cfg.current_monero_price,)

        # Convert from a POSIX timestamp to a human-readable format
        tx[timestamp_name] = datetime.fromtimestamp(tx[timestamp_name]).strftime('%Y-%m-%d %H:%M:%S')

    # Sort new_transactions based on timestamp
    new_transactions.sort(key=lambda x: datetime.strptime(x[timestamp_name], '%Y-%m-%d %H:%M:%S'))

    # Write the new transactions to the CSV
    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=desired_order)

        # If the CSV was empty, write the headers
        if file.tell() == 0:
            writer.writeheader()

        for tx in new_transactions:
            # Use the desired order to write rows
            ordered_tx = {col: tx[col] for col in desired_order}
            writer.writerow(ordered_tx)

    print(f'Wrote to {filename}')


# LOOPING THREADS ######################################################################################################
def check_for_new_transactions():
    while not cfg.stop_flag.is_set():
        try:
            cfg.current_monero_price = monero_usd_price.median_price(print_price_to_console=False)
            print(f'Got current Monero price: {str(cfg.current_monero_price)}')

            # Get All Transactions
            transactions = wallet.get_all_transactions()

            # Filter to incoming/outgoing
            incoming_filtered_tx = wallet.filter_transactions(transfers=transactions, direction='in')
            outgoing_filtered_tx = wallet.filter_transactions(transfers=transactions, direction='out')

            # Write new ones to csv
            write_transactions_to_csv(transactions=incoming_filtered_tx, filename=cfg.received_transactions_file)
            write_transactions_to_csv(transactions=outgoing_filtered_tx, filename=cfg.sent_transactions_file)
            print('Wrote new transactions to csv files.')

            # Wait 2 minutes (Monero has a 2-minute block time).
            time.sleep(120)

        except Exception as e:
            print(f'Exception in thread "check_for_new_transactions: {e}"')


def autoforward_monero():
    while not cfg.stop_flag.is_set():
        try:
            # See if our balance is over usd_amount_to_leave_in_wallet_for_tx_fees
            xmr_wallet_balance_to_forward = wallet.get_wallet_balance_in_xmr_minus_amount(amount_in_usd=cfg.usd_amount_to_leave_in_wallet_for_tx_fees)

            if xmr_wallet_balance_to_forward > 0:
                # DO "wait until over $100"
                print(f'THIS IS WHAT WAIT FOR BALANCE IS: {str(window["wait_for_balance"].get())}')
                if window['wait_for_balance'].get():
                    # Make sure we have over $100
                    if wallet.get_wallet_balance_in_xmr_minus_amount(amount_in_usd=(100 + cfg.usd_amount_to_leave_in_wallet_for_tx_fees)):  # Evaluates to False if we don't have enough
                        # Are we converting, or forwarding?
                        convert_or_forward()

                    else:
                        print('Balance not yet above forwarding limit.')

                # DO NOT "wait until over $100"
                else:
                    # Are we converting, or forwarding?
                    convert_or_forward()

            # Not enough to bother transferring
            else:
                print('No balance worth forwarding.')

            # Wait 2 minutes (Monero has a 2-minute block time).
            time.sleep(120)

        except Exception as e:
            print(f'Exception in thread "check_for_new_transactions: {e}"')


# GUI FUNCTIONS (NOT LAYOUT) ########################################################################################################
def refresh_gui():
    global window
    window.close()
    window = create_main_window()  # recreate the window to refresh the GUI


def make_transparent():
    # Make the main window transparent
    window.TKroot.attributes('-alpha', 0.00)


def make_visible():
    # Make the main window transparent
    window.TKroot.attributes('-alpha', 1.00)


def update_gui_balance():
    while not cfg.stop_flag.is_set():
        try:
            # Get the wallet balance info
            cfg.wallet_balance_xmr, cfg.wallet_balance_usd, cfg.xmr_unlocked_balance = wallet.get_wallet_balance()
            #print(cfg.wallet_balance_usd)
            # Update the GUI with the new balance info
            if not cfg.wallet_balance_usd == '---.--':
                window['wallet_balance_in_usd'].update(f'        Balance:  ${cfg.wallet_balance_usd} USD')

            window['wallet_balance_in_xmr'].update(f'        XMR: {cfg.wallet_balance_xmr:.12f}')

            # Wait before updating again
            time.sleep(5)

        except Exception as e:
            print(f'Exception in thread "update_gui_balance: {e}"')


# GUI LAYOUT FUNCTIONS #################################################################################################
def make_layout_part_for_forwarding_to():
    if cfg.convert:  # Conversion Wallet
        return [sg.Text(f'      Forwarding To:', size=(15, 1), font=(cfg.font, 14), pad=(10, 0), text_color=cfg.ui_sub_font, background_color=cfg.ui_overall_background), sg.Text(f'{cfg.convert_wallet}', size=(48, 1), font=(cfg.font, 14), pad=(10, 0), text_color=cfg.monero_orange, background_color=cfg.ui_overall_background)]
    elif cfg.forward:  # Cold Storage
        return [sg.Text(f'      Forwarding To:', size=(15, 1), font=(cfg.font, 14), pad=(10, 0), text_color=cfg.ui_sub_font, background_color=cfg.ui_overall_background), sg.Text(f'{cfg.cold_wallet}', size=(90, 1), font=(cfg.font, 10), pad=(10, 0), text_color=cfg.monero_orange, background_color=cfg.ui_overall_background)]


def make_layout_part_for_forwarding_to_2():
    if cfg.convert:  # Conversion Wallet
        return [sg.Text(f'                        ({cfg.convert_coin} on {cfg.convert_network} network)', size=(48, 1), font=(cfg.font, 14), text_color=cfg.monero_orange, background_color=cfg.ui_overall_background, justification='c')]
    else:
        return []

def make_please_wait_popup():
    layout = [
        [sg.Text("Please Wait: Monero RPC Server Is Starting", key="wait_text", font=(cfg.font, 18), background_color=cfg.ui_overall_background)],
        [sg.Text("                                   This may take a few minutes on first launch.", key="wait_text2", font=(cfg.font, 10), background_color=cfg.ui_overall_background)]
    ]
    return layout

def make_node_window_layout():
    layout = [[sg.Column([
        [sg.Text("Add A Monero Node:", font=(cfg.font, 24), text_color=cfg.monero_orange, background_color=cfg.ui_overall_background)],
        [sg.Text("     For maximum privacy: Add your own node, or one run by someone you trust     \n", font=(cfg.font, 16), text_color=cfg.ui_sub_font, background_color=cfg.ui_overall_background)],
        [sg.Input(default_text='node.sethforprivacy.com:18089', key='custom_node', justification='center', size=(30, 2), font=(cfg.font, 18)), sg.Button('Add Node', key='add_node', font=(cfg.font, 12), size=(12, 1), button_color=(cfg.ui_button_a_font, cfg.ui_button_a))],
        [sg.Text('', font=(cfg.font, 4))],
        [sg.Text("...or add a random node (NOT RECOMMENDED)\n", font=(cfg.font, 12), text_color=cfg.ui_sub_font, background_color=cfg.ui_overall_background)],
        [sg.Button('          Add A Random Node          ', key='add_random_node', font=(cfg.font, 12), button_color=(cfg.ui_button_b_font, cfg.ui_button_b))],
        [sg.Text('')],
        [sg.Text("Random nodes pulled from: https://Monero.fail\n", font=(cfg.font, 10), text_color=cfg.monero_orange, background_color=cfg.ui_overall_background)],
        ], element_justification='c', justification='center')
    ]]

    return layout


def make_convert_forward_window_layout():
    layout = [[sg.Column([
        [sg.Text("What Should Be Done With Received Funds?", font=(cfg.font, 24), text_color=cfg.monero_orange, background_color=cfg.ui_overall_background)],
        #[sg.Text("     For maximum privacy: Add your own node, or one run by someone you trust     \n", font=(cfg.font, 16), text_color=cfg.ui_sub_font, background_color=cfg.ui_overall_background)],
        [sg.Text('', font=(cfg.font, 4))],
        [sg.Button('   Keep As Monero & Forward To Cold Storage   ', key='forward', font=(cfg.font, 12), size=(80, 1), button_color=(cfg.ui_button_a_font, cfg.ui_button_a))],
        [sg.Text('', font=(cfg.font, 1))],
        [sg.Button('       Convert To USD & Send To Exchange      ', key='convert', font=(cfg.font, 12), size=(80, 1), button_color=(cfg.ui_button_b_font, cfg.ui_button_b))],
        [sg.Text('')],
        ], element_justification='c', justification='center')
    ]]

    return layout


def prompt_for_forward_to_cold_storage():
    # Define the window's layout
    layout = [[sg.Column([
        [sg.Text("Enter A Monero Wallet Address To Forward Funds To:", font=(cfg.font, 24), text_color=cfg.monero_orange, background_color=cfg.ui_overall_background)],
        [sg.Text("     This software (a hot wallet) is not a good place to store funds longterm. They should be kept in cold storage.      \n", font=(cfg.font, 16), text_color=cfg.ui_sub_font, background_color=cfg.ui_overall_background)],
        #[sg.Text('', font=(cfg.font, 4))],
        [sg.Text("Auto-Forwarding To:", font=(cfg.font, 14), background_color=cfg.ui_overall_background, text_color=cfg.ui_sub_font), sg.Input(size=(102, 1), key="cold_storage_wallet"), sg.Button('   Submit   ', key='submit', font=(cfg.font, 12), size=(12, 1), button_color=(cfg.ui_button_a_font, cfg.ui_button_a))],
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

            if wallet.check_if_monero_wallet_address_is_valid_format(cold_storage_wallet_address):
                # write to file
                with open(cfg.cold_wallet_filename, 'w') as f:
                    f.write(cold_storage_wallet_address + '\n')

                cfg.cold_wallet = cold_storage_wallet_address
            break

        if event == sg.WIN_CLOSED:
            break

    window.close()


def prompt_for_convert_to_usd():
    ###################### LEFT OFF WORKING HERE. COPY/PASTE UPDATING THE DATA IN THIS FUNCTION ###################################################################################################################
    # Define the window's layout
    layout = [[sg.Column([
        [sg.Text("Auto-Convert To USD:", font=(cfg.font, 24), text_color=cfg.monero_orange, background_color=cfg.ui_overall_background)],
        [sg.Text('      Make sure to select the correct coin and network for your wallet, or it will result in loss of funds.      ', font=(cfg.font, 12), background_color=cfg.ui_overall_background, text_color=cfg.ui_sub_font)],
        [sg.Text('')],
        #[sg.Text("     (For lowest fees, use the defaults)      ", font=(cfg.font, 16), text_color=cfg.ui_sub_font, background_color=cfg.ui_overall_background)],
        #[sg.Text('', font=(cfg.font, 4))],
        [sg.Text("Convert To Coin:", font=(cfg.font, 14), background_color=cfg.ui_overall_background, text_color=cfg.ui_sub_font), sg.Combo(swap.supported_coins, default_value="USDC", key="coin", font=(cfg.font, 12), size=(6, 1)),
         sg.Text("On Network:", font=(cfg.font, 14), background_color=cfg.ui_overall_background, text_color=cfg.ui_sub_font), sg.Combo(swap.supported_networks, default_value="Polygon", key="network", font=(cfg.font, 12), size=(16, 1)), sg.Text('     ', background_color=cfg.ui_overall_background)],
        [sg.Text('')],
        [sg.Text("     Wallet Address:", font=(cfg.font, 14), background_color=cfg.ui_overall_background, text_color=cfg.ui_sub_font), sg.Input(size=(45, 1), key="wallet", default_text='[ Enter a wallet address ]', justification='center')],
        [sg.Text('')],
        [sg.Button('      Submit      ', key='submit', font=(cfg.font, 12), size=(28, 1), button_color=(cfg.ui_button_a_font, cfg.ui_button_a))],
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
            swap_coin = values["coin"]
            swap_network = values["network"]
            swap_wallet_address = values["wallet"]

            swap_info = {
                "coin": swap_coin,
                "network": swap_network,
                "wallet": swap_wallet_address
            }
            swap_info = json.dumps(swap_info)
            print(swap_info)

            # write to file
            with open(cfg.convert_wallet_filename, 'w') as f:
                f.write(swap_info + '\n')
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


def create_main_window():  # Creates the main window and returns it
    layout = [
        [sg.Text("Monero Business Wallet", font=(cfg.font, 24), expand_x=True, justification='center', relief=sg.RELIEF_RIDGE, size=(None, 1), pad=(0, 0), text_color=cfg.main_text, background_color=cfg.ui_overall_background)],
        [sg.Text("Incoming payments will be recorded and forwarded automatically if the wallet remains open", font=(cfg.font, 10), expand_x=True, justification='center', background_color=cfg.ui_overall_background, pad=(0, 0))],
        [sg.Text("", font=(cfg.font, 8))],
            [
                sg.Column(
                    [
                        ########
                        [sg.Text(f'        Balance:  ${cfg.wallet_balance_usd} USD', size=(25, 1), font=(cfg.font, 18), key='wallet_balance_in_usd', text_color=cfg.ui_sub_font, background_color=cfg.ui_overall_background)],
                        [sg.Text(f'        XMR: {cfg.wallet_balance_xmr}', size=(25, 1), font=(cfg.font, 18), key='wallet_balance_in_xmr', background_color=cfg.ui_overall_background)],
                        [sg.Text('')],
                        [sg.HorizontalSeparator(pad=(90, 0))],
                        [sg.Text('')],
                        [sg.Text('               ', background_color=cfg.ui_overall_background), sg.Checkbox('Forward As Multiple Random Amounts', key='random_amounts', default=True, size=40, background_color=cfg.ui_overall_background)],
                        [sg.Text('               ', background_color=cfg.ui_overall_background), sg.Checkbox('Use Random Time Delay Before Forwarding', key='random_delay', default=True, size=40, background_color=cfg.ui_overall_background)],
                        [sg.Text('               ', background_color=cfg.ui_overall_background), sg.Checkbox('Do Not Forward Until Balance Is Over $100', key='wait_for_balance', default=False, size=40, background_color=cfg.ui_overall_background)],
                        #[sg.Button("   Copy Wallet Address   ", size=(24, 1), key='copy_address', pad=(10, 10))],
                        ########

                    ], element_justification='center', expand_x=True, expand_y=True
                ),
                sg.VerticalSeparator(pad=(0, 10)),
                sg.Column(
                    [
                        ########
                        [sg.Text('Deposit XMR:', size=(20, 1), font=(cfg.font, 18), justification='center', text_color=cfg.ui_sub_font, background_color=cfg.ui_overall_background)],
                        [sg.Column([
                            [sg.Image(generate_monero_qr(wallet_address), size=(147, 147), key='qr_code', pad=(10, 0))],  # Placeholder for the QR code image
                            [sg.Button("Copy Address", size=(16, 1), key='copy_address', pad=(10, 10))],
                            ],
                            element_justification='center', pad=(0, 0))],
                        ########
                    ], expand_x=True, expand_y=True, element_justification='c'
                )
            ],
            [sg.Text("", font=(cfg.font, 8), expand_x=True, justification='center', size=(None, 1), pad=(0, 0), text_color=cfg.main_text, background_color=cfg.ui_overall_background)],

            ########
            [sg.Column([
                make_layout_part_for_forwarding_to(),
                make_layout_part_for_forwarding_to_2()
                #[sg.InputText(default_text='[ Enter a wallet address ]', key='withdraw_to_wallet', pad=(10, 10), justification='center', size=(46, 1)),
                #sg.InputText(default_text=' [ Enter an amount ]', key='withdraw_amount', pad=(10, 10), justification='center', size=(20, 1)),
                #sg.Button("Send", size=(8, 1), key='send', pad=(10, 10), button_color=(cfg.ui_button_b_font, cfg.ui_button_b))
                #],
            ], element_justification='c', justification='center'),
                sg.Text('', pad=(15, 5))],
            ########

            [sg.Text("", font=(cfg.font, 8), expand_x=True, justification='center', size=(None, 1), pad=(0, 0), text_color=cfg.main_text, background_color=cfg.ui_overall_background)],
    ]
    if platform.system() == 'Darwin':
        return sg.Window('Monero Business Wallet', layout, margins=(20, 20), titlebar_icon='', titlebar_background_color=cfg.ui_overall_background, use_custom_titlebar=False, grab_anywhere=True, icon="./icon.png", finalize=True)
    elif platform.system() == 'Linux':
        return sg.Window('Monero Business Wallet', layout, margins=(20, 20), titlebar_icon='', titlebar_background_color=cfg.ui_overall_background, use_custom_titlebar=False, grab_anywhere=True, icon="./icon.png", finalize=True)
    else:
        return sg.Window(cfg.title_bar_text, layout, margins=(20, 20), titlebar_icon='', titlebar_background_color=cfg.ui_overall_background, use_custom_titlebar=True, grab_anywhere=True, icon=cfg.icon, finalize=True)


# SET THEME ############################################################################################################
# Start with template
sg.theme('DarkGrey2')

# Modify the colors you want to change
sg.theme_background_color(cfg.ui_overall_background)  # MAIN BACKGROUND COLOR
sg.theme_button_color((cfg.ui_button_a_font, cfg.ui_button_a))  # whiteish, blackish
sg.theme_text_color(cfg.monero_orange)  # HEADING TEXT AND DIVIDERS
sg.theme_text_element_background_color(cfg.ui_title_bar)  # Text Heading Boxes
sg.theme_element_background_color(cfg.ui_title_bar)  # subscriptions & transactions box color
sg.theme_element_text_color(cfg.ui_sub_font)  # My Subscriptions Text Color
sg.theme_input_background_color(cfg.ui_title_bar)
sg.theme_input_text_color(cfg.monero_orange)
sg.theme_border_width(0)
sg.theme_slider_border_width(0)


# START PROGRAM ########################################################################################################
# BEGIN "Add Daemon/Node" SECTION
if os.path.exists(cfg.node_filename):
    with open(cfg.node_filename, 'r') as f:
        node = f.readline().strip()  # read first line into 'node'
else:
    # welcome popup
    sg.popup(cfg.welcome_popup_text, icon=cfg.icon, no_titlebar=True, background_color=cfg.ui_overall_background, grab_anywhere=True)

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

            if wallet.check_if_node_works(node):
                window['custom_node'].update(value="Success!")

                # Save the node to the file
                with open(cfg.node_filename, 'w') as f:
                    f.write(node + '\n')
                break

            else:
                window['custom_node'].update(value="Node did not respond. Try Another.")

        elif event == 'add_random_node':
            print('Adding a random node. Please wait. \nThe software will seem to be frozen until a node is found.')
            node = get_random_monero_node()
            # Save the node to the file
            with open(cfg.node_filename, 'w') as f:
                f.write(node + '\n')
            break

        if event == sg.WIN_CLOSED:
            break

    window.close()

host = node.split(':')[0]
port = node.split(':')[1]

daemon_rpc_url = f"http://{host}:{port}/json_rpc"
# END "Add Daemon/Node" SECTION


# BEGIN "Convert/Forward" SECTION
# Note: cold_storage takes priority over convert. If both are specified, it should forward to cold storage only.
if os.path.exists(cfg.cold_wallet_filename):
    with open(cfg.cold_wallet_filename, 'r') as f:
        cfg.cold_wallet = f.readline().strip()
        if wallet.check_if_monero_wallet_address_is_valid_format(cfg.cold_wallet):
            cfg.forward = True

elif os.path.exists(cfg.convert_wallet_filename):
    with open(cfg.convert_wallet_filename, 'r') as f:
        data = f.read().strip()
        data = json.loads(data)
        cfg.convert_wallet = data['wallet']
        cfg.convert_coin = data['coin']
        cfg.convert_network = data['network']
        if cfg.convert_wallet and cfg.convert_coin and cfg.convert_network:
            cfg.convert = True
            print(cfg.convert_wallet, cfg.convert_coin, cfg.convert_network)

# If we haven't configured either, have the user configure one
if not cfg.forward and not cfg.convert:
    prompt_for_convert_forward_selection()

# If both are configured, make sure "Forward" takes priority.
if cfg.forward and cfg.convert:
    cfg.convert = False
# END "Convert/Forward" SECTION


# START PREREQUISITES ##################################################################################################
start_block_height = wallet.check_if_wallet_exists()  # auto-create one if it doesn't exist

# Start Local RPC Server
kill_monero_wallet_rpc()  # May be running from a previous launch
threading.Thread(target=start_local_rpc_server_thread).start()

# Make "Please Wait" Popup
window = sg.Window("Waiting", layout=make_please_wait_popup(), finalize=True, keep_on_top=True, no_titlebar=True, grab_anywhere=True)

# Wait until the RPC server starts
while not cfg.rpc_is_ready:
    # Check for window events
    event, values = window.read(timeout=100)  # Read with a timeout so the window is updated
print('\n\nRPC Server has started')

wallet_address = wallet.get_wallet_address()  # Now that the RPC Server is running, get the wallet address

try:  # Now that the RPC Server is running, get the wallet balance
    cfg.wallet_balance_xmr, cfg.wallet_balance_usd, cfg.xmr_unlocked_balance = wallet.get_wallet_balance()
except:
    pass

window.close()  # Close "Please Wait" Popup


# Create the window
window = create_main_window()

# START THREADS ########################################################################################################
# Continually update displayed GUI balance every 5 seconds
threading.Thread(target=update_gui_balance).start()

# Continually update the payments received/sent csv files every 2 min (every block)
threading.Thread(target=check_for_new_transactions).start()

# Continually auto-forward Monero if conditions are met every 2 min (every block)
threading.Thread(target=autoforward_monero).start()


# MAIN EVENT LOOP ######################################################################################################
while True:
    event, values = window.read()

    # CLOSE BUTTON PRESSED
    if event == sg.WIN_CLOSED:
        break

    # COPY ADDRESS BUTTON PRESSED
    elif event == 'copy_address':
        clipboard.copy(wallet_address)
        print(f'COPIED: {wallet_address}')

    # SEND BUTTON PRESSED
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
                choice = sg.popup(f"Are you sure you want to send all your XMR to this address?\n", text_color=cfg.ui_sub_font, title='', custom_text=("    Yes, I am sure!    ", "    No, CANCEL!    "), no_titlebar=True, background_color=cfg.ui_title_bar, modal=True, grab_anywhere=True, icon=cfg.icon)
                if "No, CANCEL!" in choice:
                    print("Cancelled wallet sweep!")
                    pass
                elif "Yes, I am sure!" in choice:
                    wallet.send_monero(destination_address=withdraw_to_wallet, amount=cfg.xmr_unlocked_balance)
                    print("The wallet has been swept!")
            else:
                wallet.send_monero(destination_address=withdraw_to_wallet, amount=withdraw_amount)

        except Exception as e:
            print(e)
            print('failed to send')
            window['withdraw_to_wallet'].update('Error: Enter a valid wallet address and XMR amount.')

window.close()
