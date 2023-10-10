import os
import platform
import threading

"""
Configuration File for Monero Business Wallet
Contains global settings and variables used across the application.
"""

# =====================
# Files
# =====================
received_transactions_file = 'received_transactions.csv'
sent_transactions_file = 'sent_transactions.csv'
node_filename = "node_to_use.txt"
wallet_name = "business_wallet"
swap_file = 'swap_info.csv'

# =====================
# RPC Settings
# =====================
rpc_bind_port = '18088'
local_rpc_url = f"http://127.0.0.1:{rpc_bind_port}/json_rpc"
rpc_username = "monero"
rpc_password = "monero"

# =====================
# Cold Wallet Configurations
# =====================
cold_wallet_filename = 'cold_wallet.txt'
cold_wallet = ''

# =====================
# Convert Wallet Configurations
# =====================
convert_wallet_filename = 'conversion_wallet.txt'
convert_wallet = ''
convert_coin = ''
convert_network = ''

# =====================
# Placeholders and Dynamic Values
# =====================
xmr_unlocked_balance = '--.------------'
wallet_balance_xmr = '--.------------'
wallet_balance_usd = '---.--'
current_monero_price = 150.00
wallet_address = ''

# =====================
# Amounts
# =====================
usd_amount_to_leave_in_wallet_for_tx_fees = 1

# =====================
# Flags and Booleans
# =====================
convert = False
forward = False
rpc_is_ready = False
stop_flag = threading.Event()  # Define a flag to indicate if the threads should stop

# =====================
# Theme Variables
# =====================
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
main_text = ui_main_font  # this lets separators be orange but text stay white
subscription_text_color = ui_sub_font
subscription_background_color = ui_overall_background  # cfg.ui_title_bar

# Other
icon = 'icon.ico'
font = 'Nunito Sans'
title_bar_text = ''

# =====================
# Longform Text
# =====================
welcome_popup_text = '''
           Welcome to the Monero Business Wallet!

We're thrilled that you've chosen to use our Free and Open Source Software (FOSS). Before you get started, there are a few important things you should know:

1. Monero Business Wallet is currently in alpha. Your feedback is valuable to us in making this software better. Please let us know if you encounter any issues or, if you are a developer, help resolve them! All the code is on GitHub.

2. Monero Business Wallet is an internet-connected hot wallet, its security is only as robust as your computer's is.

3. By using this software, you understand and agree that you're doing so at your own risk. The developers cannot be held responsible for any lost funds.

Enjoy using the Monero Business Wallet, thank you for your support, and if you are a Python developer, please consider helping us improve the project!

https://github.com/lukeprofits/Monero_Business_Wallet
'''

# =====================
# Platform-Dependent Configurations
# =====================
# Set Monero Wallet CLI Path
if platform.system() == 'Windows':
    # Update path to the location of the monero-wallet-cli executable if your on WINDOWS
    monero_wallet_cli_path = "" + 'monero-wallet-cli.exe'
else:
    # Update path to the location of the monero-wallet-cli executable if your on other platforms
    monero_wallet_cli_path = os.getcwd() + '/' + 'monero-wallet-cli'

# Set Wallet Path
if platform.system() == 'Windows':
    wallet_file_path = ""
else:
    # Update this path to the location where you want to save the wallet file
    wallet_file_path = f'{os.getcwd()}/'
