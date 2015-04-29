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

from murano.common.i18n import _LE
import murano.openstack.common.log as logging


LOG = logging.getLogger(__name__)


class Environment(object):
    def __init__(self):
        self.token = None
        self.tenant_id = None
        self.trust_id = None
        self.system_attributes = {}
        self.clients = None
        self._set_up_list = []
        self._tear_down_list = []

    def on_session_start(self, delegate):
        self._set_up_list.append(delegate)

    def on_session_finish(self, delegate):
        self._tear_down_list.append(delegate)

    def start(self):
        for delegate in self._set_up_list:
            try:
                delegate()
            except Exception:
                LOG.exception(_LE('Unhandled exception on invocation of '
                                  'pre-execution hook'))
        self._set_up_list = []

    def finish(self):
        for delegate in self._tear_down_list:
            try:
                delegate()
            except Exception:
                LOG.exception(_LE('Unhandled exception on invocation of '
                                  'post-execution hook'))
        self._tear_down_list = []
