// Money is represented internally as an integer number of cents (BigInt), so
// every calculation is exact. Amounts cross the API boundary as decimal strings
// ("12.50") so they never pass through a binary floating-point number.

export class MoneyError extends Error {}

// Up to 15 integer digits keeps any realistic total far from 64-bit limits.
const AMOUNT_RE = /^(0|[1-9]\d{0,14})(?:\.(\d{1,2}))?$/;

/** Parse a positive decimal string such as "12.5" or "12.50" into cents. */
export function parseAmount(input) {
  if (typeof input !== 'string') {
    throw new MoneyError('amount must be a decimal string, e.g. "12.50"');
  }
  const match = AMOUNT_RE.exec(input);
  if (!match) {
    throw new MoneyError('amount must be a non-negative decimal with at most 2 decimal places, e.g. "12.50"');
  }
  const cents = BigInt(match[1]) * 100n + BigInt((match[2] ?? '').padEnd(2, '0'));
  if (cents <= 0n) throw new MoneyError('amount must be greater than zero');
  return cents;
}

/** Format cents as a decimal string, e.g. -1234n -> "-12.34". */
export function formatCents(cents) {
  const negative = cents < 0n;
  const abs = negative ? -cents : cents;
  const fraction = (abs % 100n).toString().padStart(2, '0');
  return `${negative ? '-' : ''}${abs / 100n}.${fraction}`;
}

/**
 * Split `total` cents into `count` shares that differ by at most one cent and
 * sum exactly to `total`. Leftover cents go to the earliest shares.
 */
export function splitEqually(total, count) {
  if (!Number.isInteger(count) || count <= 0) throw new MoneyError('count must be a positive integer');
  const n = BigInt(count);
  const base = total / n;
  const remainder = total % n;
  return Array.from({ length: count }, (_, i) => base + (BigInt(i) < remainder ? 1n : 0n));
}
