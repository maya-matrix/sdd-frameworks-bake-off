# 07: Delete Expenses and Payments

**What to build:** A caller can permanently delete an Expense or a Payment recorded by mistake, and Balances update to match. Expenses and Payments can't be edited; to change one, delete it and record it again.

**Blocked by:** 05 (Payments)

**Status:** done

- [x] `DELETE /groups/{id}/expenses/{expense_id}` returns 204. The Expense disappears from the list and its effect on Balances is reversed.
- [x] `DELETE /groups/{id}/payments/{payment_id}` returns 204. The Payment disappears from the list and its effect on Balances is reversed.
- [x] 404 for an unknown Group, an unknown Expense or Payment, or one that belongs to a different Group.
- [x] Deleting the same item twice returns 404 the second time.
- [x] The Balances still add up to zero after deletions.
