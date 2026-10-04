import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EXACT_LIMIT, minimumTransfers } from '../src/settle.js';

const balancesOf = (...amounts) => amounts.map((amount, i) => ({ id: `u${i}`, amount: BigInt(amount) }));

/** Apply transfers and assert every balance ends at exactly zero. */
function assertSettles(balances, transfers) {
  const net = new Map(balances.map((b) => [b.id, b.amount]));
  for (const t of transfers) {
    assert.ok(t.amount > 0n, 'transfer amounts must be positive');
    assert.notEqual(t.from, t.to);
    net.set(t.from, net.get(t.from) + t.amount);
    net.set(t.to, net.get(t.to) - t.amount);
  }
  for (const [id, amount] of net) assert.equal(amount, 0n, `${id} not settled`);
}

/** Independent reference: classic backtracking search for the minimum transfer count. */
function bruteForceMinimum(amounts) {
  const debts = amounts.filter((a) => a !== 0n);
  const dfs = (start) => {
    while (start < debts.length && debts[start] === 0n) start++;
    if (start === debts.length) return 0;
    let best = Infinity;
    for (let i = start + 1; i < debts.length; i++) {
      if ((debts[i] > 0n) !== (debts[start] > 0n)) {
        debts[i] += debts[start];
        best = Math.min(best, 1 + dfs(start + 1));
        debts[i] -= debts[start];
      }
    }
    return best;
  };
  return dfs(0);
}

test('no transfers when everyone is even', () => {
  assert.deepEqual(minimumTransfers(balancesOf(0, 0, 0)), { transfers: [], optimal: true });
  assert.deepEqual(minimumTransfers([]), { transfers: [], optimal: true });
});

test('single debtor pays single creditor', () => {
  const balances = balancesOf(500, -500);
  const { transfers } = minimumTransfers(balances);
  assert.deepEqual(transfers, [{ from: 'u1', to: 'u0', amount: 500n }]);
});

test('settles matching debts pairwise', () => {
  const balances = balancesOf(600, 500, 400, -600, -500, -400);
  const { transfers, optimal } = minimumTransfers(balances);
  assert.equal(optimal, true);
  assert.equal(transfers.length, 3);
  assertSettles(balances, transfers);
});

test('exploits zero-sum subgroups (7,-7 is independent of 3,4,-2,-5)', () => {
  const balances = balancesOf(300, 400, 700, -200, -500, -700);
  const { transfers } = minimumTransfers(balances);
  assert.equal(transfers.length, bruteForceMinimum(balances.map((b) => b.amount)));
  assert.equal(transfers.length, 4);
  assertSettles(balances, transfers);
});

test('beats largest-first greedy matching', () => {
  // Greedy matching of the largest debtor to the largest creditor needs 5 transfers here.
  // Splitting into {8,-5,-3} and {7,-5,-2} needs only 4.
  const balances = balancesOf(800, 700, -500, -500, -300, -200);
  const { transfers } = minimumTransfers(balances);
  assert.equal(transfers.length, 4);
  assertSettles(balances, transfers);
});

test('rejects balances that do not sum to zero', () => {
  assert.throws(() => minimumTransfers(balancesOf(100, -99)), /sum to zero/);
});

test('matches brute-force minimum on random inputs', () => {
  let seed = 42;
  const rand = (n) => {
    seed = (seed * 1103515245 + 12345) % 2 ** 31;
    return seed % n;
  };
  for (let trial = 0; trial < 300; trial++) {
    const size = 2 + rand(8);
    const amounts = Array.from({ length: size - 1 }, () => BigInt(rand(21) - 10) * 100n);
    amounts.push(-amounts.reduce((a, b) => a + b, 0n));
    const balances = amounts.map((amount, i) => ({ id: `u${i}`, amount }));

    const { transfers, optimal } = minimumTransfers(balances);
    assert.equal(optimal, true);
    assertSettles(balances, transfers);
    assert.equal(transfers.length, bruteForceMinimum(amounts), `amounts: ${amounts.join(',')}`);
  }
});

test('solves exactly at the size limit and falls back to a valid settlement beyond it', () => {
  const at = balancesOf(...Array.from({ length: EXACT_LIMIT }, (_, i) => (i % 2 === 0 ? 100 + i : -(100 + i - 1))));
  const exact = minimumTransfers(at);
  assert.equal(exact.optimal, true);
  assert.equal(exact.transfers.length, EXACT_LIMIT / 2);
  assertSettles(at, exact.transfers);

  const beyond = balancesOf(...Array.from({ length: EXACT_LIMIT + 2 }, (_, i) => (i % 2 === 0 ? 100 : -100)));
  const fallback = minimumTransfers(beyond);
  assert.equal(fallback.optimal, false);
  assert.ok(fallback.transfers.length <= beyond.length - 1);
  assertSettles(beyond, fallback.transfers);
});
