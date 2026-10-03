import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import { MAX_AMOUNT_CENTS, formatMoney, parseMoney, splitEqually } from '../../src/domain/money.js';
import { ValidationError } from '../../src/errors.js';

describe('parseMoney', () => {
  it.each([
    ['0', 0n],
    ['12', 1200n],
    ['12.3', 1230n],
    ['12.34', 1234n],
    ['0.01', 1n],
    ['9999999999.99', 999999999999n],
  ])('parses %s to %s cents', (text, cents) => {
    expect(parseMoney(text)).toBe(cents);
  });

  it.each(['1.005', '-1', '1e3', '.5', '5.', ' 5', '', '1,00', '12345678901'])(
    'rejects %j',
    (text) => {
      expect(() => parseMoney(text)).toThrow(ValidationError);
    },
  );
});

describe('formatMoney', () => {
  it.each([
    [0n, '0.00'],
    [5n, '0.05'],
    [-333n, '-3.33'],
    [100000n, '1000.00'],
  ])('formats %s as %s', (cents, text) => {
    expect(formatMoney(cents)).toBe(text);
  });

  it('round-trips every valid amount', () => {
    fc.assert(
      fc.property(fc.bigInt({ min: 0n, max: MAX_AMOUNT_CENTS }), (cents) => {
        expect(parseMoney(formatMoney(cents))).toBe(cents);
      }),
    );
  });
});

describe('splitEqually', () => {
  it('gives leftover cents to the first shares', () => {
    expect(splitEqually(1000n, 3)).toEqual([334n, 333n, 333n]);
    expect(splitEqually(2n, 3)).toEqual([1n, 1n, 0n]);
    expect(splitEqually(0n, 1)).toEqual([0n]);
  });

  it('rejects invalid arguments', () => {
    expect(() => splitEqually(-1n, 2)).toThrow(RangeError);
    expect(() => splitEqually(10n, 0)).toThrow(RangeError);
    expect(() => splitEqually(10n, 1.5)).toThrow(RangeError);
  });

  it('conserves the total, spreads by at most 1 cent, and is non-increasing', () => {
    fc.assert(
      fc.property(
        fc.bigInt({ min: 0n, max: MAX_AMOUNT_CENTS }),
        fc.integer({ min: 1, max: 100 }),
        (total, count) => {
          const shares = splitEqually(total, count);
          expect(shares).toHaveLength(count);
          expect(shares.reduce((a, b) => a + b, 0n)).toBe(total);
          const first = shares[0] as bigint;
          const last = shares[shares.length - 1] as bigint;
          expect(first - last <= 1n).toBe(true);
          for (let i = 1; i < shares.length; i++) {
            expect((shares[i] as bigint) <= (shares[i - 1] as bigint)).toBe(true);
          }
        },
      ),
    );
  });
});
