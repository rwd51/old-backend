from contextlib import contextmanager, ContextDecorator
from django.db import transaction
from priyomoney_client.request_config import request_config


class slave_db_manager(ContextDecorator):
    """
        Context Manager for enabling/disabling slave db
        Usage:
            as context manager: with slave_db_manager(allow_slave_db=True) or with slave_db_manager(allow_slave_db=False)
            as decorator: @slave_db_manager(allow_slave_db=True) or @slave_db_manager(allow_slave_db=False)
    """
    def __init__(self, allow_slave_db: bool):
        self.value = allow_slave_db

    def __enter__(self):
        self.old_value = request_config.is_slave_allowed
        request_config.is_slave_allowed = self.value

    def __exit__(self, exc_type, exc_val, exc_tb):
        request_config.is_slave_allowed = self.old_value


@contextmanager
def db_dry_run():
    """
        Context Manager for enabling dry run (no db operation will be committed)
        Usage:
            as context manager: with db_dry_run()
            as decorator: @db_dry_run()

    """
    with transaction.atomic():
        yield
        transaction.set_rollback(True)


