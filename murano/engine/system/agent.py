# Copyright (c) 2013 Mirantis Inc.
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
import datetime
import logging
import os
import types
import urlparse
import uuid

import eventlet.event

import murano.common.config as config
import murano.common.exceptions as exceptions
import murano.common.messaging as messaging
import murano.dsl.murano_class as murano_class
import murano.dsl.murano_object as murano_object
import murano.dsl.yaql_expression as yaql_expression
import murano.engine.system.common as common

LOG = logging.getLogger(__name__)


class AgentException(Exception):
    pass


@murano_class.classname('io.murano.system.Agent')
class Agent(murano_object.MuranoObject):
    def initialize(self, _context, host):
        self._enabled = False
        if config.CONF.engine.disable_murano_agent:
            LOG.debug('Use of murano-agent is disallowed '
                      'by the server configuration')
            return

        self._environment = self._get_environment(_context)
        self._enabled = True
        self._queue = str('e%s-h%s' % (
            self._environment.object_id, host.object_id)).lower()

    def _get_environment(self, _context):
        return yaql_expression.YaqlExpression(
            "$host.find('io.murano.Environment').require()"
        ).evaluate(_context)

    @property
    def enabled(self):
        return self._enabled

    def prepare(self):
        # (sjmc7) - turn this into a no-op if agents are disabled
        if config.CONF.engine.disable_murano_agent:
            LOG.debug('Use of murano-agent is disallowed '
                      'by the server configuration')
            return

        with common.create_rmq_client() as client:
            client.declare(self._queue, enable_ha=True, ttl=86400000)

    def queueName(self):
        return self._queue

    def _check_enabled(self):
        if config.CONF.engine.disable_murano_agent:
            raise exceptions.PolicyViolationException(
                'Use of murano-agent is disallowed '
                'by the server configuration')

    def _prepare_message(self, template, msg_id):
        msg = messaging.Message()
        msg.body = template
        msg.id = msg_id
        return msg

    def _send(self, template, wait_results, timeout, _context):
        """Send a message over the MQ interface."""
        msg_id = template.get('ID', uuid.uuid4().hex)
        if wait_results:
            event = eventlet.event.Event()
            listener = self._environment.agentListener
            listener.subscribe(msg_id, event, _context)

        msg = self._prepare_message(template, msg_id)
        with common.create_rmq_client() as client:
            client.send(message=msg, key=self._queue)

        if wait_results:
            try:
                with eventlet.Timeout(timeout):
                    result = event.wait()

            except eventlet.Timeout:
                listener.unsubscribe(msg_id)
                raise exceptions.TimeoutException(
                    'The Agent does not respond'
                    'within {0} seconds'.format(timeout))

            if not result:
                return None

            if result.get('FormatVersion', '1.0.0').startswith('1.'):
                return self._process_v1_result(result)

            else:
                return self._process_v2_result(result)

        else:
            return None

    def call(self, template, resources, _context, timeout=600):
        self._check_enabled()
        plan = self.buildExecutionPlan(template, resources)
        return self._send(plan, True, timeout, _context)

    def send(self, template, resources, _context):
        self._check_enabled()
        plan = self.buildExecutionPlan(template, resources)
        return self._send(plan, False, 0, _context)

    def callRaw(self, plan, _context, timeout=600):
        self._check_enabled()
        return self._send(plan, True, timeout, _context)

    def sendRaw(self, plan, _context):
        self._check_enabled()
        return self._send(plan, False, 0, _context)

    def isReady(self, _context, timeout=100):
        try:
            self.waitReady(_context, timeout)
        except exceptions.TimeoutException:
            return False
        else:
            return True

    def waitReady(self, _context, timeout=100):
        self._check_enabled()
        template = {'Body': 'return', 'FormatVersion': '2.0.0', 'Scripts': {}}
        self.call(template, False, _context, timeout)

    def _process_v1_result(self, result):
        if result['IsException']:
            raise AgentException(dict(self._get_exception_info(
                result.get('Result', [])), source='execution_plan'))
        else:
            results = result.get('Result', [])
            if not result:
                return None
            value = results[-1]
            if value['IsException']:
                raise AgentException(dict(self._get_exception_info(
                    value.get('Result', [])), source='command'))
            else:
                return value.get('Result')

    def _process_v2_result(self, result):
        error_code = result.get('ErrorCode', 0)
        if not error_code:
            return result.get('Body')
        else:
            body = result.get('Body') or {}
            err = {
                'message': body.get('Message'),
                'details': body.get('AdditionalInfo'),
                'errorCode': error_code,
                'time': result.get('Time')
            }
            for attr in ('Message', 'AdditionalInfo'):
                if attr in body:
                    del body[attr]
            err['extra'] = body if body else None
            raise AgentException(err)

    def _get_array_item(self, array, index):
        return array[index] if len(array) > index else None

    def _get_exception_info(self, data):
        data = data or []
        return {
            'type': self._get_array_item(data, 0),
            'message': self._get_array_item(data, 1),
            'command': self._get_array_item(data, 2),
            'details': self._get_array_item(data, 3),
            'timestamp': datetime.datetime.now().isoformat()
        }

    def buildExecutionPlan(self, template, resources):
        template = copy.deepcopy(template)
        if not isinstance(template, types.DictionaryType):
            raise ValueError('Incorrect execution plan ')
        format_version = template.get('FormatVersion')
        if not format_version or format_version.startswith('1.'):
            return self._build_v1_execution_plan(template, resources)
        else:
            return self._build_v2_execution_plan(template, resources)

    def _build_v1_execution_plan(self, template, resources):
        scripts_folder = 'scripts'
        script_files = template.get('Scripts', [])
        scripts = []
        for script in script_files:
            script_path = os.path.join(scripts_folder, script)
            scripts.append(resources.string(
                script_path).encode('base64'))
        template['Scripts'] = scripts
        return template

    def _build_v2_execution_plan(self, template, resources):
        scripts_folder = 'scripts'
        plan_id = uuid.uuid4().hex
        template['ID'] = plan_id
        if 'Action' not in template:
            template['Action'] = 'Execute'
        if 'Files' not in template:
            template['Files'] = {}

        files = {}
        for file_id, file_descr in template['Files'].items():
            files[file_descr['Name']] = file_id

        for name, script in template.get('Scripts', {}).items():
            if 'EntryPoint' not in script:
                raise ValueError('No entry point in script ' + name)

            if 'Application' in script['Type']:
                script['EntryPoint'] = self._place_file(
                    scripts_folder, script['EntryPoint'],
                    template, files, resources)
            scripts_files = script.get('Files', [])
            script['Files'] = []
            for file in scripts_files:
                file_id = self._place_file(scripts_folder, file,
                                           template, files, resources)
                if self._is_url(file):
                    script['Files'].append(file)
                else:
                    script['Files'].append(file_id)
        return template

    def _is_url(self, file):
        file = self._get_url(file)
        parts = urlparse.urlsplit(file)
        if not parts.scheme or not parts.netloc:
            return False
        else:
            return True

    def _get_url(self, file):
        if isinstance(file, dict):
            return file.values()[0]
        else:
            return file

    def _get_name(self, file):
        if isinstance(file, dict):
            name = file.keys()[0]
        else:
            name = file

        if self._is_url(name):
            name = name[name.rindex('/') + 1:len(name)]
        elif name.startswith('<') and name.endswith('>'):
            name = name[1: -1]
        return name

    def _get_file(self, file):
        if isinstance(file, dict):
            return file.values()[0]
        else:
            return file

    def _place_file(self, folder, file, template, files, resources):
        name = self._get_name(file)
        location = self._get_file(file)
        file_id = uuid.uuid4().hex

        if self._is_url(location):
            key = '='.join((name, location))
            if key in files:
                return files[key]

            template['Files'][file_id] = {
                'Name': name,
                'URL': location,
                'Type': 'Downloadable'
            }
            files[key] = file_id
        else:
            if name in files:
                return files[name]

            use_base64 = False
            if location.startswith('<') and location.endswith('>'):
                use_base64 = True
                location = location[1: -1]

            body_type = 'Base64' if use_base64 else 'Text'
            body = resources.string(os.path.join(folder, location))
            if use_base64:
                body = body.encode('base64')

            template['Files'][file_id] = {
                'Name': name,
                'BodyType': body_type,
                'Body': body
            }
            files[name] = file_id
        return file_id
