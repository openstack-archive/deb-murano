# coding: utf-8
# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
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

import json

from oslo_config import cfg
from oslo_utils import timeutils

from murano.api.v1 import environments
from murano.db import models
from murano.services import states
import murano.tests.unit.api.base as tb
import murano.tests.unit.utils as test_utils

CONF = cfg.CONF


class TestEnvironmentApi(tb.ControllerTest, tb.MuranoApiTestCase):
    def setUp(self):
        super(TestEnvironmentApi, self).setUp()
        self.controller = environments.Controller()

    @staticmethod
    def _configure_opts():
        opts = [
            cfg.StrOpt('config_dir'),
            cfg.StrOpt('config_file', default='murano.conf'),
            cfg.StrOpt('project', default='murano'),
        ]
        CONF.register_opts(opts)

    def test_list_empty_environments(self):
        """Check that with no environments an empty list is returned."""
        self._set_policy_rules(
            {'list_environments': '@'}
        )
        self.expect_policy_check('list_environments')

        req = self._get('/environments')
        result = req.get_response(self.api)
        self.assertEqual({'environments': []}, json.loads(result.body))

    def test_list_all_tenants(self):
        """Check whether all_tenants param is taken into account."""

        self._configure_opts()
        self._set_policy_rules(
            {'list_environments': '@',
             'create_environment': '@',
             'list_environments_all_tenants': '@'}
        )
        self.expect_policy_check('create_environment')

        body = {'name': 'my_env'}
        req = self._post('/environments', json.dumps(body), tenant="other")
        req.get_response(self.api)

        self._check_listing(False, 'list_environments', 0)
        self._check_listing(True, 'list_environments_all_tenants', 1)

    def _check_listing(self, all_tenants, expected_check, expected_count):
        self.expect_policy_check(expected_check)
        req = self._get('/environments', {'all_tenants': all_tenants})
        response = req.get_response(self.api)
        body = json.loads(response.body)
        self.assertEqual(200, response.status_code)
        self.assertEqual(expected_count, len(body['environments']))

    def test_create_environment(self):
        """Create an environment, test environment.show()."""
        self._configure_opts()
        self._set_policy_rules(
            {'list_environments': '@',
             'create_environment': '@',
             'show_environment': '@'}
        )
        self.expect_policy_check('create_environment')

        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now

        uuids = ('env_object_id', 'network_id', 'environment_id')
        mock_uuid = self._stub_uuid(uuids)

        expected = {'tenant_id': self.tenant,
                    'id': 'environment_id',
                    'name': 'my_env',
                    'version': 0,
                    'created': timeutils.isotime(fake_now)[:-1],
                    'updated': timeutils.isotime(fake_now)[:-1],
                    }

        body = {'name': 'my_env'}
        req = self._post('/environments', json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(expected, json.loads(result.body))

        expected['status'] = 'ready'

        # Reset the policy expectation
        self.expect_policy_check('list_environments')

        req = self._get('/environments')
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)
        self.assertEqual({'environments': [expected]}, json.loads(result.body))

        expected['services'] = []
        expected['acquired_by'] = None

        # Reset the policy expectation
        self.expect_policy_check('show_environment',
                                 {'environment_id': uuids[-1]})

        req = self._get('/environments/%s' % uuids[-1])
        result = req.get_response(self.api)

        self.assertEqual(expected, json.loads(result.body))
        self.assertEqual(3, mock_uuid.call_count)

    def test_illegal_environment_name_create(self):
        """Check that an illegal env name results in an HTTPClientError."""
        self._set_policy_rules(
            {'list_environments': '@',
             'create_environment': '@',
             'show_environment': '@'}
        )
        self.expect_policy_check('create_environment')

        body = {'name': '   '}
        req = self._post('/environments', json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(400, result.status_code)

    def test_unicode_environment_name_create(self):
        """Check that an unicode env name doesn't raise an HTTPClientError."""
        self._configure_opts()
        self._set_policy_rules(
            {'list_environments': '@',
             'create_environment': '@',
             'show_environment': '@'}
        )
        self.expect_policy_check('create_environment')

        body = {'name': u'$yaql \u2665 unicode'}
        req = self._post('/environments', json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)

    def test_no_environment_name_create(self):
        """Check that no env name provided results in an HTTPBadResquest."""
        self._set_policy_rules(
            {'list_environments': '@',
             'create_environment': '@',
             'show_environment': '@'}
        )
        self.expect_policy_check('create_environment')

        body = {'no_name': 'fake'}
        req = self._post('/environments', json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(400, result.status_code)
        result_msg = result.text.replace('\n', '')
        self.assertIn('Please, specify a name of the environment to create',
                      result_msg)

    def test_too_long_environment_name_create(self):
        """Check that an too long env name results in an HTTPBadResquest."""
        self._set_policy_rules(
            {'list_environments': '@',
             'create_environment': '@',
             'show_environment': '@'}
        )
        self.expect_policy_check('create_environment')

        body = {'name': 'a' * 256}
        req = self._post('/environments', json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(400, result.status_code)
        result_msg = result.text.replace('\n', '')
        self.assertIn('Environment name should be 255 characters maximum',
                      result_msg)

    def test_create_environment_with_empty_body(self):
        """Check that empty request body results in an HTTPBadResquest."""
        body = ''
        req = self._post('/environments', body)
        result = req.get_response(self.api)
        self.assertEqual(400, result.status_code)
        result_msg = result.text.replace('\n', '')
        self.assertIn('The server could not comply with the request since it '
                      'is either malformed or otherwise incorrect.',
                      result_msg)

    def test_missing_environment(self):
        """Check that a missing environment results in an HTTPNotFound.

        Environment check will be made in the decorator and raises,
        no need to check policy in this testcase.
        """
        req = self._get('/environments/no-such-id')
        result = req.get_response(self.api)
        self.assertEqual(404, result.status_code)

    def test_update_environment(self):
        """Check that environment rename works."""
        self._set_policy_rules(
            {'show_environment': '@',
             'update_environment': '@'}
        )
        self.expect_policy_check('update_environment',
                                 {'environment_id': '12345'})

        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now

        expected = dict(
            id='12345',
            name='my-env',
            version=0,
            created=fake_now,
            updated=fake_now,
            tenant_id=self.tenant,
            description={
                'Objects': {
                    '?': {'id': '12345'}
                },
                'Attributes': []
            }
        )
        e = models.Environment(**expected)
        test_utils.save_models(e)

        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now

        del expected['description']
        expected['services'] = []
        expected['status'] = 'ready'
        expected['name'] = 'renamed_env'
        expected['updated'] = fake_now

        body = {
            'name': 'renamed_env'
        }
        req = self._put('/environments/12345', json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)

        self.expect_policy_check('show_environment',
                                 {'environment_id': '12345'})
        req = self._get('/environments/12345')
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)

        expected['created'] = timeutils.isotime(expected['created'])[:-1]
        expected['updated'] = timeutils.isotime(expected['updated'])[:-1]
        expected['acquired_by'] = None

        self.assertEqual(expected, json.loads(result.body))

    def test_update_environment_with_existing_name(self):
        self._set_policy_rules(
            {'update_environment': '@'}
        )

        self._create_fake_environment('env1', '111')
        self._create_fake_environment('env2', '222')

        self.expect_policy_check('update_environment',
                                 {'environment_id': '111'})

        body = {
            'name': 'env2'
        }
        req = self._put('/environments/111', json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(409, result.status_code)

    def test_delete_environment(self):
        """Test that environment deletion results in the correct rpc call."""
        result = self._test_delete_or_abandon(abandon=False)
        self.assertEqual('', result.body)
        self.assertEqual(200, result.status_code)

    def test_abandon_environment(self):
        """Check that abandon feature works"""
        result = self._test_delete_or_abandon(abandon=True)
        self.assertEqual('', result.body)
        self.assertEqual(200, result.status_code)

    def test_abandon_environment_of_different_tenant(self):
        """Test abandon environment belongs to another tenant."""
        result = self._test_delete_or_abandon(abandon=True, tenant='not_match')
        self.assertEqual(403, result.status_code)
        self.assertTrue(('User is not authorized to access these'
                         ' tenant resources') in result.body)

    def test_get_last_status_of_different_tenant(self):
        """Test get last services status of env belongs to another tenant."""
        self._create_fake_environment('env1', '111')
        req = self._get('/environments/111/lastStatus', tenant='not_match')
        result = req.get_response(self.api)
        self.assertEqual(403, result.status_code)
        self.assertTrue(('User is not authorized to access these'
                         ' tenant resources') in result.body)

    def test_get_environment(self):
        """Test GET request of an environment in ready status"""
        self._set_policy_rules(
            {'show_environment': '@'}
        )
        self.expect_policy_check('show_environment',
                                 {'environment_id': '123'})
        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now

        env_id = '123'
        self._create_fake_environment(env_id=env_id)
        req = self._get('/environments/{0}'.format(env_id))
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)

        expected = {'tenant_id': self.tenant,
                    'id': env_id,
                    'name': 'my-env',
                    'version': 0,
                    'created': timeutils.isotime(fake_now)[:-1],
                    'updated': timeutils.isotime(fake_now)[:-1],
                    'acquired_by': None,
                    'services': [],
                    'status': 'ready',
                    }
        self.assertEqual(expected, json.loads(result.body))

    def test_get_environment_acquired(self):
        """Test GET request of an environment in deploying status"""
        self._set_policy_rules(
            {'show_environment': '@'}
        )
        self.expect_policy_check('show_environment',
                                 {'environment_id': '1234'})
        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now

        env_id = '1234'
        self._create_fake_environment(env_id=env_id)

        sess_id = '321'
        expected = dict(
            id=sess_id,
            environment_id=env_id,
            version=0,
            state=states.SessionState.DEPLOYING,
            user_id=self.tenant,
            description={
                'Objects': {
                    '?': {'id': '{0}'.format(env_id)}
                },
                'Attributes': {}
            }
        )
        s = models.Session(**expected)
        test_utils.save_models(s)

        req = self._get('/environments/{0}'.format(env_id))
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)

        expected = {'tenant_id': self.tenant,
                    'id': env_id,
                    'name': 'my-env',
                    'version': 0,
                    'created': timeutils.isotime(fake_now)[:-1],
                    'updated': timeutils.isotime(fake_now)[:-1],
                    'acquired_by': sess_id,
                    'services': [],
                    'status': states.EnvironmentStatus.DEPLOYING,
                    }
        self.assertEqual(expected, json.loads(result.body))

    def _create_fake_environment(self, env_name='my-env', env_id='123'):
        fake_now = timeutils.utcnow()
        expected = dict(
            id=env_id,
            name=env_name,
            version=0,
            created=fake_now,
            updated=fake_now,
            tenant_id=self.tenant,
            description={
                'Objects': {
                    '?': {'id': '{0}'.format(env_id)}
                },
                'Attributes': {}
            }
        )
        e = models.Environment(**expected)
        test_utils.save_models(e)

    def _test_delete_or_abandon(self, abandon, env_name='my-env',
                                env_id='123', tenant=None):
        self._set_policy_rules(
            {'delete_environment': '@'}
        )
        self.expect_policy_check(
            'delete_environment',
            {'environment_id': '{0}'.format(env_id)}
        )

        self._create_fake_environment(env_name, env_id)

        path = '/environments/{0}'.format(env_id)

        req = self._delete(path, params={'abandon': abandon},
                           tenant=tenant or self.tenant)
        result = req.get_response(self.api)

        return result
