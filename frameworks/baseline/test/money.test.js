import { test } from 'node:test';
import assert from 'node:assert/strict';
import { MoneyError, formatCents, parseAmount, splitEqually } from '../src/money.js';

test('parseAmount converts decimal strings to exact cents', () => {
  assert.equal(parseAmount('12'), 1200n);
  assert.equal(parseAmount('12.5'), 1250n);
  assert.equal(parseAmount('12.50'), 1250n);
  assert.equal(parseAmount('0.01'), 1n);
  assert.equal(parseAmount('0.10'), 10n);
  assert.equal(parseAmount('999999999999999.99'), 99999999999999999n);
});

test('parseAmount rejects invalid, zero, negative and over-precise amounts', () => {
  for (const bad of ['', '0', '0.00', '-1', '1.234', '1.', '.5', '01', 'abc', '1e3', ' 1', '1,00', '1000000000000000']) {
    assert.throws(() => parseAmount(bad), MoneyError, `expected ${JSON.stringify(bad)} to be rejected`);
  }
  for (const bad of [12.5, 10, null, undefined, {}]) {
    assert.throws(() => parseAmount(bad), MoneyError);
  }
});

test('formatCents renders signed two-decimal strings', () => {
  assert.equal(formatCents(0n), '0.00');
  assert.equal(formatCents(5n), '0.05');
  assert.equal(formatCents(1234n), '12.34');
  assert.equal(formatCents(-1234n), '-12.34');
  assert.equal(formatCents(-7n), '-0.07');
});

test('splitEqually distributes leftover cents and always sums to the total', () => {
  assert.deepEqual(splitEqually(1000n, 3), [334n, 333n, 333n]);
  assert.deepEqual(splitEqually(1001n, 3), [334n, 334n, 333n]);
  assert.deepEqual(splitEqually(1n, 3), [1n, 0n, 0n]);
  assert.deepEqual(splitEqually(900n, 3), [300n, 300n, 300n]);

  for (let total = 1n; total < 500n; total += 7n) {
    for (let n = 1; n <= 9; n++) {
      const shares = splitEqually(total, n);
      assert.equal(shares.reduce((a, b) => a + b, 0n), total);
      const max = shares.reduce((a, b) => (b > a ? b : a));
      const min = shares.reduce((a, b) => (b < a ? b : a));
      assert.ok(max - min <= 1n);
    }
  }
});

test('parse/format round-trip shows no floating-point drift (0.1 + 0.2)', () => {
  assert.equal(formatCents(parseAmount('0.10') + parseAmount('0.20')), '0.30');
});
