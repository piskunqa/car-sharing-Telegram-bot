import logging
import math
import time
from abc import ABC
from datetime import date, datetime

from peewee import OperationalError, MySQLDatabase, SENTINEL
from telebot import types


class ReconnectMixin(object):
    reconnect_errors = (
        (OperationalError, '2006'),
        (OperationalError, '2013'),
        (OperationalError, '2003'),
        (OperationalError, '2014'),
        (OperationalError, 'MySQL Connection not available.'),
    )

    def __init__(self, *args, **kwargs):
        super(ReconnectMixin, self).__init__(*args, **kwargs)

        self._reconnect_errors = {}
        for exc_class, err_fragment in self.reconnect_errors:
            self._reconnect_errors.setdefault(exc_class, [])
            self._reconnect_errors[exc_class].append(err_fragment.lower())

    def execute_sql(self, sql, params=None, commit=SENTINEL, tr=0):
        try:
            return super(ReconnectMixin, self).execute_sql(sql, params, commit)
        except Exception as exc:
            exc_class = type(exc)
            if exc_class not in self._reconnect_errors:
                raise exc

            exc_repr = str(exc).lower()
            for err_fragment in self._reconnect_errors[exc_class]:
                if err_fragment in exc_repr:
                    break
            else:
                raise exc

            if not self.is_closed():
                self.close()
            try:
                self.connect()
            except Exception as e:
                logging.error("CONNECTION ERROR: %s", str(e))

            if tr >= 20:
                raise exc
            time.sleep(tr / 10)
            return self.execute_sql(sql, params, commit, tr=tr + 1)


class MySQLDatabaseReconnected(ReconnectMixin, MySQLDatabase, ABC): ...


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def get_handler_for_command(bot, command: str):
    """
    Returns the function that handles the given command.
    Example: handler = get_handler_for_command(bot, "start")
    """
    for h in bot.message_handlers:
        filters = h.get("filters", {})
        cmd_list = filters.get("commands")
        if cmd_list and command in cmd_list:
            return h["function"]

    return None
