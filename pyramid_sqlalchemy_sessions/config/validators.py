import itertools
import string

from pyramid.settings import asbool


none_variants = tuple(sorted(map(
    ''.join,
    itertools.product(*zip('None'.upper(), 'None'.lower()))
)) + [None])
# rfc2616 token
token_alphabet = string.ascii_letters + string.digits + "!#$%&'*+-.^_`|~"
# pep-3131 describes non-ascii identifiers, but for simplicity we
# don't support it - its too exotic. Patches fixing this are welcome.
python_id_first_char_alphabet = ('_' + string.ascii_lowercase +
                                 string.ascii_uppercase)
python_id_alphabet = python_id_first_char_alphabet + string.digits
# ~ 3 years should be enough - this is delta and we need to store expiration
MAX_INTEGER = 100000000
MAX_SMALLINT = 32767
MAX_SHORT_VARCHAR = 255


def _validate_gt(names, values):
    if values[0] is None:
        return
    if values[1] is None:
        return
    if values[0] <= values[1]:
        raise ValueError(
            '%s setting should be greater than %s' % (names[0], names[1])
        )


def _validate_prob_extension(names, values):
    idle, delay, chance, dead = values
    if idle is None or chance == 100:
        return
    _validate_gt((names[0], names[3]), (idle, dead))
    if delay is not None:
        _validate_gt((names[3], names[1]), (dead, delay))


def _validate_cookie_domain(name, value):
    # Can't use none_variants because 'none' could be a valid string.
    if value is None:
        return value
    if isinstance(value, str) and len(value) > 0 and len(value) <= 255:
        return value
    else:
        raise ValueError(
            'Setting should be a non-empty string not longer than %d chars'
            ' or None: %s' % (MAX_SHORT_VARCHAR, name)
        )


def _validate_asbool(name, value):
    return asbool(value)


def _validate_int_size_none(name, value, max):
    if value in none_variants:
        return None
    else:
        try:
            value = int(value)
            assert 0 < value <= max
            return value
        except (ValueError, AssertionError) as e:
            raise ValueError(
                'Setting should be a positive integer (max %d) or None: %s'
                % (max, name)
            ) from e


def _validate_int_none(name, value):
    return _validate_int_size_none(name, value, MAX_INTEGER)


def _validate_smallint_none(name, value):
    return _validate_int_size_none(name, value, MAX_SMALLINT)


def _validate_positive_smallint(name, value):
    try:
        i = int(value)
        assert 0 < i <= MAX_SMALLINT
        return i
    except (ValueError, AssertionError) as e:
        raise ValueError(
            'Setting should be a positive smallint: %s' % name
        ) from e


def _validate_nonzero_percent(name, value):
    try:
        percent = int(value)
        assert 0 < percent <= 100
    except (ValueError, AssertionError) as e:
        raise ValueError(
            'Setting should be an 0 < int <= 100: %s' % name
        ) from e
    return percent


def _validate_python_id(name, value):
    try:
        assert isinstance(value, str) and len(value) != 0
        assert value[0] in python_id_first_char_alphabet
        if len(value) > 1:
            assert set(value[1:]) <= set(python_id_alphabet)
        return value
    except AssertionError as e:
        raise ValueError(
            'Setting should be a valid Python identifier: %s' % name
        ) from e


def _validate_rfc2616_token(name, value):
    if isinstance(value, str) and len(value) != 0:
        if set(value) <= set(token_alphabet):
            return value
    raise ValueError('Setting should be a valid rfc2616 token: %s' % name)


def _validate_cookie_path(name, value):
    # This is rather simplistic validation.
    if (isinstance(value, str) and
        len(value) != 0 and
        len(value) <= 255 and
        value[0] == '/'):

        return value
    raise ValueError(
        "%s should be a string not longer than %d chars starting with /"
        % (name, MAX_SHORT_VARCHAR)
    )
