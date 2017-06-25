from setuptools import setup

requires = [
    'pyramid',
    'pyramid_tm',
    'SQLAlchemy',
    'transaction',
    'zope.sqlalchemy',
    'pycryptodomex',
]

tests_extras = [
    'pytest',
    'pytest-cov',
    'hypothesis',
]

docs_extras = [
    'Sphinx >= 1.3.5',
    'docutils',
    'repoze.sphinx.autointerface',
]

setup(
    name='pyramid_sqlalchemy_sessions',
    version='0.1',
    description='Provides session implementation for Pyramid framework based'
                'on SQLAlchemy storage backend',
    url='http://github.com/corehack/pyramid_sqlalchemy_sessions',
    author='Andrey Tretyakov',
    author_email='***REMOVED***',
    license='MIT',
    packages=['pyramid_sqlalchemy_sessions'],
    zip_safe=False,
    extras_require={
        'testing': tests_extras,
        'docs': docs_extras,
    },
    install_requires=requires,
    entry_points = """\
      [console_scripts]
      pyramid_session_gc = pyramid_sqlalchemy_sessions.gc:main
      """,
    )