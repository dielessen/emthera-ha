"""Pinning the Hub's public key for the https link (HUB-TLS P10).

The Hub makes its own key and a self-made certificate, so the usual chain of trust has nothing to check. Home Assistant
instead remembers the SHA-256 of the certificate's public key (the SubjectPublicKeyInfo, the form of RFC 7469 pins) the
first time the owner connects and confirms it (trust on first use), and refuses every later connection whose key is
different. The Hub renews its certificate with the same key, so a renewal does not change the pin; a new key (a reset
by the owner, a replaced board) does, and is never accepted silently: Home Assistant raises a Repairs issue that shows
the old and the new fingerprint and asks the owner to confirm the new one.

How the pin is checked, in the aiohttp that Home Assistant ships (verified on 3.14.4 and 3.14.5, Home Assistant 2026.10
and 2026.11): ``TCPConnector(ssl=<an aiohttp.Fingerprint>)`` makes the connection with an unverified TLS context and
then calls ``Fingerprint.check(transport)`` before the first byte of the request is sent. The stock class hashes the
whole certificate and returns without checking when the transport carries no TLS context; SpkiPin replaces check():
it hashes the public key and fails closed (a missing certificate is a mismatch).

What a pin protects against and what it does not: it makes sure that the party answering is the one the owner
confirmed, and the link is encrypted, so the password, the session cookie and the settings do not cross the network
in clear. It does not protect the first connection against someone who is already between Home Assistant and the Hub
at that moment (trust on first use); comparing the fingerprint with the one the Hub shows on its own page closes that
gap. It says nothing about the http listener the Hub keeps for browsers.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass
import datetime
import hashlib
import hmac
import ipaddress
import ssl
import weakref

import aiohttp
from aiohttp.client_exceptions import ServerFingerprintMismatch
from cryptography import x509
from cryptography.hazmat.primitives import serialization

# The entry data key: base64 of the 32-byte SHA-256 of the public key (the form of "pin-sha256" in RFC 7469).
PIN_KEY = "controller_pin"
PROBE_TIMEOUT_S = 8


class PinError(ValueError):
    """A bounded code, never a certificate or an address."""


def spki_sha256(certificate_der):
    """SHA-256 of the certificate's SubjectPublicKeyInfo (DER), the pin of RFC 7469."""
    certificate = x509.load_der_x509_certificate(certificate_der)
    spki = certificate.public_key().public_bytes(serialization.Encoding.DER,
                                                 serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(spki).digest()


def pin_text(spki):
    return base64.b64encode(spki).decode("ascii")


def parse_pin(text):
    """The 32 bytes of a stored pin (base64), or PinError("controller_pin_invalid")."""
    try:
        if type(text) is not str or not text.isascii():
            raise ValueError
        raw = base64.b64decode(text, validate=True)
        if len(raw) != 32 or pin_text(raw) != text:
            raise ValueError
    except (ValueError, binascii.Error):
        raise PinError("controller_pin_invalid") from None
    return raw


def hex_pairs(spki):
    """The fingerprint as the owner compares it: 32 uppercase hex pairs separated by colons."""
    return ":".join(f"{byte:02X}" for byte in spki)


def same_fingerprint(spki, text):
    """True when ``text`` (hex pairs with or without separators, any case, or the base64 form) is this key."""
    if type(text) is not str:
        return False
    plain = text.replace(":", "").replace(" ", "").replace("-", "")
    candidates = []
    try:
        candidates.append(bytes.fromhex(plain))
    except ValueError:
        pass
    try:
        candidates.append(parse_pin(text.strip()))
    except PinError:
        pass
    return any(len(c) == len(spki) and hmac.compare_digest(c, spki) for c in candidates)


class SpkiPin(aiohttp.Fingerprint):
    """aiohttp's own pin hook, pinned to the public key and failing closed.

    ``Fingerprint.check`` is called with the connected transport before any request byte is written. The parent hashes
    the certificate bytes and returns silently without a TLS context; this one hashes the public key (so a renewal with
    the same key keeps working) and treats a missing certificate, an unreadable one and a different key alike.
    """

    def __init__(self, spki):
        super().__init__(spki)  # 32 bytes (sha256); aiohttp refuses md5 and sha1 lengths

    def check(self, transport):
        got = b""
        try:
            sslobj = transport.get_extra_info("ssl_object")
            certificate = sslobj.getpeercert(binary_form=True) if sslobj is not None else None
            got = spki_sha256(certificate) if certificate else b""
        except Exception:  # an unreadable certificate is not the pinned key
            got = b""
        if not got or not hmac.compare_digest(got, self.fingerprint):
            peer = transport.get_extra_info("peername") or ("", 0)
            raise ServerFingerprintMismatch(self.fingerprint, got, peer[0], peer[1])


# {event loop: {Hub address: 32-byte pin}}: what Home Assistant has confirmed, loaded from the entries at set-up.
_PINS = weakref.WeakKeyDictionary()


def _pins():
    return _PINS.setdefault(asyncio.get_running_loop(), {})


def register_pin(address, spki):
    if type(spki) is not bytes or len(spki) != 32:
        raise PinError("controller_pin_invalid")
    _pins()[address] = spki


def pin_for(address):
    return _pins().get(address)


def forget_pin(address):
    _pins().pop(address, None)


@dataclass(frozen=True)
class HubIdentity:
    """What a Hub shows at the handshake: its key's pin and what the owner can compare (nothing here is secret)."""
    spki: bytes
    names: tuple
    not_before: datetime.datetime
    not_after: datetime.datetime

    @property
    def fingerprint(self):
        return hex_pairs(self.spki)


def identity_of(certificate_der):
    certificate = x509.load_der_x509_certificate(certificate_der)
    names = []
    try:
        san = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        names = [*san.get_values_for_type(x509.DNSName), *(str(ip) for ip in san.get_values_for_type(x509.IPAddress))]
    except x509.ExtensionNotFound:
        pass
    return HubIdentity(spki_sha256(certificate_der), tuple(names), certificate.not_valid_before_utc,
                       certificate.not_valid_after_utc)


def _check_address(address):
    from .controller_link import controller_address
    return controller_address(address)


async def async_probe(address, *, timeout=PROBE_TIMEOUT_S):
    """Make the TLS handshake with the Hub at an https address and read what it presents; send nothing.

    The context verifies nothing on purpose (this is the moment the owner decides whom to trust), so the result is
    shown to the owner and never trusted by itself. ControllerLinkError("controller_probe_failed") when there is no
    TLS answer, "controller_address_invalid" for an address that is not a local https address.
    """
    from .controller_link import ControllerLinkError, PrivateResolver
    address = _check_address(address)
    if not address.startswith("https://"):
        raise ControllerLinkError("controller_address_invalid")
    from yarl import URL
    url = URL(address)
    host, port = url.raw_host, url.port or 443
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # no default certificates are loaded: nothing is verified
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    writer = None
    try:
        try:
            ipaddress.ip_address(host)
            target = host
        except ValueError:
            target = (await PrivateResolver().resolve(host, port))[0]["host"]
        async with asyncio.timeout(timeout):
            _, writer = await asyncio.open_connection(target, port, ssl=context, server_hostname=host)
        certificate = writer.get_extra_info("ssl_object").getpeercert(binary_form=True)
        return identity_of(certificate)
    except (OSError, ssl.SSLError, TimeoutError, ValueError, AttributeError):
        raise ControllerLinkError("controller_probe_failed") from None
    finally:
        if writer is not None:
            writer.close()
            try:
                async with asyncio.timeout(2):
                    await writer.wait_closed()
            except (OSError, ssl.SSLError, TimeoutError):
                pass
