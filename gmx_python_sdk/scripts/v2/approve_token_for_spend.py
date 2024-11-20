import json
import os

from web3 import Web3

from .gmx_utils import (
    create_connection, base_dir, convert_to_checksum_address
)


def check_if_approved(
        config,
        spender: str,
        token_to_approve: str,
        amount_of_tokens_to_spend: int,
        max_fee_per_gas,
        approve: bool):
    """
    For a given chain, check if a given amount of tokens is approved for spend by a contract, and
    approve is passed as True.

    Parameters
    ----------
    config : object
        Configuration object containing chain details, user wallet, etc.
    spender : str
        Contract address of the requested spender.
    token_to_approve : str
        Contract address of the token to spend.
    amount_of_tokens_to_spend : int
        Amount of tokens to spend in expanded decimals.
    max_fee_per_gas : int
        Maximum fee per gas for the transaction.
    approve : bool
        If True, approve the spender if the allowance is insufficient.

    Raises
    ------
    Exception
        If balance is insufficient or token is not approved for spending.
    """

    # Establish a connection to the blockchain
    connection = create_connection(config)

    # Handle specific cases for known token mappings
    if token_to_approve == "0x47904963fc8b2340414262125aF798B9655E58Cd":
        print("[DEBUG] Re-mapping token_to_approve address for compatibility.")
        token_to_approve = "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f"

    # Convert addresses to checksum format
    print("[DEBUG] Converting spender address to checksum format.")
    spender_checksum_address = convert_to_checksum_address(config, spender)

    print("[DEBUG] Converting user wallet address to checksum format.")
    user_checksum_address = convert_to_checksum_address(config, config.user_wallet_address)

    print("[DEBUG] Converting token address to checksum format.")
    token_checksum_address = convert_to_checksum_address(config, token_to_approve)

    # Load the token contract ABI for interaction
    print("[DEBUG] Loading token contract ABI.")
    token_contract_abi = json.load(open(os.path.join(
        base_dir,
        'gmx_python_sdk',
        'contracts',
        'token_approval.json'
    )))

    # Create a contract object for interacting with the token
    token_contract_obj = connection.eth.contract(
        address=token_to_approve,
        abi=token_contract_abi
    )

    # Determine balance for native tokens (ETH) or ERC-20 tokens
    print("[DEBUG] Fetching wallet balance.")
    if token_checksum_address == "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1":  # ETH on Arbitrum
        try:
            balance_of = connection.eth.getBalance(user_checksum_address)
        except AttributeError:
            balance_of = connection.eth.get_balance(user_checksum_address)
    else:  # ERC-20 tokens
        balance_of = token_contract_obj.functions.balanceOf(user_checksum_address).call()

    print(f"[DEBUG] Wallet balance: {balance_of} (raw units).")

    # Check if balance is sufficient for the transaction
    if balance_of < amount_of_tokens_to_spend:
        print("[ERROR] Insufficient balance to proceed with the transaction.")
        raise Exception("Insufficient balance!")

    # Check current allowance for the spender
    print("[DEBUG] Fetching current allowance for spender.")
    amount_approved = token_contract_obj.functions.allowance(
        user_checksum_address,
        spender_checksum_address
    ).call()

    print(f"[DEBUG] Current allowance: {amount_approved} (raw units).")

    # If insufficient allowance and approval is enabled, approve the spender
    if amount_approved < amount_of_tokens_to_spend and approve:
        print("[DEBUG] Allowance insufficient. Proceeding to approve spender.")

        print('Approving contract "{}" to spend {} tokens belonging to token address: {}'.format(
            spender_checksum_address, amount_of_tokens_to_spend, token_checksum_address))

        # Fetch the current nonce for the user's wallet
        nonce = connection.eth.get_transaction_count(user_checksum_address)

        # Build the approval transaction
        arguments = (spender_checksum_address, amount_of_tokens_to_spend)
        raw_txn = token_contract_obj.functions.approve(
            *arguments
        ).build_transaction({
            'value': 0,
            'chainId': config.chain_id,
            'gas': 4000000,
            'maxFeePerGas': int(max_fee_per_gas),
            'maxPriorityFeePerGas': 0,
            'nonce': nonce
        })

        # Sign the transaction with the user's private key
        signed_txn = connection.eth.account.sign_transaction(
            raw_txn,
            config.private_key
        )

        # Submit the transaction to the blockchain
        try:
            txn = signed_txn.rawTransaction
        except TypeError:
            txn = signed_txn.raw_transaction

        tx_hash = connection.eth.send_raw_transaction(txn)

        print("Txn submitted!")
        print("Check status: https://arbiscan.io/tx/{}".format(tx_hash.hex()))

    # If allowance is insufficient and approve is False, raise an error
    if amount_approved < amount_of_tokens_to_spend and not approve:
        print("[ERROR] Token not approved for spend. Please allow first!")
        raise Exception("Token not approved for spend, please allow first!")

    # Log success message
    print('Contract "{}" approved to spend {} tokens belonging to token address: {}'.format(
        spender_checksum_address, amount_of_tokens_to_spend, token_checksum_address))
    print("Coins Approved for spend!")


if __name__ == "__main__":
    pass
