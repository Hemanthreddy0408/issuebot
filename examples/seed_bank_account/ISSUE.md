When I create an account with `BankAccount(balance=50.0, overdraft_limit=100.0)` and try to
withdraw 120.0, I get `InsufficientFundsError` even though 120 ≤ 50 + 100 and the overdraft
limit should cover it.

The `withdraw` method does not use `overdraft_limit` at all — it only blocks withdrawals that
would push the balance below zero. It should allow withdrawals down to `-overdraft_limit`.
