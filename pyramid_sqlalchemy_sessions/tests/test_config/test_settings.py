import pytest

from hypothesis import (
    given,
    assume,
)
import hypothesis.strategies as st

from ...config import RUNTIME_SETTINGS
from ...exceptions import SettingsError
from ..contexts import (
    new_context,
    new_request,
)
from ..strategies import (
    valid_settings,
    shared_config,
    enabled_runtime_settings_names,
    non_configurable_names,
)


@given(
    settings=valid_settings(),
    names=enabled_runtime_settings_names(),
    new_settings=valid_settings(),
    use_mapping=st.tuples(st.booleans(), st.booleans()),
    invalid_names=non_configurable_names(),
    shared=shared_config(),
)
def test_integrated_settings(
    settings,
    names,
    new_settings,
    use_mapping,
    invalid_names,
    shared,
):
    assume(names)
    for name in names:
        assume(settings[name] != new_settings[name])

    def set_names(names, new_settings, request):
        settings = request.session.settings
        for name in names:
            if use_mapping[0]:
                settings[name] = new_settings[name]
            else:
                setattr(settings, name, new_settings[name])

    def check_names(names, new_settings, request, equals=True):
        settings = request.session.settings
        for name in names:
            if use_mapping[1]:
                condition = settings[name] == new_settings[name]
            else:
                condition = getattr(settings, name) == new_settings[name]
            assert condition if equals else not condition

    # Test not editable raises SettingsError.
    with new_context(settings) as context:
        with new_request(context) as request:
            with pytest.raises(SettingsError):
                set_names(names, new_settings, request)
    # Test not new raises SettingsError.
    with new_context(settings) as context:
        with new_request(context) as request:
            request.session['test'] = 1
        with new_request(context) as request:
            with pytest.raises(SettingsError):
                with request.session.settings:
                    pass
            with pytest.raises(SettingsError):
                request.session.settings.edit()
            # Test invalidation makes writable.
            request.session.invalidate()
            with request.session.settings:
                set_names(names, new_settings, request)
    # Test not runtime-configurable raises SettingsError.
    with new_context(settings) as context:
        with new_request(context) as request:
            with request.session.settings as s:
                for name in invalid_names:
                    with pytest.raises(SettingsError):
                        s[name] = new_settings[name]
    # Test cm mode works.
    with new_context(settings) as context:
        with new_request(context) as request:
            request.session['test'] = 1
            with request.session.settings:
                set_names(names, new_settings, request)
        with new_request(context) as request:
            check_names(names, new_settings, request)
    # Edit-save mode works.
    with new_context(settings) as context:
        with new_request(context) as request:
            request.session['test'] = 1
            request.session.settings.edit()
            set_names(names, new_settings, request)
            request.session.settings.save()
        with new_request(context) as request:
            check_names(names, new_settings, request)
    # Test validation. We don't need variability of failures here.
    # Atm booleans are not validated.
    not_failing = ('cookie_secure', 'cookie_httponly')
    with new_context(settings) as context:
        with new_request(context) as request:
            for name in names:
                if name not in not_failing:
                    with pytest.raises(ValueError):
                        with request.session.settings:
                            set_names((name,), {name: -1}, request)
    # Test unsaved settings are not persisted in the db.
    with new_context(settings) as context:
        with new_request(context) as request:
            request.session['test'] = 1
            request.session.settings.edit()
            set_names(names, new_settings, request)
        with new_request(context) as request:
            check_names(names, new_settings, request, equals=False)
    # Test clean session changed settings are not persisted in the db.
    with new_context(settings) as context:
        with new_request(context) as request:
            with request.session.settings:
                set_names(names, new_settings, request)
        with new_request(context) as request:
            check_names(names, new_settings, request, equals=False)
    # Test invalidation resets dirty settings and editable state.
    with new_context(settings) as context:
        with new_request(context) as request:
            request.session.settings.edit()
            set_names(names, new_settings, request)
            request.session.invalidate()
            assert len(request.session.settings._dirty) == 0
            assert request.session.settings._locked
            check_names(names, new_settings, request, equals=False)
    # Test unsaved settings don't affect features.
    if settings['idle_timeout'] and shared['config_idle']:
        disabled_idle_settings = settings.copy()
        disabled_idle_settings['idle_timeout'] = None
        with new_context(disabled_idle_settings) as context:
            with new_request(context) as request:
                request.session['test'] = 1
                s = request.session.settings
                s.edit()
                s['idle_timeout'] = settings['idle_timeout']
            with new_request(context) as request:
                assert request.session.settings['idle_timeout'] == None
                assert request.session._session.idle_expire == None
