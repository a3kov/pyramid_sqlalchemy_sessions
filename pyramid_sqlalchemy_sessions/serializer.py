from base64 import (
    urlsafe_b64decode,
    urlsafe_b64encode,
)

from Cryptodome.Cipher import AES

from .exceptions import (
    InvalidCookieError,
    CookieCryptoError,
)


SECRET_SIZES = (16, 24, 32)


class AESGCMBytestore():
    """ Serializer, that uses AES-GCM authenticated encryption to store
    bytes data. """
    nonce_size = 16
    tag_size = 16

    def __init__(self, secret):
        is_bytes = isinstance(secret, bytes)
        if not is_bytes or len(secret) not in SECRET_SIZES:
            raise ValueError(
                "Secret should be a bytes object with size of %s"
                % repr(SECRET_SIZES)
            )
        self.secret = secret

    def loads(self, encoded):
        try:
            decoded = urlsafe_b64decode(encoded)
        except ValueError as e:
            raise InvalidCookieError(e)

        decoded_len = len(decoded)
        n, t = self.nonce_size, self.tag_size
        if decoded_len < n + t:
            raise InvalidCookieError(
                "Cookie size is incorrect: %d bytes (expected atleast %d)"
                % (decoded_len, n + t)
            )
        elif decoded_len == n + t:
            ciphertext = b''
        else:
            ciphertext = decoded[n + t:]
        # Support AAD ?
        nonce = decoded[:n]
        tag = decoded[n:n + t]
        cipher = AES.new(self.secret, AES.MODE_GCM, nonce)
        try:
            data = cipher.decrypt_and_verify(ciphertext, tag)
        except ValueError as e:
            raise CookieCryptoError(e)
        return data

    def dumps(self, data):
        cipher = AES.new(self.secret, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        encoded = urlsafe_b64encode(cipher.nonce + tag + ciphertext)
        return encoded
