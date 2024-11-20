from eth_abi import encode
from web3 import Web3
import yaml
import logging
import os
import json
import requests
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    format='{asctime} {levelname}: {message}',
    datefmt='%m/%d/%Y %I:%M:%S %p',
    style='{',
    level=logging.INFO
)

# Set base directory for accessing relative paths
current_script_path = os.path.abspath(__file__)
base_dir = os.path.abspath(
    os.path.join(current_script_path, '..', '..', '..', '..')
)
package_dir = base_dir + '/gmx_python_sdk/'

# Debug helper to print current status
def debug_log(message):
    print(f"[DEBUG] {message}")
    logging.info(message)

# Multithreading helper functions
def execute_call(call):
    """Execute a smart contract call."""
    return call.call()

def execute_threading(function_calls):
    """Execute multiple smart contract calls in parallel."""
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(execute_call, function_calls))
    return results

# Configuration and blockchain interaction
class ConfigManager:
    """
    Manage configuration for chain-specific settings like RPC, chain ID, and wallet details.
    """

    def __init__(self, chain: str):
        self.chain = chain
        self.rpc = None
        self.chain_id = None
        self.user_wallet_address = None
        self.private_key = None
        self.tg_bot_token = None

    def set_config(self, filepath: str = os.path.join(base_dir, "config.yaml")):
        """Load configuration from a YAML file."""
        debug_log(f"Loading configuration from {filepath}")
        with open(filepath, 'r') as file:
            config_file = yaml.safe_load(file)

        self.set_rpc(config_file['rpcs'][self.chain])
        self.set_chain_id(config_file['chain_ids'][self.chain])
        self.set_wallet_address(config_file['user_wallet_address'])
        self.set_private_key(config_file['private_key'])

    def set_rpc(self, value):
        """Set RPC URL."""
        debug_log(f"Setting RPC URL to {value}")
        self.rpc = value

    def set_chain_id(self, value):
        """Set chain ID."""
        debug_log(f"Setting chain ID to {value}")
        self.chain_id = value

    def set_wallet_address(self, value):
        """Set wallet address."""
        debug_log(f"Setting wallet address to {value}")
        self.user_wallet_address = value

    def set_private_key(self, value):
        """Set private key."""
        debug_log("Private key set (hidden for security).")
        self.private_key = value

def create_connection(config):
    """
    Establish a connection to the blockchain using Web3.
    """
    debug_log(f"Connecting to blockchain via RPC: {config.rpc}")
    web3_obj = Web3(Web3.HTTPProvider(config.rpc))
    if web3_obj.isConnected():
        debug_log("Successfully connected to blockchain.")
    else:
        debug_log("Failed to connect to blockchain.")
    return web3_obj

def get_contract_object(web3_obj, contract_name: str, chain: str):
    """
    Retrieve the contract object using the contract name and chain.
    """
    debug_log(f"Fetching contract object for {contract_name} on {chain}.")
    contract_address = contract_map[chain][contract_name]["contract_address"]
    abi_path = os.path.join(base_dir, 'gmx_python_sdk', contract_map[chain][contract_name]["abi_path"])

    # Load ABI
    debug_log(f"Loading ABI from {abi_path}")
    with open(abi_path, 'r') as abi_file:
        contract_abi = json.load(abi_file)

    # Return contract object
    debug_log(f"Instantiating contract at address {contract_address}")
    return web3_obj.eth.contract(address=contract_address, abi=contract_abi)

def get_tokens_address_dict(chain: str):
    """
    Retrieve available tokens on GMX for the specified chain from GMX's API.
    """
    debug_log(f"Fetching token data for chain: {chain}")
    url = {
        "arbitrum": "https://arbitrum-api.gmxinfra.io/tokens",
        "avalanche": "https://avalanche-api.gmxinfra.io/tokens"
    }

    try:
        response = requests.get(url[chain])
        response.raise_for_status()  # Ensure request was successful
        debug_log(f"Token data retrieved successfully for {chain}")
        token_infos = response.json()['tokens']
    except requests.RequestException as e:
        debug_log(f"Error fetching token data: {e}")
        return {}

    # Build token address dictionary
    token_address_dict = {
        token_info['address']: token_info
        for token_info in token_infos
    }
    debug_log(f"Token address dictionary constructed with {len(token_address_dict)} tokens.")
    return token_address_dict

# Example: Reader contract for querying data
def get_reader_contract(config):
    """
    Retrieve the reader contract for the chain.
    """
    debug_log("Retrieving reader contract.")
    web3_obj = create_connection(config)
    return get_contract_object(web3_obj, 'syntheticsreader', config.chain)

# Example of creating a hash
def create_hash(data_type_list: list, data_value_list: list):
    """
    Create a Keccak hash using specified data types and values.
    """
    debug_log("Creating Keccak hash.")
    byte_data = encode(data_type_list, data_value_list)
    keccak_hash = Web3.keccak(byte_data)
    debug_log(f"Keccak hash created: {keccak_hash.hex()}")
    return keccak_hash

# Save data utilities
def save_json_file_to_datastore(filename: str, data: dict):
    """
    Save data as a JSON file to the datastore.
    """
    filepath = os.path.join(package_dir, 'data_store', filename)
    debug_log(f"Saving data to JSON file: {filepath}")
    with open(filepath, 'w') as f:
        json.dump(data, f)
    debug_log("Data saved successfully.")

# Instantiate and test configuration
if __name__ == "__main__":
    debug_log("Initializing configuration manager.")
    arbitrum_config_object = ConfigManager(chain='arbitrum')
    arbitrum_config_object.set_config()
    debug_log("Configuration initialized.")
