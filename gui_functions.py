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
import config as cfg


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
                            [sg.Image(generate_monero_qr(cfg.wallet_address), size=(147, 147), key='qr_code', pad=(10, 0))],  # Placeholder for the QR code image
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


# OTHER VISUALS ########################################################################################################
def generate_monero_qr(wallet_address):
    if wallet.check_if_monero_wallet_address_is_valid_format(cfg.wallet_address):
        # Generate the QR code
        qr = qrcode.QRCode(version=1, box_size=3, border=4)
        qr.add_data("monero:" + cfg.wallet_address)
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
