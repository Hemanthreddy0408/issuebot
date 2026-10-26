"""Simple bank account with overdraft protection."""


class InsufficientFundsError(Exception):
    pass


class BankAccount:
    """A bank account with optional overdraft limit."""

    def __init__(self, balance: float = 0.0, overdraft_limit: float = 0.0) -> None:
        if overdraft_limit < 0:
            raise ValueError("overdraft_limit must be >= 0")
        self._balance = balance
        self._overdraft_limit = overdraft_limit
        self._transactions: list[tuple[str, float]] = []

    @property
    def balance(self) -> float:
        return round(self._balance, 2)

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        self._balance += amount
        self._transactions.append(("deposit", amount))

    def withdraw(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        # BUG: should check self._balance - amount >= -self._overdraft_limit
        # Currently it only checks against 0, ignoring the overdraft limit
        if self._balance - amount < 0:
            raise InsufficientFundsError(
                f"Cannot withdraw {amount:.2f}: balance {self._balance:.2f}, "
                f"overdraft limit {self._overdraft_limit:.2f}"
            )
        self._balance -= amount
        self._transactions.append(("withdrawal", amount))

    def statement(self) -> list[tuple[str, float]]:
        return list(self._transactions)
