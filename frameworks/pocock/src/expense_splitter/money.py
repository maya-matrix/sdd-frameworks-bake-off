"""Exact money arithmetic. Amounts are always integers in a Currency's minor units (ADR 0002)."""

# ISO 4217 codes whose minor unit is exactly 2 decimal places. Currencies with 0 or 3
# decimals (JPY, KWD, ...) are deliberately unsupported.
SUPPORTED_CURRENCIES = frozenset(
    {
        "AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP",
        "HKD", "ILS", "INR", "MXN", "NOK", "NZD", "PLN", "RON", "SEK", "SGD",
        "THB", "TRY", "USD", "ZAR",
    }
)  # fmt: skip
