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

import fnmatch
import os.path

import six

from murano.dsl import murano_package
from murano.dsl import namespace_resolver
from murano.dsl import package_loader
from murano.engine import yaql_yaml_loader
from murano.tests.unit.dsl.foundation import object_model


class TestPackage(murano_package.MuranoPackage):
    def __init__(self, pkg_loader, name, version,
                 runtime_version, requirements, configs):
        self.__configs = configs
        super(TestPackage, self).__init__(
            pkg_loader, name, version,
            runtime_version, requirements)

    def get_class_config(self, name):
        return self.__configs.get(name, {})

    def get_resource(self, name):
        pass


class TestPackageLoader(package_loader.MuranoPackageLoader):
    _classes_cache = {}

    def __init__(self, directory, package_name, parent_loader=None):
        self._package_name = package_name
        self._yaml_loader = yaql_yaml_loader.get_loader('1.0')
        if directory in TestPackageLoader._classes_cache:
            self._classes = TestPackageLoader._classes_cache[directory]
        else:
            self._classes = {}
            self._build_index(directory)
            TestPackageLoader._classes_cache[directory] = self._classes
        self._parent = parent_loader
        self._configs = {}
        self._package = TestPackage(
            self, package_name, None, '1.0', None, self._configs)
        for name, payload in six.iteritems(self._classes):
            self._package.register_class(payload, name)
        super(TestPackageLoader, self).__init__()

    def load_package(self, package_name, version_spec):
        if package_name == self._package_name:
            return self._package
        elif self._parent:
            return self._parent.load_package(package_name, version_spec)
        else:
            raise KeyError(package_name)

    def load_class_package(self, class_name, version_spec):
        if class_name in self._classes:
            return self._package
        elif self._parent:
            return self._parent.load_class_package(class_name, version_spec)
        else:
            raise KeyError(class_name)

    def _build_index(self, directory):
        yamls = [os.path.join(dirpath, f)
                 for dirpath, _, files in os.walk(directory)
                 for f in fnmatch.filter(files, '*.yaml')]
        for class_def_file in yamls:
            self._load_class(class_def_file)

    def _load_class(self, class_def_file):
        with open(class_def_file) as stream:
            data = self._yaml_loader(stream.read(), class_def_file)

        if 'Name' not in data:
            return

        for name, method in six.iteritems(data.get('Methods') or data.get(
                'Workflow') or {}):
            if name.startswith('test'):
                method['Usage'] = 'Action'

        ns = namespace_resolver.NamespaceResolver(data.get('Namespaces', {}))
        class_name = ns.resolve_name(data['Name'])
        self._classes[class_name] = data

    def set_config_value(self, class_name, property_name, value):
        if isinstance(class_name, object_model.Object):
            class_name = class_name.type_name
        self._configs.setdefault(class_name, {})[
            property_name] = value

    def register_package(self, package):
        super(TestPackageLoader, self).register_package(package)
