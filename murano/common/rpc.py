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

import oslo_messaging as messaging
from oslo_messaging import rpc
from oslo_messaging import target

from murano.common import config

TRANSPORT = None


class ApiClient(object):
    def __init__(self, transport):
        client_target = target.Target('murano', 'results')
        self._client = rpc.RPCClient(transport, client_target, timeout=15)

    def process_result(self, result, environment_id):
        return self._client.call({}, 'process_result', result=result,
                                 environment_id=environment_id)


class EngineClient(object):
    def __init__(self, transport):
        client_target = target.Target('murano', 'tasks')
        self._client = rpc.RPCClient(transport, client_target, timeout=15)

    def handle_task(self, task):
        return self._client.cast({}, 'handle_task', task=task)


def api():
    global TRANSPORT
    if TRANSPORT is None:
        TRANSPORT = messaging.get_transport(config.CONF)

    return ApiClient(TRANSPORT)


def engine():
    global TRANSPORT
    if TRANSPORT is None:
        TRANSPORT = messaging.get_transport(config.CONF)

    return EngineClient(TRANSPORT)
