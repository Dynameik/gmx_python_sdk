import numpy as np
from hexbytes import HexBytes
from web3 import Web3
from ..get.get_markets import Markets
from ..get.get_oracle_prices import OraclePrices
from ..gmx_utils import (
    get_exchange_router_contract, create_connection, contract_map,
    PRECISION, get_execution_price_and_price_impact, order_type as order_types,
    decrease_position_swap_type as decrease_position_swap_types,
    convert_to_checksum_address, check_web3_correct_version
)
from ..gas_utils import get_execution_fee
from ..approve_token_for_spend import check_if_approved

is_newer_version, version = check_web3_correct_version()
if is_newer_version:
    print("[DEBUG] Warning: Current version of py web3 ({version}), may result in errors.")

class Order:
    def __init__(
        self, config: str, market_key: str, collateral_address: str,
        index_token_address: str, is_long: bool, size_delta: float,
        initial_collateral_delta_amount: str, slippage_percent: float,
        swap_path: list, max_fee_per_gas: int = None, auto_cancel: bool = False,
        debug_mode: bool = False, execution_buffer: float = 1.3
    ) -> None:
        """
        Initialize the Order class with all the parameters required for submitting a transaction.
        """
        self.config = config
        self.market_key = market_key
        self.collateral_address = collateral_address
        self.index_token_address = index_token_address
        self.is_long = is_long
        self.size_delta = size_delta  # USD position size
        self.initial_collateral_delta_amount = initial_collateral_delta_amount  # Collateral amount (scaled)
        self.slippage_percent = slippage_percent  # Allowable slippage as a percentage
        self.swap_path = swap_path  # Token swap path
        self.max_fee_per_gas = max_fee_per_gas  # Max gas fee for transaction
        self.debug_mode = debug_mode  # Debug mode for testing without submission
        self.auto_cancel = auto_cancel  # Whether to auto-cancel the order
        self.execution_buffer = execution_buffer  # Buffer for execution fee

        if self.debug_mode:
            print(f"[DEBUG] Execution buffer set to: {(self.execution_buffer - 1) * 100:.2f}%")

        if self.max_fee_per_gas is None:
            block = create_connection(config).eth.get_block('latest')
            self.max_fee_per_gas = block['baseFeePerGas'] * 1.35
            print(f"[DEBUG] Max fee per gas dynamically set to: {self.max_fee_per_gas}")

        self._exchange_router_contract_obj = get_exchange_router_contract(config=self.config)
        self._connection = create_connection(config)
        self._is_swap = False

        print("[DEBUG] Creating order...")

    def determine_gas_limits(self):
        """
        Placeholder for gas limits determination. Override this in derived classes.
        """
        pass

    def check_for_approval(self):
        """
        Check if the collateral token is approved for spending by the contract and approve if necessary.
        """
        spender = contract_map[self.config.chain]["syntheticsrouter"]['contract_address']
        print(f"[DEBUG] Checking approval for spender: {spender} on token: {self.collateral_address}")
        
        check_if_approved(
            self.config,
            spender,
            self.collateral_address,
            self.initial_collateral_delta_amount,
            self.max_fee_per_gas,
            approve=True
        )
        print("[DEBUG] Approval check completed.")

    def _submit_transaction(self, user_wallet_address: str, value_amount: float, multicall_args: list, gas_limits: dict):
        """
        Build and submit the transaction to the blockchain.
        """
        print("[DEBUG] Building transaction...")
        try:
            wallet_address = Web3.to_checksum_address(user_wallet_address)
        except AttributeError:
            wallet_address = Web3.toChecksumAddress(user_wallet_address)

        print(f"[DEBUG] Wallet address: {wallet_address}")
        
        nonce = self._connection.eth.get_transaction_count(wallet_address)
        print(f"[DEBUG] Nonce for transaction: {nonce}")

        try:
            raw_txn = self._exchange_router_contract_obj.functions.multicall(multicall_args).build_transaction({
                'value': value_amount,
                'chainId': self.config.chain_id,
                'gas': self._gas_limits_order_type.call() + self._gas_limits_order_type.call(),
                'maxFeePerGas': int(self.max_fee_per_gas),
                'maxPriorityFeePerGas': 0,
                'nonce': nonce
            })

            print(f"[DEBUG] Raw transaction built: {raw_txn}")

            if not self.debug_mode:
                signed_txn = self._connection.eth.account.sign_transaction(raw_txn, self.config.private_key)
                txn = signed_txn.rawTransaction if hasattr(signed_txn, 'rawTransaction') else signed_txn.raw_transaction
                tx_hash = self._connection.eth.send_raw_transaction(txn)
                
                print(f"[DEBUG] Transaction submitted! Tx Hash: {tx_hash.hex()}")
                print(f"[DEBUG] Check status at: https://arbiscan.io/tx/{tx_hash.hex()}")

        except Exception as e:
            print(f"[ERROR] Failed to submit transaction: {e}")

    def _get_prices(self, decimals: float, prices: float, is_open: bool = False, is_close: bool = False, is_swap: bool = False):
        """
        Fetch and calculate token prices including slippage and acceptable price range.
        """
        print("[DEBUG] Getting prices...")
        try:
            price = np.median([
                float(prices[self.index_token_address]['maxPriceFull']),
                float(prices[self.index_token_address]['minPriceFull'])
            ])
            print(f"[DEBUG] Median price: {price}")

            if is_open:
                slippage = price * (1 + self.slippage_percent) if self.is_long else price * (1 - self.slippage_percent)
            elif is_close:
                slippage = price * (1 - self.slippage_percent) if self.is_long else price * (1 + self.slippage_percent)
            else:
                slippage = 0
            
            print(f"[DEBUG] Slippage-adjusted price: {slippage}")

            acceptable_price_in_usd = int(slippage) * 10 ** (decimals - PRECISION)
            print(f"[DEBUG] Acceptable price in USD (scaled): {acceptable_price_in_usd}")

            return price, int(slippage), acceptable_price_in_usd

        except Exception as e:
            print(f"[ERROR] Error while getting prices: {e}")
            raise
