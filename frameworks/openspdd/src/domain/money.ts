import { ValidationError } from '../errors.js';

/** Largest accepted expense amount: 9,999,999,999.99. */
export const MAX_AMOUNT_CENTS = 999_999_999_999n;

const MONEY_PATTERN = /^(\d{1,10})(?:\.(\d{1,2}))?$/;

/**
 * Parses a non-negative decimal string with at most 2 decimal places into exact cents.
 * Uses only string and bigint arithmetic. May return 0n; positivity is the caller's rule.
 */
export function parseMoney(text: string): bigint {
  const match = MONEY_PATTERN.exec(text);
  if (match === null) {
    throw new ValidationError('amount must be a decimal string with at most 2 decimal places', {
      amount: text,
    });
  }
  const [, intPart = '0', fracPart] = match;
  const fraction = (fracPart ?? '').padEnd(2, '0');
  return BigInt(intPart) * 100n + BigInt(fraction);
}

/** Formats cents as a decimal string with exactly 2 decimals; 0n is "0.00", never "-0.00". */
export function formatMoney(cents: bigint): string {
  const sign = cents < 0n ? '-' : '';
  const abs = cents < 0n ? -cents : cents;
  return `${sign}${abs / 100n}.${(abs % 100n).toString().padStart(2, '0')}`;
}

/**
 * Splits total into count shares. Shares sum exactly to total, differ by at most 1 cent,
 * and the leftover cents go to the first shares (result is non-increasing).
 */
export function splitEqually(total: bigint, count: number): bigint[] {
  if (total < 0n) {
    throw new RangeError('total must be non-negative');
  }
  if (!Number.isInteger(count) || count < 1) {
    throw new RangeError('count must be a positive integer');
  }
  const n = BigInt(count);
  const base = total / n;
  const remainder = Number(total % n);
  return Array.from({ length: count }, (_, i) => (i < remainder ? base + 1n : base));
}
