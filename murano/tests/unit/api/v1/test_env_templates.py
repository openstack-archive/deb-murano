# Copyright (c) 2015 Telefonica I+D.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from oslo.config import cfg
from oslo.utils import timeutils

from murano.api.v1 import templates
from murano.common import config
from murano.db import models
import murano.tests.unit.api.base as tb
import murano.tests.unit.utils as test_utils


class TestEnvTemplateApi(tb.ControllerTest, tb.MuranoApiTestCase):
    def setUp(self):
        super(TestEnvTemplateApi, self).setUp()
        self.controller = templates.Controller()
        self.uuids = ['env_template_id', 'other', 'network_id',
                      'environment_id', 'session_id']
        self.mock_uuid = self._stub_uuid(self.uuids)

    def test_list_empty_env_templates(self):
        """Check that with no templates an empty list is returned."""
        self._set_policy_rules(
            {'list_env_templates': '@'}
        )
        self.expect_policy_check('list_env_templates')

        req = self._get('/templates')
        result = req.get_response(self.api)
        self.assertEqual({'templates': []}, json.loads(result.body))

    def test_create_env_templates(self):
        """Create an template, test template.show()."""
        self._set_policy_rules(
            {'list_env_templates': '@',
             'create_env_template': '@',
             'show_env_template': '@'}
        )
        self.expect_policy_check('create_env_template')

        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now

        expected = {'tenant_id': self.tenant,
                    'id': 'env_template_id',
                    'name': 'mytemp',
                    'networking': {},
                    'version': 0,
                    'created': timeutils.isotime(fake_now)[:-1],
                    'updated': timeutils.isotime(fake_now)[:-1]}

        body = {'name': 'mytemp'}
        req = self._post('/templates', json.dumps(body))
        result = req.get_response(self.api)

        self.assertEqual(expected, json.loads(result.body))

        # Reset the policy expectation
        self.expect_policy_check('list_env_templates')

        req = self._get('/templates')
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)
        self.assertEqual({'templates': [expected]}, json.loads(result.body))

        expected['services'] = []

        self.expect_policy_check('show_env_template',
                                 {'env_template_id': self.uuids[0]})
        req = self._get('/templates/%s' % self.uuids[0])
        result = req.get_response(self.api)
        self.assertEqual(expected, json.loads(result.body))

    def test_illegal_template_name_create(self):
        """Check that an illegal temp name results in an HTTPClientError."""
        self._set_policy_rules(
            {'list_env_templates': '@',
             'create_env_template': '@',
             'show_env_template': '@'}
        )
        self.expect_policy_check('create_env_template')

        body = {'name': 'my+#temp'}
        req = self._post('/templates', json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(400, result.status_code)

    def test_mallformed_body(self):
        """Check that an illegal temp name results in an HTTPClientError."""
        self._set_policy_rules(
            {'create_env_template': '@'}
        )
        self.expect_policy_check('create_env_template')

        body = {'invalid': 'test'}
        req = self._post('/templates', json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(400, result.status_code)

    def test_missing_env_template(self):
        """Check that a missing environment template
        results in an HTTPNotFound.
        """
        self._set_policy_rules(
            {'show_env_template': '@'}
        )
        self.expect_policy_check('show_env_template',
                                 {'env_template_id': 'no-such-id'})

        req = self._get('/templates/no-such-id')
        result = req.get_response(self.api)
        self.assertEqual(404, result.status_code)

    def test_update_env_template(self):
        """Check that environment rename works."""
        self._set_policy_rules(
            {'show_env_template': '@',
             'update_env_template': '@'}
        )
        self.expect_policy_check('update_env_template',
                                 {'env_template_id': '12345'})

        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now

        expected = dict(
            id='12345',
            name='my-temp',
            version=0,
            networking={},
            created=fake_now,
            updated=fake_now,
            tenant_id=self.tenant,
            description={
                'name': 'my-temp',
                '?': {'id': '12345'}
            }
        )
        e = models.EnvironmentTemplate(**expected)
        test_utils.save_models(e)

        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now

        del expected['description']
        expected['services'] = []
        expected['name'] = 'renamed_temp'
        expected['updated'] = fake_now

        body = {
            'name': 'renamed_temp'
        }
        req = self._put('/templates/12345', json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)

        self.expect_policy_check('show_env_template',
                                 {'env_template_id': '12345'})
        req = self._get('/templates/12345')
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)

        expected['created'] = timeutils.isotime(expected['created'])[:-1]
        expected['updated'] = timeutils.isotime(expected['updated'])[:-1]

        self.assertEqual(expected, json.loads(result.body))

    def test_delete_env_templates(self):
        """Test that environment deletion results in the correct rpc call."""
        self._set_policy_rules(
            {'delete_env_template': '@'}
        )
        self.expect_policy_check(
            'delete_env_template', {'env_template_id': '12345'}
        )

        fake_now = timeutils.utcnow()
        expected = dict(
            id='12345',
            name='my-temp',
            version=0,
            networking={},
            created=fake_now,
            updated=fake_now,
            tenant_id=self.tenant,
            description={
                'name': 'my-temp',
                '?': {'id': '12345'}
            }
        )
        e = models.EnvironmentTemplate(**expected)
        test_utils.save_models(e)

        req = self._delete('/templates/12345')
        result = req.get_response(self.api)

        # Should this be expected behavior?
        self.assertEqual('', result.body)
        self.assertEqual(200, result.status_code)

    def test_create_env_templates_with_applications(self):
        """Create an template, test template.show()."""
        self._set_policy_rules(
            {'list_env_templates': '@',
             'create_env_template': '@',
             'show_env_template': '@'}
        )
        self.expect_policy_check('create_env_template')

        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now
        expected = {'tenant_id': self.tenant,
                    'id': self.uuids[0],
                    'name': 'env_template_name',
                    'networking': {},
                    'version': 0,
                    'created': timeutils.isotime(fake_now)[:-1],
                    'updated': timeutils.isotime(fake_now)[:-1]}

        services = [
            {
                "instance": {
                    "assignFloatingIp": "true",
                    "keyname": "mykeyname",
                    "image": "cloud-fedora-v3",
                    "flavor": "m1.medium",
                    "?": {
                        "type": "io.murano.resources.Linux",
                        "id": "ef984a74-29a4-45c0-b1dc-2ab9f075732e"
                    }
                },
                "name": "orion",
                "port": "8080",
                "?": {
                    "type": "io.murano.apps.apache.Tomcat",
                    "id": "54cea43d-5970-4c73-b9ac-fea656f3c722"
                }
            }
        ]
        expected['services'] = services

        body = {
            "name": "env_template_name",
            "services": [
                {
                    "instance": {
                        "assignFloatingIp": "true",
                        "keyname": "mykeyname",
                        "image": "cloud-fedora-v3",
                        "flavor": "m1.medium",
                        "?": {
                            "type": "io.murano.resources.Linux",
                            "id": "ef984a74-29a4-45c0-b1dc-2ab9f075732e"
                        }
                    },
                    "name": "orion",
                    "port": "8080",
                    "?": {
                        "type": "io.murano.apps.apache.Tomcat",
                        "id": "54cea43d-5970-4c73-b9ac-fea656f3c722"
                    }
                }
            ]
        }

        req = self._post('/templates', json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(expected, json.loads(result.body))

        # Reset the policy expectation
        self.expect_policy_check('list_env_templates')

        req = self._get('/templates')
        result = req.get_response(self.api)
        del expected['services']
        self.assertEqual(200, result.status_code)
        self.assertEqual({'templates': [expected]}, json.loads(result.body))

        # Reset the policy expectation
        self.expect_policy_check('show_env_template',
                                 {'env_template_id': self.uuids[0]})
        expected['services'] = services
        req = self._get('/templates/%s' % self.uuids[0])
        result = req.get_response(self.api)
        self.assertEqual(expected, json.loads(result.body))

    def test_add_application_to_template(self):
        """Create an template, test template.show()."""
        self._set_policy_rules(
            {'create_env_template': '@',
             'add_application': '@'}
        )
        self.expect_policy_check('create_env_template')

        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now
        services = [
            {
                "instance": {
                    "assignFloatingIp": "true",
                    "keyname": "mykeyname",
                    "image": "cloud-fedora-v3",
                    "flavor": "m1.medium",
                    "?": {
                        "type": "io.murano.resources.Linux",
                        "id": "ef984a74-29a4-45c0-b1dc-2ab9f075732e"
                    }
                },
                "name": "orion",
                "port": "8080",
                "?": {
                    "type": "io.murano.apps.apache.Tomcat",
                    "id": "54cea43d-5970-4c73-b9ac-fea656f3c722"
                }
            }
        ]

        body = {
            "name": "template_name",
        }

        req = self._post('/templates', json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)

        body = services
        req = self._post('/templates/%s/services' % self.uuids[0],
                         json.dumps(body))
        result = req.get_response(self.api)

        self.assertEqual(200, result.status_code)
        self.assertEqual(services, json.loads(result.body))
        req = self._get('/templates/%s/services' % self.uuids[0])
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)
        self.assertEqual(1, len(json.loads(result.body)))

        service_no_instance = [
            {
                "instance": "ef984a74-29a4-45c0-b1dc-2ab9f075732e",
                "name": "tomcat",
                "port": "8080",
                "?": {
                    "type": "io.murano.apps.apache.Tomcat",
                    "id": "54cea43d-5970-4c73-b9ac-fea656f3c722"
                }
            }
        ]

        req = self._post('/templates/%s/services' % self.uuids[0],
                         json.dumps(service_no_instance))
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)

        req = self._get('/templates/%s/services' % self.uuids[0])
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)
        self.assertEqual(2, len(json.loads(result.body)))

    def test_delete_application_in_template(self):
        """Create an template, test template.show()."""
        self._set_policy_rules(
            {'create_env_template': '@',
             'delete_env_application': '@'}
        )
        self.expect_policy_check('create_env_template')

        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now

        body = {
            "name": "mytemplate",
            "services": [
                {
                    "name": "tomcat",
                    "port": "8080",
                    "?": {
                        "type": "io.murano.apps.apache.Tomcat",
                        "id": "54cea43d-5970-4c73-b9ac-fea656f3c722"
                    }
                }
            ]
        }

        req = self._post('/templates', json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)

        req = self._get('/templates/%s/services' % self.uuids[0])
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)
        self.assertEqual(1, len(json.loads(result.body)))

        service_id = '54cea43d-5970-4c73-b9ac-fea656f3c722'
        req = self._get('/templates/' + self.uuids[0] +
                        '/services/' + service_id)
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)

        req = self._delete('/templates/' + self.uuids[0] +
                           '/services/' + service_id)
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)

        req = self._get('/templates/' + self.uuids[0] +
                        '/services/' + service_id)
        result = req.get_response(self.api)
        self.assertEqual(404, result.status_code)

    def test_create_environment(self):
        """Test that environment is created, session configured."""

        opts = [
            cfg.StrOpt('config_dir'),
            cfg.StrOpt('config_file', default='murano.conf'),
            cfg.StrOpt('project', default='murano'),
        ]
        config.CONF.register_opts(opts)
        self._set_policy_rules(
            {'create_env_template': '@',
             'create_environment': '@'}
        )

        self._create_env_template_no_service()
        body_env = {'name': 'my_template'}

        self.expect_policy_check('create_environment',
                                 {'env_template_id': self.uuids[0]})
        req = self._post('/templates/%s/create-environment' %
                         self.uuids[0], json.dumps(body_env))
        session_result = req.get_response(self.api)
        self.assertEqual(200, session_result.status_code)
        self.assertIsNotNone(session_result)
        body_returned = json.loads(session_result.body)
        self.assertEqual(self.uuids[4], body_returned['session_id'])
        self.assertEqual(self.uuids[3], body_returned['environment_id'])

    def test_create_env_with_template_no_services(self):
        """Test that environment is created and session with template
        without services.
        """
        opts = [
            cfg.StrOpt('config_dir'),
            cfg.StrOpt('config_file', default='murano.conf'),
            cfg.StrOpt('project', default='murano'),
        ]
        config.CONF.register_opts(opts)
        self._set_policy_rules(
            {'create_env_template': '@',
             'create_environment': '@'}
        )
        self._create_env_template_no_service()

        self.expect_policy_check('create_environment',
                                 {'env_template_id': self.uuids[0]})
        body = {'name': 'my_template'}

        req = self._post('/templates/%s/create-environment' %
                         self.uuids[0], json.dumps(body))
        result = req.get_response(self.api)
        self.assertIsNotNone(result)
        self.assertEqual(200, result.status_code)
        body_returned = json.loads(result.body)
        self.assertEqual(self.uuids[4], body_returned['session_id'])
        self.assertEqual(self.uuids[3], body_returned['environment_id'])

    def test_mallformed_env_body(self):
        """Check that an illegal temp name results in an HTTPClientError."""
        self._set_policy_rules(
            {'create_env_template': '@',
             'create_environment': '@'}
        )
        self. _create_env_template_no_service()

        self.expect_policy_check('create_environment',
                                 {'env_template_id': self.uuids[0]})
        body = {'invalid': 'test'}
        req = self._post('/templates/%s/create-environment' %
                         self.uuids[0], json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(400, result.status_code)

    def test_create_env_notexisting_templatebody(self):
        """Check that an illegal temp name results in an HTTPClientError."""
        self._set_policy_rules(
            {'create_environment': '@'}
        )
        env_template_id = 'noexisting'
        self.expect_policy_check('create_environment',
                                 {'env_template_id': env_template_id})

        body = {'name': 'test'}
        req = self._post('/templates/%s/create-environment'
                         % env_template_id, json.dumps(body))
        result = req.get_response(self.api)
        self.assertEqual(404, result.status_code)

    def _create_env_template_no_service(self):
        self.expect_policy_check('create_env_template')
        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now

        req = self._post('/templates', json.dumps({'name': 'name'}))
        result = req.get_response(self.api)
        self.assertEqual(200, result.status_code)

    def _create_env_template_services(self):
        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now

        self.expect_policy_check('create_env_template')

        fake_now = timeutils.utcnow()
        timeutils.utcnow.override_time = fake_now
        body = {
            "name": "env_template_name",
            "services": [
                {
                    "instance": {
                        "assignFloatingIp": "true",
                        "keyname": "mykeyname",
                        "image": "cloud-fedora-v3",
                        "flavor": "m1.medium",
                        "?": {
                            "type": "io.murano.resources.Linux",
                            "id": "ef984a74-29a4-45c0-b1dc-2ab9f075732e"
                        }
                    },
                    "name": "orion",
                    "port": "8080",
                    "?": {
                        "type": "io.murano.apps.apache.Tomcat",
                        "id": "54cea43d-5970-4c73-b9ac-fea656f3c722"
                    }
                }
            ]
        }

        req = self._post('/templates', json.dumps(body))
        req.get_response(self.api)
