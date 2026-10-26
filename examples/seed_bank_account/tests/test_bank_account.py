import pytest
from bank_account import BankAccount, InsufficientFundsError


def test_deposit_increases_balance():
    acc = BankAccount()
    acc.deposit(100.0)
    assert acc.balance == 100.0


def test_withdraw_decreases_balance():
    acc = BankAccount(balance=200.0)
    acc.withdraw(50.0)
    assert acc.balance == 150.0


def test_withdraw_with_overdraft_limit():
    """Withdrawing within overdraft limit should succeed."""
    acc = BankAccount(balance=50.0, overdraft_limit=100.0)
    acc.withdraw(120.0)
    assert acc.balance == -70.0


def test_withdraw_beyond_overdraft_raises():
    """Withdrawing beyond balance + overdraft should raise."""
    acc = BankAccount(balance=50.0, overdraft_limit=100.0)
    with pytest.raises(InsufficientFundsError):
        acc.withdraw(160.0)


def test_withdraw_no_overdraft_raises():
    """No overdraft: any withdrawal beyond balance raises."""
    acc = BankAccount(balance=30.0)
    with pytest.raises(InsufficientFundsError):
        acc.withdraw(31.0)


def test_deposit_invalid_amount():
    acc = BankAccount()
    with pytest.raises(ValueError):
        acc.deposit(-10.0)


def test_statement_records_transactions():
    acc = BankAccount(balance=100.0, overdraft_limit=50.0)
    acc.deposit(20.0)
    acc.withdraw(130.0)
    stmt = acc.statement()
    assert stmt == [("deposit", 20.0), ("withdrawal", 130.0)]
