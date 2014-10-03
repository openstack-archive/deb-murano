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


class InternalFlowException(Exception):
    pass


class ReturnException(InternalFlowException):
    def __init__(self, value):
        self._value = value

    @property
    def value(self):
        return self._value


class BreakException(InternalFlowException):
    pass


class ContinueException(InternalFlowException):
    pass


class DslInvalidOperationError(Exception):
    pass


class NoMethodFound(Exception):
    def __init__(self, name):
        super(NoMethodFound, self).__init__('Method %s is not found' % name)


class NoClassFound(Exception):
    def __init__(self, name):
        super(NoClassFound, self).__init__('Class %s is not found' % name)


class NoPackageFound(Exception):
    def __init__(self, name):
        super(NoPackageFound, self).__init__('Package %s is not found' % name)


class NoPackageForClassFound(Exception):
    def __init__(self, name):
        super(NoPackageForClassFound, self).__init__('Package for class %s '
                                                     'is not found' % name)


class NoObjectFoundError(Exception):
    def __init__(self, object_id):
        super(NoObjectFoundError, self).__init__(
            'Object %s is not found in object store' % object_id)


class AmbiguousMethodName(Exception):
    def __init__(self, name):
        super(AmbiguousMethodName, self).__init__(
            'Found more that one method %s' % name)


class DslContractSyntaxError(Exception):
    pass


class ContractViolationException(Exception):
    pass


class ValueIsMissingError(Exception):
    pass


class DslSyntaxError(Exception):
    pass


class PropertyAccessError(Exception):
    pass


class AmbiguousPropertyNameError(PropertyAccessError):
    def __init__(self, name):
        super(AmbiguousPropertyNameError, self).__init__(
            'Found more that one property %s' % name)


class NoWriteAccess(PropertyAccessError):
    def __init__(self, name):
        super(NoWriteAccess, self).__init__(
            'Property %s is immutable to the caller' % name)


class NoWriteAccessError(PropertyAccessError):
    def __init__(self, name):
        super(NoWriteAccessError, self).__init__(
            'Property %s is immutable to the caller' % name)


class PropertyReadError(PropertyAccessError):
    def __init__(self, name, murano_class):
        super(PropertyAccessError, self).__init__(
            'Property %s in class %s cannot be read' %
            (name, murano_class.name))


class PropertyWriteError(PropertyAccessError):
    def __init__(self, name, murano_class):
        super(PropertyAccessError, self).__init__(
            'Property %s in class %s cannot be written' %
            (name, murano_class.name))


class UninitializedPropertyAccessError(PropertyAccessError):
    def __init__(self, name, murano_class):
        super(PropertyAccessError, self).__init__(
            'Access to uninitialized property '
            '%s in class %s is forbidden' % (name, murano_class.name))
