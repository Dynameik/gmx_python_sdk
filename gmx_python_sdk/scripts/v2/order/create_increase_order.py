from .order import Order
from ..gas_utils import get_gas_limits
from ..gmx_utils import get_datastore_contract


class IncreaseOrder(Order):
    """
    Handles the creation and submission of an order to increase a position (buy order) on GMX.
    This class extends the base `Order` class, inheriting shared functionality.
    """

    def __init__(self, *args: list, **kwargs: dict) -> None:
        """
        Initialize the IncreaseOrder class.

        Parameters:
        - *args: Positional arguments passed to the base `Order` class.
        - **kwargs: Keyword arguments passed to the base `Order` class.

        This constructor immediately calls `order_builder` to set up the order for increasing a position.
        """
        # Call the parent class constructor to initialize common order attributes.
        super().__init__(*args, **kwargs)

        # Debug: Log the initialization of an IncreaseOrder.
        print("[DEBUG] IncreaseOrder initialized with the following parameters:")
        for arg_name, arg_value in kwargs.items():
            print(f"  - {arg_name}: {arg_value}")

        # Open an increase order.
        # The `order_builder` method prepares the order parameters to align with GMX's requirements.
        print("[DEBUG] Calling order_builder to configure the increase order...")
        self.order_builder(is_open=True)
        print("[DEBUG] Increase order configured successfully.")

    def determine_gas_limits(self):
        """
        Determine the gas limits for the increase order.

        This method fetches the gas limits specific to the increase order type from GMX's data store.
        """
        # Fetch the datastore contract instance using the provided configuration.
        print("[DEBUG] Fetching datastore contract to retrieve gas limits...")
        datastore = get_datastore_contract(self.config)
        print("[DEBUG] Datastore contract retrieved.")

        # Retrieve gas limits from the datastore.
        print("[DEBUG] Retrieving gas limits for the increase order...")
        self._gas_limits = get_gas_limits(datastore)
        print(f"[DEBUG] Retrieved gas limits: {self._gas_limits}")

        # Extract the specific gas limit for the "increase_order" type.
        self._gas_limits_order_type = self._gas_limits["increase_order"]
        print(f"[DEBUG] Gas limit for 'increase_order': {self._gas_limits_order_type}")
