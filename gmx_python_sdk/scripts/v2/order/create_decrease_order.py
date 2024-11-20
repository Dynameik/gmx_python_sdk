from .order import Order
from ..gas_utils import get_gas_limits
from ..gmx_utils import get_datastore_contract


class DecreaseOrder(Order):
    """
    Open a sell (decrease) order.

    Extends the base Order class to handle the specific functionality 
    required to close (or decrease) an existing position in GMX.
    """

    def __init__(self, *args: list, **kwargs: dict) -> None:
        """
        Initialize the DecreaseOrder class.

        Parameters:
        - *args: List of positional arguments to be passed to the base Order class.
        - **kwargs: Dictionary of keyword arguments to be passed to the base Order class.
        """
        print("[DEBUG] Initializing DecreaseOrder with arguments and keyword arguments.")
        super().__init__(
            *args, **kwargs
        )

        # Build the order as a "close" order
        print("[DEBUG] Building order as a 'close' order.")
        self.order_builder(is_close=True)

    def determine_gas_limits(self):
        """
        Determine the gas limits for a decrease order.

        This method interacts with the GMX datastore to fetch appropriate
        gas limit settings for a decrease order.
        """
        print("[DEBUG] Determining gas limits for the decrease order.")
        
        # Fetch the datastore contract
        datastore = get_datastore_contract(self.config)
        print(f"[DEBUG] Retrieved datastore contract: {datastore}")

        # Fetch and store gas limits specific to decrease orders
        self._gas_limits = get_gas_limits(datastore)
        print(f"[DEBUG] Gas limits fetched: {self._gas_limits}")

        # Set the specific gas limit for decrease orders
        self._gas_limits_order_type = self._gas_limits["decrease_order"]
        print(f"[DEBUG] Gas limit for 'decrease_order': {self._gas_limits_order_type}")
