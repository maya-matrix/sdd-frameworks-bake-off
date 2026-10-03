/**
 * Money is represented as a bigint count of minor units (cents).
 * Conversion to and from strings never goes through floating point.
 */
export type Cents = bigint;

export const AMOUNT_PATTERN = /^\d+(\.\d{1,2})?$/;

export class InvalidAmountError extends Error {
  constructor(input: unknown) {
    super(`Invalid amount: ${JSON.stringify(input)}`);
    this.name = "InvalidAmountError";
  }
}

/** Parses a non-negative decimal string with at most two fraction digits into cents. */
export function parseAmount(input: string): Cents {
  if (typeof input !== "string" || !AMOUNT_PATTERN.test(input)) {
    throw new InvalidAmountError(input);
  }
  const [whole = "0", fraction = ""] = input.split(".");
  return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
}

/** Formats cents as a decimal string with exactly two fraction digits, e.g. -15n → "-0.15". */
export function formatAmount(cents: Cents): string {
  const negative = cents < 0n;
  const abs = negative ? -cents : cents;
  const whole = abs / 100n;
  const fraction = (abs % 100n).toString().padStart(2, "0");
  return `${negative ? "-" : ""}${whole}.${fraction}`;
}

/** Basis points: hundredths of a percent, so 100% is 10000n. */
export type BasisPoints = bigint;

export const FULL_PERCENTAGE: BasisPoints = 10_000n;

/**
 * Parses a percentage string between "0" and "100" with at most two fraction
 * digits into basis points ("33.33" → 3333n). Uses the same exact parsing as amounts.
 */
export function parsePercentage(input: string): BasisPoints {
  const basisPoints = parseAmount(input);
  if (basisPoints > FULL_PERCENTAGE) {
    throw new InvalidAmountError(input);
  }
  return basisPoints;
}

/** Formats basis points as a percentage with exactly two fraction digits, e.g. 6000n → "60.00". */
export function formatPercentage(basisPoints: BasisPoints): string {
  return formatAmount(basisPoints);
}
