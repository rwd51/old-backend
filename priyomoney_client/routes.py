import sys
from enum import Enum

from django.conf import settings

from priyomoney_client.request_config import request_config


class SlaveDBMode(Enum):
    ALWAYS = 'always'
    NEVER = 'never'
    ONLY_GET = 'only_get'


class CustomRouter(object):
    """A router that sets up a simple master/slave configuration"""
    """And also allows to enable/disable slave db"""

    @classmethod
    def is_slave_allowed(cls):
        if request_config.is_slave_allowed is not None:
            return request_config.is_slave_allowed
        return settings.ENABLE_SLAVE_DB == SlaveDBMode.ALWAYS.value

    def db_for_read(self, model, **hints):
        """Point all read operations to slave, if _slave_allowed is True and not migrate"""
        if 'pytest' in sys.modules or 'migrate' in sys.argv or not self.is_slave_allowed():
            return 'default'
        return 'priyo_pay_slave'

    def db_for_write(self, model, **hints):
        """Point all write operations to the primary/default"""
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """Allow any relation between two objects in the db pool"""
        # db_list = ('default', 'priyo_pay_slave',)
        # if obj1._state.db in db_list and obj2._state.db in db_list:
        #     return True
        return True

    def allow_syncdb(self, db, model):
        if db == 'default':
            return True
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == 'default'
