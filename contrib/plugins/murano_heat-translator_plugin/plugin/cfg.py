# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_config import cfg


def init_config(conf):
    opts = [
        cfg.IntOpt('api_version', default=2),
        cfg.StrOpt('endpoint_type', default='publicURL')
    ]
    conf.register_opts(opts, group="heat_translator")
    return conf.heat_translator
