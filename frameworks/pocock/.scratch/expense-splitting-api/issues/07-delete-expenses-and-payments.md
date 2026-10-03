# 07: Delete Expenses and Payments

**What to build:** A caller can permanently delete an Expense or a Payment recorded by mistake, and Balances update to match. Expenses and Payments can't be edited; to change one, delete it and record it again.

**Blocked by:** 05 (Payments)

**Status:** ready-for-agent

- [ ] `DELETE /groups/{id}/expenses/{expense_id}` returns 204. The Expense disappears from the list and its effect on Balances is reversed.
- [ ] `DELETE /groups/{id}/payments/{payment_id}` returns 204. The Payment disappears from the list and its effect on Balances is reversed.
- [ ] 404 for an unknown Group, an unknown Expense or Payment, or one that belongs to a different Group.
- [ ] Deleting the same item twice returns 404 the second time.
- [ ] The Balances still add up to zero after deletions.
