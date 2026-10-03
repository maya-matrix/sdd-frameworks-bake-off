# 05: Payments

**What to build:** A caller can record a Payment, in which one Member gave another an Amount directly, and list a Group's Payments. Payments feed into Balances: the sender's Balance goes up and the recipient's goes down.

**Blocked by:** 04 (Balances)

**Status:** done

- [x] `POST /groups/{id}/payments` with `{from_id, to_id, amount}` returns 201 with the Payment (id, from_id, to_id, amount, created_at).
- [x] `GET /groups/{id}/payments` lists the Group's Payments.
- [x] Example: after B (−333) pays A 333, B's Balance is 0 and A's goes down by 333.
- [x] Overpaying is allowed: the Balances simply flip sign.
- [x] 422 for:
  - `from_id` equal to `to_id`;
  - an Amount that is not a positive integer;
  - a sender or recipient that isn't a Member of this Group.
- [x] An unknown Group returns 404.
- [x] After any mix of Expenses and Payments, the Balances still add up to exactly zero.
