# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy
import traceback
import uuid

import eventlet.debug
from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging as messaging
from oslo_messaging import target
from oslo_serialization import jsonutils

from murano.common import auth_utils
from murano.common.helpers import token_sanitizer
from murano.common import plugin_loader
from murano.common import rpc
from murano.dsl import context_manager
from murano.dsl import dsl_exception
from murano.dsl import executor as dsl_executor
from murano.dsl import linked_context
from murano.dsl import serializer
from murano.engine import environment
from murano.engine import package_loader
from murano.engine.system import status_reporter
from murano.engine.system import yaql_functions
from murano.common.i18n import _LI, _LE, _LW
from murano.policy import model_policy_enforcer as enforcer

CONF = cfg.CONF

RPC_SERVICE = None
PLUGIN_LOADER = None

LOG = logging.getLogger(__name__)

eventlet.debug.hub_exceptions(False)


def _prepare_rpc_service(server_id):
    endpoints = [TaskProcessingEndpoint()]

    transport = messaging.get_transport(CONF)
    s_target = target.Target('murano', 'tasks', server=server_id)
    return messaging.get_rpc_server(transport, s_target, endpoints, 'eventlet')


def get_rpc_service():
    global RPC_SERVICE

    if RPC_SERVICE is None:
        RPC_SERVICE = _prepare_rpc_service(str(uuid.uuid4()))
    return RPC_SERVICE


def get_plugin_loader():
    global PLUGIN_LOADER

    if PLUGIN_LOADER is None:
        PLUGIN_LOADER = plugin_loader.PluginLoader()
    return PLUGIN_LOADER


class ContextManager(context_manager.ContextManager):
    def create_root_context(self, runtime_version):
        root_context = super(ContextManager, self).create_root_context(
            runtime_version)
        return linked_context.link(
            root_context, yaql_functions.get_context(runtime_version))


class TaskProcessingEndpoint(object):
    @classmethod
    def handle_task(cls, context, task):
        result = cls.execute(task)
        rpc.api().process_result(result, task['id'])

    @staticmethod
    def execute(task):
        s_task = token_sanitizer.TokenSanitizer().sanitize(task)
        LOG.info(_LI('Starting processing task: {task_desc}').format(
            task_desc=jsonutils.dumps(s_task)))

        result = None
        reporter = status_reporter.StatusReporter(task['id'])

        try:
            task_executor = TaskExecutor(task, reporter)
            result = task_executor.execute()
            return result
        finally:
            LOG.info(_LI('Finished processing task: {task_desc}').format(
                task_desc=jsonutils.dumps(result)))


class TaskExecutor(object):
    @property
    def action(self):
        return self._action

    @property
    def environment(self):
        return self._environment

    @property
    def model(self):
        return self._model

    def __init__(self, task, reporter=None):
        if reporter is None:
            reporter = status_reporter.StatusReporter(task['id'])
        self._action = task.get('action')
        self._model = task['model']
        self._environment = environment.Environment()
        self._environment.token = task['token']
        self._environment.tenant_id = task['tenant_id']
        self._environment.system_attributes = self._model.get('SystemData', {})
        self._reporter = reporter

        self._model_policy_enforcer = enforcer.ModelPolicyEnforcer(
            self._environment)

    def execute(self):
        try:
            self._create_trust()
        except Exception as e:
            return self.exception_result(e, None, '<system>')

        murano_client_factory = \
            lambda: self._environment.clients.get_murano_client()
        with package_loader.CombinedPackageLoader(
                murano_client_factory,
                self._environment.tenant_id) as pkg_loader:
            result = self._execute(pkg_loader)
        self._model['SystemData'] = self._environment.system_attributes
        result['model'] = self._model

        if (not self._model.get('Objects') and
                not self._model.get('ObjectsCopy')):
            try:
                self._delete_trust()
            except Exception:
                LOG.warning(_LW('Cannot delete trust'), exc_info=True)

        return result

    def _execute(self, pkg_loader):
        get_plugin_loader().register_in_loader(pkg_loader)

        executor = dsl_executor.MuranoDslExecutor(
            pkg_loader, ContextManager(), self.environment)
        try:
            obj = executor.load(self.model)
        except Exception as e:
            return self.exception_result(e, None, '<load>')

        if obj is not None:
            try:
                self._validate_model(obj.object, pkg_loader)
            except Exception as e:
                return self.exception_result(e, obj, '<validate>')

        try:
            LOG.debug('Invoking pre-cleanup hooks')
            self.environment.start()
            executor.cleanup(self._model)
        except Exception as e:
            return self.exception_result(e, obj, '<GC>')
        finally:
            LOG.debug('Invoking post-cleanup hooks')
            self.environment.finish()
        self._model['ObjectsCopy'] = copy.deepcopy(self._model.get('Objects'))

        action_result = None
        if self.action:
            try:
                LOG.debug('Invoking pre-execution hooks')
                self.environment.start()
                try:
                    action_result = self._invoke(executor)
                finally:
                    try:
                        self._model = serializer.serialize_model(obj, executor)
                    except Exception as e:
                        return self.exception_result(e, None, '<model>')
            except Exception as e:
                return self.exception_result(e, obj, self.action['method'])
            finally:
                LOG.debug('Invoking post-execution hooks')
                self.environment.finish()

        try:
            action_result = serializer.serialize(action_result)
        except Exception as e:
            return self.exception_result(e, None, '<result>')

        return {
            'action': {
                'result': action_result,
                'isException': False
            }
        }

    def exception_result(self, exception, root, method_name):
        if isinstance(exception, dsl_exception.MuranoPlException):
            LOG.error('\n' + exception.format(prefix='  '))
            exception_traceback = exception.format()
        else:
            exception_traceback = traceback.format_exc()
            LOG.exception(
                _LE("Exception %(exc)s occurred"
                    " during invocation of %(method)s"),
                {'exc': exception, 'method': method_name})
        self._reporter.report_error(root, str(exception))

        return {
            'action': {
                'isException': True,
                'result': {
                    'message': str(exception),
                    'details': exception_traceback
                }
            }
        }

    def _validate_model(self, obj, pkg_loader):
        if CONF.engine.enable_model_policy_enforcer:
            if obj is not None:
                self._model_policy_enforcer.modify(obj, pkg_loader)
                self._model_policy_enforcer.validate(obj.to_dictionary(),
                                                     pkg_loader)

    def _invoke(self, mpl_executor):
        obj = mpl_executor.object_store.get(self.action['object_id'])
        method_name, kwargs = self.action['method'], self.action['args']

        if obj is not None:
            return obj.type.invoke(method_name, mpl_executor, obj, (), kwargs)

    def _create_trust(self):
        if not CONF.engine.use_trusts:
            return
        trust_id = self._environment.system_attributes.get('TrustId')
        if not trust_id:
            trust_id = auth_utils.create_trust(self._environment.token,
                                               self._environment.tenant_id)
            self._environment.system_attributes['TrustId'] = trust_id
        self._environment.trust_id = trust_id

    def _delete_trust(self):
        trust_id = self._environment.trust_id
        if trust_id:
            auth_utils.delete_trust(self._environment.trust_id)
            self._environment.system_attributes['TrustId'] = None
            self._environment.trust_id = None
