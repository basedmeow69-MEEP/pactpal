import pytest

from pactpal.mandate import MandateViolation, SpendMandate, authorize_spend, sign, verify

SECRET = "x" * 32
MANDATE = SpendMandate("pact-1", "390.00", "USD", "seller@example.com", "ab" * 32, expires_at=2000)


def test_round_trip_and_limits():
    mandate = verify(sign(MANDATE, SECRET), SECRET, now=1000)
    assert mandate == MANDATE
    authorize_spend(mandate, amount="390.00", currency="USD", payee_email="Seller@Example.com")
    for kwargs, message in [
        ({"amount": "390.01", "currency": "USD", "payee_email": "seller@example.com"}, "ceiling"),
        ({"amount": "10.00", "currency": "EUR", "payee_email": "seller@example.com"}, "currency"),
        ({"amount": "10.00", "currency": "USD", "payee_email": "other@example.com"}, "payee"),
    ]:
        with pytest.raises(MandateViolation, match=message):
            authorize_spend(mandate, **kwargs)


def test_rejects_tampering_wrong_secret_and_expiry():
    token = sign(MANDATE, SECRET)
    payload, signature = token.split(".")
    forged = sign(SpendMandate("pact-1", "9999.00", "USD", "seller@example.com", "ab" * 32, 2000), "y" * 32)
    for bad in [forged.split(".")[0] + "." + signature, payload + ".AAAA", "garbage"]:
        with pytest.raises(MandateViolation):
            verify(bad, SECRET, now=1000)
    with pytest.raises(MandateViolation, match="signature"):
        verify(token, "y" * 32, now=1000)
    with pytest.raises(MandateViolation, match="expired"):
        verify(token, SECRET, now=2000)
