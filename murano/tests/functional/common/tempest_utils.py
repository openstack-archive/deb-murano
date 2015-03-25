# Copyright (c) 2015 OpenStack Foundation
#
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

import congressclient.v1.client as cclient
import keystoneclient
from keystoneclient.v2_0 import client as ksclient
from tempest import config

import murano.tests.functional.common.utils as common_utils

CONF = config.CONF


class TempestDeployTestMixin(common_utils.DeployTestMixin):
    """Overrides methods to use tempest configuration."""

    @staticmethod
    @common_utils.memoize
    def keystone_client():
        return ksclient.Client(username=CONF.identity.admin_username,
                               password=CONF.identity.admin_password,
                               tenant_name=CONF.identity.admin_tenant_name,
                               auth_url=CONF.identity.uri)

    @staticmethod
    @common_utils.memoize
    def congress_client():
        auth = keystoneclient.auth.identity.v2.Password(
            auth_url=CONF.identity.uri,
            username=CONF.identity.admin_username,
            password=CONF.identity.admin_password,
            tenant_name=CONF.identity.admin_tenant_name)
        session = keystoneclient.session.Session(auth=auth)
        return cclient.Client(session=session,
                              service_type='policy')
