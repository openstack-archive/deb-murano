#    Copyright (c) 2014 Mirantis, Inc.
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
import sys
import weakref

import six
from yaql.language import specs

from murano.dsl import constants
from murano.dsl import dsl
from murano.dsl import dsl_types
from murano.dsl import exceptions
from murano.dsl import helpers
from murano.dsl import macros
from murano.dsl import meta
from murano.dsl import typespec
from murano.dsl import virtual_exceptions
from murano.dsl import yaql_integration


macros.register()
virtual_exceptions.register()


class MuranoMethod(dsl_types.MuranoMethod, meta.MetaProvider):
    def __init__(self, declaring_type, name, payload, original_name=None):
        self._name = name
        original_name = original_name or name
        self._declaring_type = weakref.ref(declaring_type)
        self._meta_values = None

        if callable(payload):
            if isinstance(payload, specs.FunctionDefinition):
                self._body = payload
            else:
                self._body = yaql_integration.get_function_definition(
                    payload, weakref.proxy(self), original_name)
            self._arguments_scheme = None
            if any((
                    helpers.inspect_is_static(
                        declaring_type.extension_class, original_name),
                    helpers.inspect_is_classmethod(
                        declaring_type.extension_class, original_name))):
                self._usage = self._body.meta.get(
                    constants.META_USAGE, dsl_types.MethodUsages.Static)
                if self._usage not in dsl_types.MethodUsages.StaticMethods:
                    raise ValueError(
                        'Invalid Usage for static method ' + self.name)
            else:
                self._usage = (self._body.meta.get(constants.META_USAGE) or
                               dsl_types.MethodUsages.Runtime)
                if self._usage not in dsl_types.MethodUsages.InstanceMethods:
                    raise ValueError(
                        'Invalid Usage for instance method ' + self.name)
            if (self._body.name.startswith('#') or
                    self._body.name.startswith('*')):
                raise ValueError(
                    'Import of special yaql functions is forbidden')
            self._meta = meta.MetaData(
                self._body.meta.get(constants.META_MPL_META),
                dsl_types.MetaTargets.Method,
                declaring_type)
        else:
            payload = payload or {}
            self._body = macros.MethodBlock(payload.get('Body'), name)
            self._usage = payload.get(
                'Usage') or dsl_types.MethodUsages.Runtime
            arguments_scheme = helpers.list_value(payload.get('Arguments'))
            if isinstance(arguments_scheme, dict):
                arguments_scheme = [{key: value} for key, value in
                                    six.iteritems(arguments_scheme)]
            self._arguments_scheme = collections.OrderedDict()
            for record in arguments_scheme:
                if (not isinstance(record, dict) or
                        len(record) > 1):
                    raise ValueError()
                name = list(record.keys())[0]
                self._arguments_scheme[name] = MuranoMethodArgument(
                    self, self.name, name, record[name])
            self._meta = meta.MetaData(
                payload.get('Meta'),
                dsl_types.MetaTargets.Method,
                declaring_type)

        self._instance_stub, self._static_stub = \
            yaql_integration.build_stub_function_definitions(
                weakref.proxy(self))

    @property
    def name(self):
        return self._name

    @property
    def declaring_type(self):
        return self._declaring_type()

    @property
    def arguments_scheme(self):
        return self._arguments_scheme

    @property
    def instance_stub(self):
        return self._instance_stub

    @property
    def static_stub(self):
        return self._static_stub

    @property
    def usage(self):
        return self._usage

    @usage.setter
    def usage(self, value):
        self._usage = value

    @property
    def body(self):
        return self._body

    @property
    def is_static(self):
        return self.usage in dsl_types.MethodUsages.StaticMethods

    def get_meta(self, context):
        def meta_producer(cls):
            method = cls.methods.get(self.name)
            if method is None:
                return None
            return method._meta

        if self._meta_values is None:
            executor = helpers.get_executor(context)
            context = executor.create_type_context(
                self.declaring_type, caller_context=context)
            self._meta_values = meta.merge_providers(
                self.declaring_type, meta_producer, context)
        return self._meta_values

    def __repr__(self):
        return 'MuranoMethod({0}::{1})'.format(
            self.declaring_type.name, self.name)

    def invoke(self, executor, this, args, kwargs, context=None,
               skip_stub=False):
        if isinstance(this, dsl.MuranoObjectInterface):
            this = this.object
        if this and not self.declaring_type.is_compatible(this):
            raise Exception("'this' must be of compatible type")
        if not this and not self.is_static:
            raise Exception("A class instance is required")

        if isinstance(this, dsl_types.MuranoObject):
            this = this.cast(self.declaring_type)
        else:
            this = self.declaring_type
        return executor.invoke_method(
            self, this, context, args, kwargs, skip_stub)


class MuranoMethodArgument(dsl_types.MuranoMethodArgument, typespec.Spec,
                           meta.MetaProvider):
    def __init__(self, murano_method, method_name, arg_name, declaration):
        super(MuranoMethodArgument, self).__init__(
            declaration, murano_method.declaring_type)
        self._method_name = method_name
        self._arg_name = arg_name
        self._murano_method = weakref.ref(murano_method)
        self._meta = meta.MetaData(
            declaration.get('Meta'),
            dsl_types.MetaTargets.Argument, self.murano_method.declaring_type)

    def transform(self, value, this, *args, **kwargs):
        try:
            if self.murano_method.usage == dsl_types.MethodUsages.Extension:
                this = self.murano_method.declaring_type
            return super(MuranoMethodArgument, self).transform(
                value, this, *args, **kwargs)
        except exceptions.ContractViolationException as e:
            msg = u'[{0}::{1}({2}{3})] {4}'.format(
                self.murano_method.declaring_type.name,
                self.murano_method.name, self.name,
                e.path, six.text_type(e))
            six.reraise(exceptions.ContractViolationException,
                        exceptions.ContractViolationException(msg),
                        sys.exc_info()[2])

    @property
    def murano_method(self):
        return self._murano_method()

    @property
    def name(self):
        return self._arg_name

    def get_meta(self, context):
        executor = helpers.get_executor(context)
        context = executor.create_type_context(
            self.murano_method.declaring_type, caller_context=context)

        return self._meta.get_meta(context)

    def __repr__(self):
        return 'MuranoMethodArgument({method}::{name})'.format(
            method=self.murano_method.name, name=self.name)
