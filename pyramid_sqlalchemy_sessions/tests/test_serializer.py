import pytest
import hypothesis.strategies as st
from base64 import urlsafe_b64encode
from hypothesis import given

from ..exceptions import (
    InvalidCookieError,
    CookieCryptoError,
)
from ..serializer import (
    AESGCMBytestore,
    SECRET_SIZES,
)
from .strategies import secret_bytes


@given(
    data=st.binary(max_size=32),
    secret=secret_bytes(),
)
def test_dumped_equals_loaded(data, secret):
    serializer = AESGCMBytestore(secret)
    assert serializer.loads(serializer.dumps(data)) == data


@given(secret=st.binary().filter(lambda s: len(s) not in SECRET_SIZES))
def test_secret(secret):
    with pytest.raises(ValueError):
        serializer = AESGCMBytestore(secret)


@given(
    secret=secret_bytes(),
    short=st.binary(max_size=31),
    random=st.binary(min_size=32, max_size=64),
    b64=st.builds(
        urlsafe_b64encode,
        st.binary(min_size=32, max_size=64),
    ),
)
def test_invalid_payload(secret, short, random, b64):
    serializer = AESGCMBytestore(secret)
    with pytest.raises(InvalidCookieError):
        serializer.loads(short)
    with pytest.raises((InvalidCookieError, CookieCryptoError)):
        serializer.loads(random)
    with pytest.raises(CookieCryptoError):
        serializer.loads(b64)
