# Copyright (c) 2015 Mirantis, Inc.
# All Rights Reserved.
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

import unittest

from tempest import test
from tempest_lib import exceptions

from murano_tempest_tests.tests.api.service_broker import base
from murano_tempest_tests import utils


class ServiceBrokerNegativeTest(base.BaseServiceBrokerAdminTest):

    # NOTE(freerunner): Tempest will fail with this test, because its
    # _parse_resp function trying to parse a nullable JSON.
    # https://review.openstack.org/#/c/260659/
    # XFail until this one merged and tempest-lib released.
    @unittest.expectedFailure
    @test.attr(type=['gate', 'negative'])
    def test_get_status_with_not_present_instance_id(self):
        not_present_instance_id = utils.generate_uuid()
        self.assertRaises(
            exceptions.Gone,
            self.service_broker_client.get_last_status,
            not_present_instance_id)
