import numpy as np

from ..get.get_oracle_prices import OraclePrices
from ..get.get_markets import Markets
from ..gmx_utils import get_tokens_address_dict, determine_swap_route


class OrderArgumentParser:

    def __init__(self, config, is_increase: bool = False, is_decrease: bool = False, is_swap: bool = False):
        """
        Initialize the parser with configuration and order type (increase, decrease, or swap).

        Parameters:
        - config: Configuration object for GMX.
        - is_increase: True if creating an increase order.
        - is_decrease: True if creating a decrease order.
        - is_swap: True if creating a swap order.
        """
        self.config = config
        self.parameters_dict = None
        self.is_increase = is_increase
        self.is_decrease = is_decrease
        self.is_swap = is_swap

        # Fetch market information
        self.markets = Markets(config).info

        # Define required keys based on the order type
        if is_increase:
            self.required_keys = [
                "chain",
                "index_token_address",
                "market_key",
                "start_token_address",
                "collateral_address",
                "swap_path",
                "is_long",
                "size_delta_usd",
                "initial_collateral_delta",
                "slippage_percent"
            ]
        elif is_decrease:
            self.required_keys = [
                "chain",
                "index_token_address",
                "market_key",
                "start_token_address",
                "collateral_address",
                "is_long",
                "size_delta_usd",
                "initial_collateral_delta",
                "slippage_percent"
            ]
        elif is_swap:
            self.required_keys = [
                "chain",
                "start_token_address",
                "out_token_address",
                "initial_collateral_delta",
                "swap_path",
                "slippage_percent"
            ]

        # Mapping missing key handlers to their respective methods
        self.missing_base_key_methods = {
            "chain": self._handle_missing_chain,
            "index_token_address": self._handle_missing_index_token_address,
            "market_key": self._handle_missing_market_key,
            "start_token_address": self._handle_missing_start_token_address,
            "out_token_address": self._handle_missing_out_token_address,
            "collateral_address": self._handle_missing_collateral_address,
            "swap_path": self._handle_missing_swap_path,
            "is_long": self._handle_missing_is_long,
            "slippage_percent": self._handle_missing_slippage_percent
        }

    def process_parameters_dictionary(self, parameters_dict):
        """
        Process the user-supplied parameters dictionary, filling in missing fields
        or raising exceptions for invalid configurations.

        Parameters:
        - parameters_dict: User-supplied dictionary of parameters for the order.
        """
        print("[DEBUG] Processing parameters dictionary...")
        print(f"[DEBUG] Initial parameters: {parameters_dict}")

        # Identify missing keys from the user-supplied dictionary
        missing_keys = self._determine_missing_keys(parameters_dict)
        print(f"[DEBUG] Missing keys: {missing_keys}")

        self.parameters_dict = parameters_dict

        # Handle missing keys using their respective methods
        for missing_key in missing_keys:
            if missing_key in self.missing_base_key_methods:
                print(f"[DEBUG] Handling missing key: {missing_key}")
                self.missing_base_key_methods[missing_key]()

        # Calculate position size or leverage if not provided (non-swap orders)
        if not self.is_swap:
            self.calculate_missing_position_size_info_keys()
            self._check_if_max_leverage_exceeded()

        # Ensure minimum collateral requirements for increase orders
        if self.is_increase:
            initial_collateral_usd = self._calculate_initial_collateral_usd()
            print(f"[DEBUG] Initial collateral in USD: {initial_collateral_usd}")
            if initial_collateral_usd < 2:
                raise Exception("Position size must be backed by >$2 of collateral!")

        # Format size and collateral values for on-chain compatibility
        self._format_size_info()
        print(f"[DEBUG] Final processed parameters: {self.parameters_dict}")

        return self.parameters_dict

    def _determine_missing_keys(self, parameters_dict):
        """
        Identify keys that are required but missing from the provided parameters dictionary.

        Parameters:
        - parameters_dict: User-supplied parameters for the order.

        Returns:
        - A list of missing keys.
        """
        print("[DEBUG] Determining missing keys...")
        return [key for key in self.required_keys if key not in parameters_dict]

    def _handle_missing_chain(self):
        """
        Handle a missing chain parameter.
        """
        raise Exception("Please pass chain name in parameters dictionary!")

    def _handle_missing_index_token_address(self):
        """
        Handle a missing index token address by deriving it from the token symbol.
        """
        try:
            token_symbol = self.parameters_dict['index_token_symbol']
            if token_symbol == "BTC":  # Exception for BTC ticker
                token_symbol = "WBTC.b"
        except KeyError:
            raise Exception("Index Token Address and Symbol not provided!")

        # Look up the address based on the token symbol
        self.parameters_dict['index_token_address'] = self.find_key_by_symbol(
            get_tokens_address_dict(self.parameters_dict['chain']),
            token_symbol
        )
        print(f"[DEBUG] Derived index token address: {self.parameters_dict['index_token_address']}")

    def _handle_missing_market_key(self):
        """
        Handle a missing market key by deriving it from the index token address.
        """
        index_token_address = self.parameters_dict['index_token_address']

        # Exception handling for specific addresses
        if index_token_address == "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f":
            index_token_address = "0x47904963fc8b2340414262125aF798B9655E58Cd"

        # Derive the market key from the index token address
        self.parameters_dict['market_key'] = self.find_market_key_by_index_address(
            self.markets,
            index_token_address
        )
        print(f"[DEBUG] Derived market key: {self.parameters_dict['market_key']}")

    # Similar methods (_handle_missing_start_token_address, _handle_missing_swap_path, etc.)
    # would include debug statements to print intermediate results.

    def _calculate_initial_collateral_usd(self):
        """
        Calculate the USD value of the initial collateral.

        Returns:
        - The USD value of the initial collateral.
        """
        initial_collateral_delta_amount = self.parameters_dict['initial_collateral_delta']
        prices = OraclePrices(chain=self.parameters_dict['chain']).get_recent_prices()

        # Get the median price for the collateral token
        price = np.median([
            float(prices[self.parameters_dict["start_token_address"]]['maxPriceFull']),
            float(prices[self.parameters_dict["start_token_address"]]['minPriceFull'])
        ])

        # Adjust for token decimals
        oracle_factor = get_tokens_address_dict(
            self.parameters_dict['chain']
        )[self.parameters_dict["start_token_address"]]['decimals'] - 30
        price = price * 10 ** oracle_factor

        collateral_usd = price * initial_collateral_delta_amount
        print(f"[DEBUG] Calculated initial collateral USD: {collateral_usd}")
        return collateral_usd

    def _format_size_info(self):
        """
        Format `size_delta` and `initial_collateral_delta` for on-chain compatibility.
        """
        print("[DEBUG] Formatting size information for on-chain compatibility...")
        if not self.is_swap:
            self.parameters_dict["size_delta"] = int(
                self.parameters_dict["size_delta_usd"] * 10**30
            )
        decimal = get_tokens_address_dict(
            self.parameters_dict['chain']
        )[self.parameters_dict["start_token_address"]]['decimals']
        self.parameters_dict["initial_collateral_delta"] = int(
            self.parameters_dict["initial_collateral_delta"] * 10**decimal
        )
        print(f"[DEBUG] Formatted size_delta: {self.parameters_dict['size_delta']}")
        print(f"[DEBUG] Formatted initial_collateral_delta: {self.parameters_dict['initial_collateral_delta']}")
