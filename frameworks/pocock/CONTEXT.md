# Expense Splitting

Shared-expense tracking for small groups: who paid for what, who owes whom, and the fewest transfers needed to square up.

## Language

### Groups and people

**Group**:
A named set of Members who share expenses, with a single Currency.
_Avoid_: Party, team, trip

**Member**:
A named person within one Group. Members are scoped to their Group and are not global accounts.
_Avoid_: User, participant (when meaning group membership), account

**Departed Member**:
A Member who has left their Group after their Balance reached zero. They stay in past Expenses and Payments but take no part in new ones, Balances or Settle-up.
_Avoid_: Deleted member, former member, inactive member

### Money

**Currency**:
The single currency, chosen when the Group is created, in which all of the Group's Amounts are expressed.

**Amount**:
A quantity of money expressed exactly as a whole number of the Currency's minor units (e.g. cents).
_Avoid_: Price, value, total

### Expenses

**Expense**:
A record that one Member (the Payer) paid an Amount for something, split equally among a set of Participants.
_Avoid_: Bill, transaction, charge

**Payer**:
The Member who paid the Expense's Amount. The Payer does not have to be a Participant.

**Participant**:
A Member whom an Expense is split between, and who therefore owes a Share of it.
_Avoid_: Splitter, debtor, beneficiary

**Share**:
The whole-minor-unit portion of an Expense's Amount owed by one Participant. Within one Expense, the Shares add up exactly to the Amount.
_Avoid_: Split, portion, cut

**Remainder**:
The minor units left over when an Amount does not divide evenly among the Participants. They are handed out one unit each to the Participants in the order they joined the Group.

### Settling

**Payment**:
A record that one Member gave another an Amount directly to reduce what they owe.
_Avoid_: Settlement, transfer (when recorded), repayment

**Balance**:
A Member's net position in a Group: what they are owed minus what they owe. Positive means they are owed money. The Balances of all a Group's Members always add up to exactly zero.
_Avoid_: Debt, total, net

**Settle-up**:
A proposed set of Suggested Transfers that would bring every Balance to zero, using as few transfers as possible.
_Avoid_: Settlement plan, simplify debts

**Suggested Transfer**:
One step of a Settle-up: a proposal that one Member pay another a given Amount. It is not recorded until a Payment is made.
_Avoid_: Payment (before it is recorded), transaction
