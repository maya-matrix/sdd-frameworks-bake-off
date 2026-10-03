import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { formatAmount, InvalidAmountError, parseAmount } from "../../src/domain/money.js";

describe("parseAmount", () => {
  it.each([
    ["7.5", 750n],
    ["0.10", 10n],
    ["0.1", 10n],
    ["12", 1200n],
    ["0", 0n],
    ["1000000000.00", 100000000000n],
  ])("parses %s to %s cents", (input, expected) => {
    expect(parseAmount(input)).toBe(expected);
  });

  it.each(["10.005", "-1", "1e3", "", " 1", "1 ", "1.", ".5", "abc", "1,00", "0x10"])(
    "rejects %j",
    (input) => {
      expect(() => parseAmount(input)).toThrow(InvalidAmountError);
    },
  );

  it("rejects non-string input", () => {
    expect(() => parseAmount(12.5 as unknown as string)).toThrow(InvalidAmountError);
  });
});

describe("formatAmount", () => {
  it.each([
    [0n, "0.00"],
    [5n, "0.05"],
    [750n, "7.50"],
    [-15n, "-0.15"],
    [-1000n, "-10.00"],
    [100000000000n, "1000000000.00"],
  ])("formats %s as %s", (cents, expected) => {
    expect(formatAmount(cents)).toBe(expected);
  });

  it("round-trips any non-negative cent value", () => {
    fc.assert(
      fc.property(fc.bigInt({ min: 0n, max: 10n ** 15n }), (cents) => {
        expect(parseAmount(formatAmount(cents))).toBe(cents);
      }),
    );
  });
});
