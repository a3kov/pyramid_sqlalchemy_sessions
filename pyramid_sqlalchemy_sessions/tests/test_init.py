from pyramid.interfaces import ISessionFactory

from .. import includeme


def test_includeme(minimal_context):
    config = minimal_context.config
    includeme(config)
    factory = config.registry.queryUtility(ISessionFactory)
    assert factory._model_class == minimal_context.settings['model_class']
