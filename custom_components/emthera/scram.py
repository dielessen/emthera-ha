"""The client side of the E32's sign-in exchange: SCRAM-SHA-256 (RFC 5802, SHA-256 profile RFC 7677).

Standard constructions only, all from the standard library: PBKDF2-HMAC-SHA-256 (RFC 8018) for ``Hi``, HMAC
(RFC 2104) and SHA-256 (FIPS 180-4) through ``hashlib`` and ``hmac``, and ``hmac.compare_digest`` wherever a secret
or a proof is compared. Nothing here is home-made.

What is adapted, deliberately (HUB-TLS-plan.md section 4.1):

* The transport is the E32's own form routes, not SASL. The RFC's text forms (``n=,r=`` and so on) are used only as
  the HMAC input (the AuthMessage), so the RFC 7677 test vector applies verbatim (test_controller_scram.py).
* No SASLprep (RFC 4013, RFC 7613): the E32 hashes the raw UTF-8 bytes of the password (WebPassword.h), so a
  password it already stores must keep working byte for byte.
* No channel binding (the ``c=biws`` of the RFC: "n,," in base64).
* The user name is fixed: ``admin``.

What it protects against and what it does not: the password is never sent, and a recorded exchange cannot be replayed
(each challenge is used once). It does not hide the session cookie that follows on plain http, and it does not stop
someone in the middle of a plain http connection; https does that.

Nothing in this module logs, keeps or returns a password except as the salted value the exchange needs.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets

ALGORITHM = "SCRAM-SHA-256"
# What the device advertises in GET /auth/version ("auth": [...]).
OFFER = "scram-sha-256"
USERNAME = "admin"
# The iteration count the E32 stores (WebPassword.h) and the lowest one this client accepts (the downgrade guard);
# the highest is the E32's own decode limit.
STORED_ITERATIONS = 4096
MIN_ITERATIONS = 4096
MAX_ITERATIONS = 200000
SALT_BYTES = 16
# The client nonce: 18 random bytes, base64 (24 characters, no comma).
CLIENT_NONCE_BYTES = 18
# The E32's password rule (WebPassword::checkNew), counted in characters.
NEW_PASSWORD_MIN, NEW_PASSWORD_MAX = 8, 64
# "n,," in base64: the gs2 header of a client that does not use channel binding (RFC 5802 section 7).
GS2_HEADER_B64 = "biws"


class ScramError(ValueError):
    """The device's challenge or answer broke the exchange; a bounded code, never a secret."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def new_client_nonce():
    return base64.b64encode(secrets.token_bytes(CLIENT_NONCE_BYTES)).decode("ascii")


def _b64(data):
    return base64.b64encode(data).decode("ascii")


def decode_b64(text, *, length=None, minimum=None, maximum=None):
    """Strict canonical base64 of bytes of the stated size, or ScramError("scram_invalid")."""
    if type(text) is not str or not text.isascii():
        raise ScramError("scram_invalid")
    try:
        raw = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        raise ScramError("scram_invalid") from None
    if _b64(raw) != text:  # canonical: the AuthMessage must hold the device's own text
        raise ScramError("scram_invalid")
    if length is not None and len(raw) != length:
        raise ScramError("scram_invalid")
    if minimum is not None and len(raw) < minimum or maximum is not None and len(raw) > maximum:
        raise ScramError("scram_invalid")
    return raw


def salted_password(password, salt, iterations):
    """Hi(password, salt, i): PBKDF2-HMAC-SHA-256, 32 bytes (RFC 5802 section 2.2, RFC 8018)."""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, 32)


def _hmac(key, message):
    return hmac.new(key, message, hashlib.sha256).digest()


def auth_message(cnonce, combined, salt_b64, iterations, username=USERNAME):
    """client-first-message-bare "," server-first-message "," client-final-message-without-proof (RFC 5802 section 3)."""
    return (f"n={username},r={cnonce},r={combined},s={salt_b64},i={iterations},"
            f"c={GS2_HEADER_B64},r={combined}").encode("ascii")


def client_proof(salted, message):
    """ClientProof = ClientKey XOR HMAC(StoredKey, AuthMessage), with the keys of RFC 5802 section 3."""
    client_key = _hmac(salted, b"Client Key")
    signature = _hmac(hashlib.sha256(client_key).digest(), message)
    return bytes(a ^ b for a, b in zip(client_key, signature))


def server_signature(salted, message):
    """ServerSignature = HMAC(ServerKey, AuthMessage): what the device returns to prove it knows the verifier."""
    return _hmac(_hmac(salted, b"Server Key"), message)


class Challenge:
    """The device's answer to POST /auth/challenge, checked: nonce, salt and iterations as the exchange needs them."""

    __slots__ = ("cnonce", "nonce", "salt_b64", "salt", "iterations", "new_salt_b64", "new_salt")

    def __init__(self, cnonce, document, *, want_new_salt=False):
        if type(document) is not dict or document.get("alg") != ALGORITHM:
            raise ScramError("scram_invalid")
        nonce, iterations = document.get("nonce"), document.get("iterations")
        if (type(nonce) is not str or not cnonce or not nonce.startswith(cnonce) or len(nonce) <= len(cnonce)
                or len(nonce) > 128 or "," in nonce or not nonce.isascii() or not nonce.isprintable()):
            raise ScramError("scram_invalid")
        if type(iterations) is not int or isinstance(iterations, bool):
            raise ScramError("scram_invalid")
        if iterations < MIN_ITERATIONS or iterations > MAX_ITERATIONS:
            raise ScramError("scram_weak")  # fewer rounds than the E32 stores: a downgrade, never accepted
        self.cnonce, self.nonce, self.iterations = cnonce, nonce, iterations
        self.salt_b64 = document.get("salt")
        self.salt = decode_b64(self.salt_b64, minimum=8, maximum=64)
        self.new_salt_b64 = self.new_salt = None
        if want_new_salt:
            self.new_salt_b64 = document.get("new_salt")
            self.new_salt = decode_b64(self.new_salt_b64, length=SALT_BYTES)

    def message(self):
        return auth_message(self.cnonce, self.nonce, self.salt_b64, self.iterations)


def prove(challenge, password):
    """(the proof to send as base64, the signature the device must return), both computed from ``password``."""
    salted = salted_password(password, challenge.salt, challenge.iterations)
    message = challenge.message()
    return _b64(client_proof(salted, message)), server_signature(salted, message)


def check_signature(expected, received_b64):
    """True when the device's server_signature equals the expected one (constant time)."""
    try:
        received = decode_b64(received_b64, length=32)
    except ScramError:
        return False
    return hmac.compare_digest(expected, received)


def new_salted_password(password, salt):
    """Hi(new password, the device's new salt, 4096) as base64: what POST /auth/password carries instead of the password."""
    return _b64(salted_password(password, salt, STORED_ITERATIONS))
