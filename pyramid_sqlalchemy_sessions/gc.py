import argparse
import logging
import sys

from pyramid.paster import (
    bootstrap,
    setup_logging
)
from pyramid.util import DottedNameResolver
from sqlalchemy.sql import or_

from .config import (
    factory_args_from_settings,
    _process_factory_args,
)
from .util import int_now


def main(argv=sys.argv):
    command = GCCommand(argv)
    return command.run()


class GCCommand():
    description = "Clean session table by removing expired session rows."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('config_uri', nargs='?', default=None)

    def __init__(self, argv, prefix='session.'):
        self.args = self.parser.parse_args(argv[1:])
        self.prefix = prefix

    @staticmethod
    def parse_config(config_uri, prefix):
        with bootstrap(config_uri) as env:
            settings = _process_factory_args(factory_args_from_settings(
                env['registry'].settings,
                DottedNameResolver().maybe_resolve,
                prefix,
            ))
            dbsession = getattr(env['request'], settings['dbsession_name'])
            return {
                'dbsession': dbsession,
                'settings': settings,
                'tm': env['request'].tm
            }

    def run(self):
        if not self.args.config_uri:
            print("Error: the following arguments are required: config_uri")
            return 2
        config_uri = self.args.config_uri
        setup_logging(config_uri)
        config = self.parse_config(config_uri, self.prefix)
        Cleaner(**config).clean()
        return 0


class Cleaner():
    logger = logging.getLogger(__name__)

    def __init__(self, dbsession, settings, tm):
        self.dbsession = dbsession
        self.settings = settings
        self.tm = tm

    def clean(self):
        with self.tm as txn:
            txn.addAfterCommitHook(self.log_result)
            self.delete_query(self.dbsession, self.settings)

    def log_result(self, status):
        if status:
            self.logger.info('Sessions table has been cleaned successfully.')
        else:
            self.logger.warning(
                'Could not clean session table: transaction commit failed.'
            )

    @staticmethod
    def delete_query(dbsession, settings):
        cls = settings['model_class']
        filter_parts = []
        if settings['idle_timeout']:
            filter_parts.append(cls.idle_expire < int_now())
        if settings['absolute_timeout']:
            filter_parts.append(cls.absolute_expire < int_now())
        if filter_parts:
            dbsession.query(cls).filter(or_(*filter_parts)).delete()
            return True
        else:
            return False
