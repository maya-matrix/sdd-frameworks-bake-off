/** All money values are bigint minor units (cents). */

export interface Group {
  id: string;
  name: string;
  createdAt: string;
}

export interface Member {
  id: string;
  groupId: string;
  name: string;
  /** Per-group insertion index; canonical order for all deterministic output. */
  seq: number;
}

export interface Share {
  memberId: string;
  amount: bigint;
}

export interface Expense {
  id: string;
  groupId: string;
  payerId: string;
  amount: bigint;
  description: string;
  shares: Share[];
  createdAt: string;
}

export interface Balance {
  memberId: string;
  /** Positive: should receive. Negative: should pay. */
  net: bigint;
}

export interface Transfer {
  fromMemberId: string;
  toMemberId: string;
  amount: bigint;
}

export interface SettlementPlan {
  transfers: Transfer[];
  /** True when the transfer count is the proven minimum. */
  optimal: boolean;
}
