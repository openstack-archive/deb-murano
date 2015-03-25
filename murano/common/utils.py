#    Copyright (c) 2013 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import collections
import functools as func
import types

import eventlet
import jsonschema

from murano.common.i18n import _, _LI
from murano.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class TraverseHelper(object):
    value_type = (types.StringTypes, types.IntType, types.FloatType,
                  types.BooleanType)

    @staticmethod
    def get(path, source):
        """Provides the ability to traverse a data source made up of any
        combination of lists and dicts. Has simple rules for selecting item of
        the list:

        * each item should have id property
        * to select item from the list, specify id value

        Examples:
            source = {'obj': {'attr': True}}
            value = TraverseHelper.get('/obj/attr', source)

            source = {'obj': [
                {'id': '1', 'value': 1},
                {'id': '2s', 'value': 2},
            ]}
            value = TraverseHelper.get('/obj/2s/value', source)


        :param path: string with path to desired value
        :param source: python object (list or dict)
        :return: object
        :raise: ValueError if object is malformed
        """
        queue = collections.deque(filter(lambda x: x, path.split('/')))

        while len(queue):
            path = queue.popleft()

            if isinstance(source, types.ListType):
                idx_source = source
                iterator = (
                    i for i in source
                    if i.get('?', {}).get('id') == path
                )
                source = next(iterator, None)
                if source is None and path.isdigit():
                    source = idx_source[int(path)]
            elif isinstance(source, types.DictionaryType):
                source = source[path]
            elif isinstance(source, TraverseHelper.value_type):
                break
            else:
                raise ValueError(_('Source object or path is malformed'))

        return source

    @staticmethod
    def update(path, value, source):
        """Updates value selected with specified path.

        Warning: Root object could not be updated

        :param path: string with path to desired value
        :param value: value
        :param source: python object (list or dict)
        """
        parent_path = '/'.join(path.split('/')[:-1])
        node = TraverseHelper.get(parent_path, source)
        key = path[1:].split('/')[-1]
        node[key] = value

    @staticmethod
    def insert(path, value, source):
        """Inserts new item to selected list.

        :param path: string with path to desired value
        :param value: value
        :param source: List
        """
        node = TraverseHelper.get(path, source)
        node.append(value)

    @staticmethod
    def extend(path, value, source):
        """Extend list by appending elements from the iterable.

        :param path: string with path to desired value
        :param value: value
        :param source: List
        """
        node = TraverseHelper.get(path, source)
        node.extend(value)

    @staticmethod
    def remove(path, source):
        """Removes selected item from source.

        :param path: string with path to desired value
        :param source: python object (list or dict)
        """
        parent_path = '/'.join(path.split('/')[:-1])
        node = TraverseHelper.get(parent_path, source)
        key = path[1:].split('/')[-1]

        if isinstance(node, types.ListType):
            iterator = (i for i in node if i.get('?', {}).get('id') == key)
            item = next(iterator, None)
            if item is None and key.isdigit():
                del node[int(key)]
            else:
                node.remove(item)
        elif isinstance(node, types.DictionaryType):
            del node[key]
        else:
            raise ValueError(_('Source object or path is malformed'))


def is_different(obj1, obj2):
    """Stripped-down version of deep.diff comparator

    Compares arbitrary nested objects, handles circular links, but doesn't
    point to the first difference as deep.diff does.
    """
    class Difference(Exception):
        pass

    def is_in(o, st):
        for _o in st:
            if o is _o:
                return True
        return False

    def rec(o1, o2, stack1=(), stack2=()):
        if is_in(o1, stack1) and is_in(o2, stack2):
            # circular reference detected - break the loop
            return
        elif is_in(o1, stack1):
            raise Difference()
        else:
            stack1 += (o1,)
            stack2 += (o2,)

        if o1 is o2:
            return
        elif (isinstance(o1, basestring)
              and isinstance(o2, basestring)) and o1 == o2:
            return
        elif type(o1) != type(o2):
            raise Difference()
        elif isinstance(o1, dict):
            # check for keys inequality
            rec(o1.keys(), o2.keys(), stack1, stack2)
            for key in o1.keys():
                rec(o1[key], o2[key], stack1, stack2)
        elif isinstance(o1, (list, tuple, set)):
            if len(o1) != len(o2):
                raise Difference()
            else:
                for _o1, _o2 in zip(o1, o2):
                    rec(_o1, _o2, stack1, stack2)
        elif hasattr(o1, '__dict__'):
            return rec(o1.__dict__, o2.__dict__, stack1, stack2)
        elif o1 != o2:
            raise Difference()

    try:
        rec(obj1, obj2)
    except Difference:
        return True
    else:
        return False


def build_entity_map(value):
    def build_entity_map_recursive(value, id_map):
        if isinstance(value, types.DictionaryType):
            if '?' in value and 'id' in value['?']:
                id_map[value['?']['id']] = value
            for k, v in value.iteritems():
                build_entity_map_recursive(v, id_map)
        if isinstance(value, types.ListType):
            for item in value:
                build_entity_map_recursive(item, id_map)

    id_map = {}
    build_entity_map_recursive(value, id_map)
    return id_map


def retry(ExceptionToCheck, tries=4, delay=3, backoff=2):
    """Retry calling the decorated function using an exponential backoff.

    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    :param ExceptionToCheck: the exception to check. may be a tuple of
        exceptions to check
    :type ExceptionToCheck: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    """

    def deco_retry(f):
        @func.wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            forever = mtries == -1
            while forever or mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck as e:

                    LOG.exception(e)
                    LOG.info(_LI("Retrying in {0} seconds...").format(mdelay))

                    eventlet.sleep(mdelay)

                    if not forever:
                        mtries -= 1

                    if mdelay < 60:
                        mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry

    return deco_retry


def handle(f):
    """Handles exception in wrapped function and writes to LOG."""

    @func.wraps(f)
    def f_handle(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            LOG.exception(e)

    return f_handle


def validate_body(schema):
    def deco_validate_body(f):
        @func.wraps(f)
        def f_validate_body(*args, **kwargs):
            if 'body' in kwargs:
                jsonschema.validate(kwargs['body'], schema)
                return f(*args, **kwargs)
        return f_validate_body
    return deco_validate_body
