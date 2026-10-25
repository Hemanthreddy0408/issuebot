from cart import Cart


def test_no_discount_below_threshold():
    c = Cart()
    c.add("pen", 2.00, 9)
    assert c.total() == 18.00


def test_discount_above_threshold():
    c = Cart()
    c.add("pen", 2.00, 11)
    assert c.total() == 19.80


def test_discount_at_threshold():
    c = Cart()
    c.add("pen", 2.00, 10)
    assert c.total() == 18.00
