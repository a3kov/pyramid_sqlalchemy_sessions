from setuptools import setup

try:
    with open('README.rst') as f:
        README = f.read()
except IOError:
    README = ''

requires = [
    'pyramid < 2',
    'pyramid_tm',
    'SQLAlchemy',
    'zope.sqlalchemy',
    'pycryptodomex',
]

tests_require = [
    'pytest',
    'pytest-cov',
    'hypothesis',
]

docs_extras = [
    'Sphinx >= 1.3.5',
    'docutils',
    'repoze.sphinx.autointerface',
]

tests_extras = tests_require

setup(
    name='pyramid_sqlalchemy_sessions',
    version='0.1',
    description='Provides session implementation for Pyramid framework based'
                'on SQLAlchemy storage backend',
    long_description=README,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Framework :: Pyramid',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP :: Session',
    ],
    keywords='pyramid session sqlalchemy',
    url='http://github.com/corehack/pyramid_sqlalchemy_sessions',
    author='Andrey Tretyakov',
    author_email='corehack@users.noreply.github.com',
    license='MIT',
    packages=['pyramid_sqlalchemy_sessions'],
    zip_safe=False,
    python_requires='>=3.5.*',
    install_requires=requires,
    extras_require={
        'testing': tests_extras,
        'docs': docs_extras,
    },
    tests_require=tests_require,
    test_suite="pyramid_sqlalchemy_sessions.tests",
    entry_points = """\
      [console_scripts]
      pyramid_session_gc = pyramid_sqlalchemy_sessions.gc:main
      """,
    )
