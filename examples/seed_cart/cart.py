"""A tiny shopping cart with a bulk discount."""

from dataclasses import dataclass

BULK_THRESHOLD = 10  # buy this many or more of one item to get the discount
BULK_DISCOUNT = 0.10


@dataclass
class Item:
    """A cart line."""

    name: str
    unit_price: float
    quantity: int = 1


class Cart:
    """Holds items and computes totals."""

    def __init__(self) -> None:
        self._items: dict[str, Item] = {}

    def add(self, name: str, unit_price: float, quantity: int = 1) -> None:
        """Add `quantity` of an item."""
        if name in self._items:
            self._items[name].quantity += quantity
        else:
            self._items[name] = Item(name, unit_price, quantity)

    def line_total(self, item: Item) -> float:
        """Total for one line, with the bulk discount applied."""
        total = item.unit_price * item.quantity
        if item.quantity > BULK_THRESHOLD:
            total *= 1 - BULK_DISCOUNT
        return round(total, 2)

    def total(self) -> float:
        """Cart total."""
        return round(sum(self.line_total(i) for i in self._items.values()), 2)
