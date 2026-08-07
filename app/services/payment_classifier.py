# This module provides the common SQL snippet for classifying payment types.
# It can be injected into the SELECT queries during the aggregation phase.

PAYMENT_TYPE_CASE_SQL = """
    CASE
        WHEN LOWER(payment_gateway_names) LIKE '%gokwik ppcod%' THEN 'PPCOD'
        WHEN (payment_gateway_names IS NULL
            OR payment_gateway_names = ''
            OR payment_gateway_names LIKE '%Cash on Delivery (COD)%'
            OR payment_gateway_names LIKE '%cash_on_delivery%')
            AND (payment_gateway_names NOT LIKE '%Gokwik PPCOD%' OR payment_gateway_names IS NULL)
            THEN 'COD'
        ELSE 'PREPAID'
    END
"""


def classify_payment_type(payment_gateway_names: str | None) -> str:
    """Python port of PAYMENT_TYPE_CASE_SQL, for classifying rows fetched from GraphQL."""
    names = (payment_gateway_names or "").strip().lower()
    if "gokwik ppcod" in names:
        return "PPCOD"
    if not names or "cash on delivery (cod)" in names or "cash_on_delivery" in names:
        return "COD"
    return "PREPAID"
