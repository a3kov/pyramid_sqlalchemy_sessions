import itertools
import math
import string

import collections.abc
import hypothesis.strategies as st

from ..config import (
    RUNTIME_SETTINGS,
    SECRET_SIZES,
)
from ..config.validators import (
    MAX_INTEGER,
    MAX_SMALLINT,
    none_variants,
    token_alphabet,
)


prefix_alphabet = ('_-.' + string.digits + string.ascii_lowercase + 
                   string.ascii_uppercase)


def get_asbool_truthy_variants():
    from pyramid.settings import truthy
    """ Returns a tuple containing all possible asbool truthy values. """
    variants = set()
    for value in itertools.chain(truthy):
        variants |= set(map(
            ''.join,
            itertools.product(*zip(value.upper(), value.lower()))
        ))
    return tuple(sorted(variants) + [True, 1])

asbool_truthy = get_asbool_truthy_variants()


def none_or_positive_int(min=1, max=MAX_INTEGER):
    return st.one_of(
        st.none(),
        st.integers(min_value=min, max_value=max),
    )


def failing_nonzero_int(max=MAX_INTEGER):
    def not_int(value):
        try:
            x = int(value)
            return False
        except ValueError:
            return True
    return st.one_of(
        st.text(max_size=255).filter(not_int),
        st.integers(min_value=max + 1),
        st.integers(max_value=-1),
    )


def shared_prefix():
    return st.shared(
        st.text(prefix_alphabet, max_size=32),
        key='prefix'
    )


@st.composite
def shared_config(draw):
    return {
        'enable_userid': draw(st.shared(
            st.sampled_from([False] + [True] * 3),
            key='enable_userid'
            )),
        'enable_csrf': draw(st.shared(
            st.sampled_from([False] + [True] * 3),
            key='enable_csrf'
            )),
        'enable_configcookie': draw(st.shared(
            st.booleans(),
            key='enable_configcookie'
            )),
        'config_renewal': draw(st.shared(
            st.sampled_from([None] + [True, False] * 3),
            key='config_renewal'
            )),
        'config_idle': draw(st.shared(
            st.sampled_from([None] + [True, False] * 3),
            key='config_idle'
            )),
        'config_absolute': draw(st.shared(
            st.sampled_from([None] + [True, False] * 3),
            key='config_absolute'
            )),
    }


@st.composite
def interdependent_timeout_settings(draw):
    return {
        'idle_timeout': draw(none_or_positive_int(min=300, max=3600)),
        'absolute_timeout': draw(none_or_positive_int(min=24*3600)),
        'renewal_timeout': draw(none_or_positive_int(min=60, max=3600)),
        'extension_delay': draw(none_or_positive_int(min=5, max=60)),
        'extension_deadline': draw(st.integers(min_value=61, max_value=120)),
        'extension_chance': draw(st.integers(min_value=1, max_value=100)),
    }


class valid_interdependent_timeouts:
    def __init__(self, shared):
        self.s = shared

    def __call__(self, c):
        abs = c['absolute_timeout']
        idle = c['idle_timeout']
        ren = c['renewal_timeout']
        ext = c['extension_delay']
        dead = c['extension_deadline']
        chance = c['extension_chance']
        try:
            if abs is not None and idle is not None:
                assert abs > idle
            if idle is not None:
                if ext is not None:
                    assert idle > ext
                if chance < 100:
                    assert idle > dead
                    if ext is not None:
                        assert dead > ext
            if self.s['config_renewal'] is None:
                assert ren is None
            if self.s['config_idle'] is None:
                assert idle is None
            if self.s['config_absolute'] is None:
                assert abs is None
            return True
        except AssertionError:
            return False


@st.composite
def valid_model_class(draw):
    from sqlalchemy.ext.declarative import declarative_base
    from ..model import (
        BaseMixin,
        UseridMixin,
        CSRFMixin,
        RenewalMixin,
        IdleMixin,
        AbsoluteMixin,
        ConfigCookieMixin,
        ConfigIdleMixin,
        ConfigAbsoluteMixin,
        ConfigRenewalMixin,
        )
    Base = declarative_base()
    bases = [Base, BaseMixin]
    shared = draw(shared_config())
    if shared['enable_userid']:
        bases.append(UseridMixin)
    if shared['enable_csrf']:
        bases.append(CSRFMixin)
    if shared['enable_configcookie']:
        bases.append(ConfigCookieMixin)

    runtime_mixins = (
        ('config_renewal', ConfigRenewalMixin, RenewalMixin),
        ('config_idle', ConfigIdleMixin, IdleMixin),
        ('config_absolute', ConfigAbsoluteMixin, AbsoluteMixin),
    )
    for name, config_mixin, mixin in runtime_mixins:
        if shared[name] is True:
            bases.append(config_mixin)
        elif shared[name] is False:
            bases.append(mixin)
    bases = tuple(reversed(bases))
    cls = type('TestSessionModel', bases, {'__tablename__': 'test_session'})
    return cls


@st.composite
def valid_settings(draw):
    """ Valid combination of settings. Every setting is provided, and has
    python value (not an ini string variant). """
    from ..config import generate_secret_key
    settings = {
        'secret_key': draw(st.builds(
            generate_secret_key,
            st.sampled_from(SECRET_SIZES)
            )),
        'model_class': draw(valid_model_class()),
        'dbsession_name': 'dbsession',
        'cookie_name': draw(st.text(
            alphabet=token_alphabet, min_size=1, max_size=255
        )),
        'cookie_max_age': draw(none_or_positive_int()),
        'cookie_path': '/' + draw(st.text(string.printable, max_size=254)),
        'cookie_domain': draw(st.one_of(
            st.none(),
            st.text(string.printable, min_size=1, max_size=255),
            )),
        'cookie_secure': draw(st.booleans()),
        'cookie_httponly': draw(st.booleans()),
        'renewal_try_every': draw(st.integers(min_value=1, max_value=MAX_SMALLINT)),
    }
    shared = draw(shared_config())
    settings.update(draw(
        interdependent_timeout_settings().filter(
            valid_interdependent_timeouts(shared)
        )
    ))
    return settings


@st.composite
def with_ini_variants(draw, value):
    """ Replace python settings with their ini text variants. """
    if value is None:
        return draw(st.sampled_from(none_variants))
    if value is True:
        return draw(st.sampled_from(asbool_truthy))
    if isinstance(value, int):
        return str(value)
    return value


@st.composite
def not_provided(draw):
    share = 1
    pool_size = 10
    pool = [1] * share + [0] * (pool_size - share)
    return draw(st.sampled_from(pool))


@st.composite
def valid_ini_settings(draw):
    """ Combination of valid settings. Optional settings can be absent.
    Each settings value is an ini string variant. 
    Model class is very basic to test python dotted name variant."""
    from ..config import get_config_defaults
    from .model import DummySessionModel

    settings = draw(valid_settings())
    settings['model_class'] = draw(st.sampled_from((
        'pyramid_sqlalchemy_sessions.tests.model.DummySessionModel',
        DummySessionModel,
    )))
    # Add ini variants and prefix.
    prefix = draw(shared_prefix())
    have_defaults = get_config_defaults().keys()
    def should_provide(k):
        return not (k in have_defaults and draw(not_provided()))
    return {
        prefix + k: draw(with_ini_variants(v)) for k, v in settings.items()
        if should_provide(k)
    }


@st.composite
def invalid_ini_settings(draw):
    import base64
    from pyramid.compat import bytes_
    from ..config import SECRET_SIZES
    from .model import FailingSessionModel

    def secret_is_invalid(secret):
        # Make sure we don't generate valid key accidentally
        try:
            secret_bytes = base64.urlsafe_b64decode(bytes_(secret))
            return len(secret_bytes) not in SECRET_SIZES
        except:
            return True
    # Optional settings are always valid here: factory_args_from_settings does
    # not validate them.
    failing_strategies = {
        'secret_key': st.sampled_from((
            draw(st.sampled_from(none_variants)),
            draw(st.text(max_size=255)),
            draw(st.builds(base64.urlsafe_b64encode, st.binary(max_size=255))),
            )).filter(secret_is_invalid),
        'model_class': st.sampled_from((
            draw(st.sampled_from(none_variants)),
            draw(st.text(max_size=255)),
            'pyramid_sqlalchemy_sessions.tests.model.FailingSessionModel',
            FailingSessionModel,
            )),
    }
    valid_settings = draw(valid_ini_settings())
    failing_keys = draw(st.sampled_from((
        ('secret_key',),
        ('model_class',),
        ('secret_key', 'model_class'),
    )))
    invalid_settings = {}
    prefix = draw(shared_prefix())
    for key, strategy in failing_strategies.items():
        if key in failing_keys:
            value = draw(strategy)
            if not draw(not_provided()):
                invalid_settings[prefix + key] = value
        else:
            invalid_settings[prefix + key] = valid_settings[prefix + key]
    return invalid_settings


@st.composite
def invalid_declarative_model(draw):
    """ Create a declarative model that fails in different ways. """
    from ..model import (
        AbsoluteMixin,
        BaseMixin,
        CSRFMixin,
        ConfigAbsoluteMixin,
        ConfigCookieMixin,
        ConfigIdleMixin,
        ConfigRenewalMixin,
        IdleMixin,
        RenewalMixin,
        UseridMixin,
    )
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy import (
        Column,
        Integer,
        )
    # Prepare error pool.
    shared=draw(shared_config())
    runtime_mixins = (
        ('config_renewal', ConfigRenewalMixin, RenewalMixin),
        ('config_idle', ConfigIdleMixin, IdleMixin),
        ('config_absolute', ConfigAbsoluteMixin, AbsoluteMixin),
    )
    num_errors = 1
    for config, x, y in runtime_mixins:
        if shared[config] is not None:
            num_errors += 1
    model_errors = [
        lambda _: draw(st.booleans()) for _ in range(num_errors - 1)
    ]
    model_errors.append(True)  # guaranteed error
    model_errors = draw(st.permutations(model_errors))
    Base = declarative_base()
    bases = [Base]
    model_class_dict = {'__tablename__': 'test_session'}
    def maybe_valid():
        return not model_errors.pop()
    if maybe_valid():
        bases.append(BaseMixin)
    else:
        model_class_dict['id'] = Column(Integer, primary_key=True)

    # The following mixins don't trigger errors, but we use them to spice up
    # the model.
    if shared['enable_userid']:
        bases.append(UseridMixin)
    if shared['enable_csrf']:
        bases.append(CSRFMixin)
    if shared['enable_configcookie']:
        bases.append(ConfigCookieMixin)

    for name, config_mixin, mixin in runtime_mixins:
        if shared[name] is True:
            if maybe_valid(): bases.append(config_mixin)
        elif shared[name] is False:
            if maybe_valid(): bases.append(mixin)
        
    assert len(model_errors) == 0
    return type(
        'TestSessionModel',
        tuple(reversed(bases)),
        model_class_dict,
    )


@st.composite
def settings_failure_distribution(
    draw,
    simple_names,
    special_names,
    percents,
):
    """ Given lists of simple and special failure names,
    generate a mapping of every name to a bit flag (failed or not).
    Desired distribution of number of failures provided by the percents 
    distribution tuple (first value is percentage of examples with 1 failure,
    2nd - with 2 failures, ad so on). """
    
    simple_names = sorted(simple_names)
    special_names = sorted(special_names)
    all_names = simple_names + special_names

    simple_size = len(simple_names)
    special_size = len(special_names)
    total_size = simple_size + special_size
    # Distribution by percents of examples with number of failures, starting
    # from 1 
    pick = draw(st.integers(min_value=1, max_value=100))
    start = 0
    n = 0
    for percent in percents:
        if start < pick <= start + percents[n]:
            num_failures = n + 1
            break
        else:
            start += percents[n]
            n += 1

    def kbits(n, k):
        powers = [1 << e for e in range(n)]
        return {sum(bits) for bits in itertools.combinations(powers, k)}

    all_variants = []
    for l in kbits(simple_size, num_failures - 1):
        for r in kbits(special_size, 1):
            all_variants.append((l << special_size) | r)
    for l in kbits(simple_size, num_failures):
        for r in kbits(special_size, 0):
            all_variants.append((l << special_size) | r)
    bin_dist = format(
        draw(st.sampled_from(all_variants)),
        '0{s}b'.format(s=total_size)
    )
    assert len(bin_dist) == total_size
    return {k:int(v) for k, v in zip(all_names, bin_dist)}


@st.composite
def invalid_factory_args(draw):
    """ Invalid combinations of factory args. """

    # Create valid settings initially and add one or more defects later.
    # Asbool will eat almost anything as a boolean, so unless we add 
    # more restrictions on top, we are stuck with non-failing  
    # boolean settings (cookie_secure and  cookie_httponly).
    settings = draw(valid_settings())
    valid_settings_copy = settings.copy()
    settings['absolute_timeout'] = None
    settings['idle_timeout'] = None
    settings['renewal_timeout'] = None
    settings['extension_delay'] = None
    shared=draw(shared_config())
    # Strategies to fail simple (independent) settings. 
    failing_strategies = {
        'cookie_name': st.sampled_from((
            None,
            '',
            draw(st.text(max_size=255).filter(
                lambda x: not set(x) <= set(token_alphabet)
                )),
            )),
        'cookie_max_age': failing_nonzero_int(),
        'cookie_path': st.sampled_from((
            draw(st.booleans()),
            draw(st.text(max_size=255).filter(
                lambda x: x == '' or x[0] != '/'
                )),
            )),
        'cookie_domain': st.sampled_from((
            '',
            draw(st.integers(min_value=1)),
            draw(st.integers(max_value=-1)),
            )),
        'renewal_try_every': failing_nonzero_int(MAX_SMALLINT),
    }

    def fail_abs_idle():
        a, i = 2, 1
        while a > i:
            a = draw(st.integers(min_value=1, max_value=MAX_INTEGER))
            i = draw(st.integers(min_value=1, max_value=MAX_INTEGER))
        settings['absolute_timeout'] = a
        settings['idle_timeout'] = i   

    def fail_idle_delay():
        i, d = 2, 1
        while i > d:
            i = draw(st.integers(min_value=1, max_value=MAX_SMALLINT))
            d = draw(st.integers(min_value=1, max_value=MAX_SMALLINT))
        settings['idle_timeout'] = i
        settings['extension_delay'] = d

    def fail_idle_deadline():
        i, d = 2, 1
        while i > d:
            i = draw(st.integers(min_value=1, max_value=MAX_SMALLINT))
            d = draw(st.integers(min_value=1, max_value=MAX_SMALLINT))
        settings['idle_timeout'] = i
        settings['extension_deadline'] = d
        settings['extension_chance'] = draw(
            st.integers(min_value=1, max_value=99)
        )

    def fail_deadline_delay():
        a, b = 2, 1
        while a > b:
            a = draw(st.integers(min_value=1, max_value=MAX_SMALLINT))
            b = draw(st.integers(min_value=1, max_value=MAX_SMALLINT))
        settings['extension_deadline'] = a
        settings['extension_delay'] = b
        settings['idle_timeout'] = draw(
            st.integers(min_value=1, max_value=MAX_INTEGER)
        )
        settings['extension_chance'] = draw(
            st.integers(min_value=1, max_value=99)
        )

    def fail_renewal():
        settings['renewal_timeout'] = draw(failing_nonzero_int())

    def fail_idle():
        settings['idle_timeout'] = draw(failing_nonzero_int())

    def fail_absolute():
        settings['absolute_timeout'] = draw(failing_nonzero_int())

    def fail_delay():
        settings['extension_delay'] = draw(failing_nonzero_int(MAX_SMALLINT))

    def fail_deadline():
        settings['extension_deadline'] = draw(failing_nonzero_int(MAX_SMALLINT))

    def fail_chance():
        settings['extension_chance'] = draw(
            st.sampled_from((
                0,
                draw(failing_nonzero_int(100)),
            ))
        )

    def fail_model():
        # To trigger model failures we can't use disabled features - we have
        # to use (coordinated) settings from the original dict.
        coordinated = {
            'idle_timeout',
            'absolute_timeout',
            'renewal_timeout',
            'extension_delay',
            'extension_deadline',
            'extension_chance',
        }
        for name in coordinated:
            settings[name] = valid_settings_copy.get(name)
        settings['model_class'] = draw(
            invalid_declarative_model()
        )

    special_failures = {
        'fail_abs_idle': fail_abs_idle,
        'fail_idle_delay': fail_idle_delay,
        'fail_idle_deadline': fail_idle_deadline,
        'fail_deadline_delay': fail_deadline_delay,
        'fail_idle': fail_idle,
        'fail_absolute': fail_absolute, 
        'fail_renewal': fail_renewal,
        'fail_delay': fail_delay,
        'fail_deadline': fail_deadline,
        'fail_chance': fail_chance,
        'fail_model': fail_model,
    }
    # We are mostly interested in single failures
    # "special" failures are interdependent so it's better to only have one 
    # crafted "special" failure at a time.
    distribution = draw(settings_failure_distribution(
        failing_strategies.keys(), special_failures.keys(), (70, 15, 10, 5)
    ))
    for key, strategy in failing_strategies.items():
        if distribution[key]:
            print("Failing key: %s \n" % key)
            settings[key] = draw(strategy)

    for key, callback in special_failures.items():
        if distribution[key]:
            print("Failing key: %s\n" % key)
            callback()

    return {k: v for k, v in settings.items()}


@st.composite
def stable_extension_interdependent(draw):
    settings = draw(interdependent_timeout_settings())
    settings.update({
        'extension_chance': 100,
    })
    return settings


@st.composite
def unstable_extension_interdependent(draw):
    settings = draw(interdependent_timeout_settings())
    # Set min chance is not too low, so that the test doesn't last forever.
    settings.update({
        'extension_chance': draw(st.integers(min_value=50, max_value=99)),
    })
    return settings


@st.composite
def stable_extension_settings(draw):
    settings = draw(valid_settings())
    shared = draw(shared_config())
    settings.update(draw(
        stable_extension_interdependent().filter(
            valid_interdependent_timeouts(shared)
        )
    ))
    return settings


@st.composite
def unstable_extension_settings(draw):
    # Pre-seed random module - we could need it for weighted truth.
    draw(st.random_module())
    settings = draw(valid_settings())
    shared = draw(shared_config())
    settings.update(draw(
        unstable_extension_interdependent().filter(
            valid_interdependent_timeouts(shared)
        )
    ))
    return settings


def flat_pickles():
    # Only simple cases here.
    return st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(string.printable),
        st.binary(),
    )


@st.composite
def n_tuples(draw, values, max_size):
    return draw(st.tuples(
        *draw(st.lists(st.just(values), min_size=1, max_size=max_size))
    ))


def pickles_container(values):
    max_size = 10
    def hashable(value):
        try:
            hash(value)
            return True
        except TypeError:
            return False

    return st.one_of(
        n_tuples(values, max_size),
        st.lists(values, max_size=max_size),
        st.sets(values.filter(hashable), max_size=max_size),
        st.frozensets(values.filter(hashable), max_size=max_size),
        st.dictionaries(st.text(string.printable), values, max_size=max_size),
    )


def pickles():
    return st.recursive(flat_pickles(), pickles_container, max_leaves=10)


@st.composite
def secret_bytes(draw):
    size = draw(st.sampled_from(SECRET_SIZES))
    return draw(st.binary(min_size=size, max_size=size))


def configurable_names(shared):
    names = []
    if shared['enable_configcookie']:
        names.append('cookie_max_age')
        names.append('cookie_path')
        names.append('cookie_domain')
        names.append('cookie_secure')
        names.append('cookie_httponly')
    if shared['config_renewal']:
        names.append('renewal_timeout')
        names.append('renewal_try_every')
    if shared['config_idle']:
        names.append('idle_timeout')
        names.append('extension_delay')
        names.append('extension_chance')
        names.append('extension_deadline')
    if shared['config_absolute']:
        names.append('absolute_timeout')
    return names


@st.composite
def enabled_runtime_settings_names(draw):
    shared = draw(shared_config())
    names = configurable_names(shared)
    if names:
        mixed = draw(st.permutations(names))
        cutoff = draw(st.integers(min_value=1, max_value=len(mixed)))
        return mixed[:cutoff]
    else:
        return []


@st.composite
def non_configurable_names(draw):
    shared = draw(shared_config())
    names = configurable_names(shared)
    return [n for n in RUNTIME_SETTINGS if n not in names]
