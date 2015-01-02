# Copyright (c) 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import os
import socket
import time
import uuid

import testresources
import testtools

from heatclient import client as heatclient
from keystoneclient.v2_0 import client as ksclient
from muranoclient import client as mclient
import muranoclient.common.exceptions as exceptions

import murano.tests.functional.engine.config as cfg


CONF = cfg.cfg.CONF


class MuranoBase(testtools.TestCase, testtools.testcase.WithAttributes,
                 testresources.ResourcedTestCase):

    @classmethod
    def setUpClass(cls):
        super(MuranoBase, cls).setUpClass()

        cfg.load_config()

        keystone_client = ksclient.Client(username=CONF.murano.user,
                                          password=CONF.murano.password,
                                          tenant_name=CONF.murano.tenant,
                                          auth_url=CONF.murano.auth_url)

        heat_url = keystone_client.service_catalog.url_for(
            service_type='orchestration', endpoint_type='publicURL')

        cls.heat_client = heatclient.Client('1', endpoint=heat_url,
                                            token=keystone_client.auth_token)

        url = CONF.murano.murano_url
        murano_url = url if 'v1' not in url else "/".join(
            url.split('/')[:url.split('/').index('v1')])

        cls.muranoclient = mclient.Client('1',
                                          endpoint=murano_url,
                                          token=keystone_client.auth_token)

        cls.linux = CONF.murano.linux_image

        cls.pkgs_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            os.path.pardir,
            'murano-app-incubator'
        ))

        def upload_package(package_name, body, app):

            files = {'%s' % package_name: open(app, 'rb')}

            return cls.muranoclient.packages.create(body, files)

        upload_package(
            'PostgreSQL',
            {"categories": ["Databases"], "tags": ["tag"]},
            os.path.join(cls.pkgs_path, 'io.murano.databases.PostgreSql.zip')
        )
        upload_package(
            'SqlDatabase',
            {"categories": ["Databases"], "tags": ["tag"]},
            os.path.join(cls.pkgs_path, 'io.murano.databases.SqlDatabase.zip')
        )
        upload_package(
            'Apache',
            {"categories": ["Application Servers"], "tags": ["tag"]},
            os.path.join(cls.pkgs_path,
                         'io.murano.apps.apache.ApacheHttpServer.zip')
        )
        upload_package(
            'Tomcat',
            {"categories": ["Application Servers"], "tags": ["tag"]},
            os.path.join(cls.pkgs_path, 'io.murano.apps.apache.Tomcat.zip')
        )
        upload_package(
            'Telnet',
            {"categories": ["Web"], "tags": ["tag"]},
            os.path.join(cls.pkgs_path, 'io.murano.apps.linux.Telnet.zip')
        )

    def setUp(self):
        super(MuranoBase, self).setUp()

        self.environments = []

    def tearDown(self):
        super(MuranoBase, self).tearDown()

        for env in self.environments:
            try:
                self.environment_delete(env)
            except Exception:
                pass

    def environment_delete(self, environment_id, timeout=180):
        self.muranoclient.environments.delete(environment_id)

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                self.muranoclient.environments.get(environment_id)
            except exceptions.HTTPNotFound:
                return
        raise Exception(
            'Environment {0} was not deleted in {1} seconds'.format(
                environment_id, timeout))

    def wait_for_environment_deploy(self, environment):
        start_time = time.time()

        while environment.manager.get(environment.id).status != 'ready':
            if time.time() - start_time > 1200:
                self.fail(
                    'Environment deployment is not finished in 1200 seconds')
            time.sleep(5)

        return environment.manager.get(environment.id)

    def check_port_access(self, ip, port):
        result = 1
        start_time = time.time()
        while time.time() - start_time < 300:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((str(ip), port))
            sock.close()

            if result == 0:
                break
            time.sleep(5)

        self.assertEqual(0, result, '%s port is closed on instance' % port)

    def deployment_success_check(self, environment, port):
        deployment = self.muranoclient.deployments.list(environment.id)[-1]

        self.assertEqual('success', deployment.state,
                         'Deployment status is {0}'.format(deployment.state))

        ip = environment.services[-1]['instance']['floatingIpAddress']

        if ip:
            self.check_port_access(ip, port)
        else:
            self.fail('Instance does not have floating IP')

    def test_deploy_telnet(self):
        post_body = {
            "instance": {
                "flavor": "m1.medium",
                "image": self.linux,
                "assignFloatingIp": True,
                "?": {
                    "type": "io.murano.resources.LinuxMuranoInstance",
                    "id": str(uuid.uuid4())
                },
                "name": "testMurano"
            },
            "name": "teMurano",
            "?": {
                "type": "io.murano.apps.linux.Telnet",
                "id": str(uuid.uuid4())
            }
        }

        environment_name = 'Telnetenv' + uuid.uuid4().hex[:5]

        env = self._quick_deploy(environment_name, post_body)

        self.deployment_success_check(env, 23)

    def test_deploy_apache(self):
        post_body = {
            "instance": {
                "flavor": "m1.medium",
                "image": self.linux,
                "assignFloatingIp": True,
                "?": {
                    "type": "io.murano.resources.LinuxMuranoInstance",
                    "id": str(uuid.uuid4())
                },
                "name": "testMurano"
            },
            "name": "teMurano",
            "?": {
                "type": "io.murano.apps.apache.ApacheHttpServer",
                "id": str(uuid.uuid4())
            }
        }

        environment_name = 'Apacheenv' + uuid.uuid4().hex[:5]

        env = self._quick_deploy(environment_name, post_body)

        self.deployment_success_check(env, 80)

    def test_deploy_postgresql(self):
        post_body = {
            "instance": {
                "flavor": "m1.medium",
                "image": self.linux,
                "assignFloatingIp": True,
                "?": {
                    "type": "io.murano.resources.LinuxMuranoInstance",
                    "id": str(uuid.uuid4())
                },
                "name": "testMurano"
            },
            "name": "teMurano",
            "database": "test_db",
            "username": "test_usr",
            "password": "test_pass",
            "?": {
                "type": "io.murano.databases.PostgreSql",
                "id": str(uuid.uuid4())
            }
        }

        environment_name = 'Postgreenv' + uuid.uuid4().hex[:5]

        env = self._quick_deploy(environment_name, post_body)

        self.deployment_success_check(env, 5432)

    def test_deploy_tomcat(self):
        post_body = {
            "instance": {
                "flavor": "m1.medium",
                "image": self.linux,
                "assignFloatingIp": True,
                "?": {
                    "type": "io.murano.resources.LinuxMuranoInstance",
                    "id": str(uuid.uuid4())
                },
                "name": "testMurano"
            },
            "name": "teMurano",
            "?": {
                "type": "io.murano.apps.apache.Tomcat",
                "id": str(uuid.uuid4())
            }
        }

        environment_name = 'Tomcatenv' + uuid.uuid4().hex[:5]

        env = self._quick_deploy(environment_name, post_body)

        self.deployment_success_check(env, 8080)

    def _get_telnet_app(self):
        return {
            "instance": {
                "?": {
                    "type": "io.murano.resources.LinuxMuranoInstance",
                    "id": str(uuid.uuid4())
                },
                "flavor": "m1.medium",
                "image": self.linux,
                "name": "instance{0}".format(uuid.uuid4().hex[:5]),
            },
            "name": "app{0}".format(uuid.uuid4().hex[:5]),
            "?": {
                "type": "io.murano.apps.linux.Telnet",
                "id": str(uuid.uuid4())
            }
        }

    def _quick_deploy(self, name, *apps):
        environment = self.muranoclient.environments.create({'name': name})
        self.environments.append(environment.id)

        session = self.muranoclient.sessions.configure(environment.id)

        for app in apps:
            self.muranoclient.services.post(environment.id,
                                            path='/',
                                            data=app,
                                            session_id=session.id)

        self.muranoclient.sessions.deploy(environment.id, session.id)

        return self.wait_for_environment_deploy(environment)

    def _get_stack(self, environment_id):

        for stack in self.heat_client.stacks.list():
            if environment_id in stack.description:
                return stack

    def test_instance_refs_are_removed_after_application_is_removed(self):
        # FIXME(sergmelikyan): Revise this as part of proper fix for #1359998
        self.skipTest('Skipped until proper fix for #1359998 is proposed')

        name = 'e' + uuid.uuid4().hex

        # create environment with telnet application
        application1 = self._get_telnet_app()
        application2 = self._get_telnet_app()
        application_id = application1['?']['id']
        instance_name = application1['instance']['name']
        apps = [application1, application2]
        environment = self._quick_deploy(name, *apps)

        # delete telnet application
        session = self.muranoclient.sessions.configure(environment.id)
        self.muranoclient.services.delete(environment.id,
                                          '/' + application_id,
                                          session.id)
        self.muranoclient.sessions.deploy(environment.id, session.id)
        self.wait_for_environment_deploy(environment)

        stack_name = self._get_stack(environment.id).stack_name
        template = self.heat_client.stacks.template(stack_name)
        ip_addresses = '{0}-assigned-ip'.format(instance_name)
        floating_ip = '{0}-FloatingIPaddress'.format(instance_name)

        self.assertNotIn(ip_addresses, template['outputs'])
        self.assertNotIn(floating_ip, template['outputs'])
        self.assertNotIn(instance_name, template['resources'])

    def test_stack_deletion_after_env_is_deleted(self):
        name = 'e' + uuid.uuid4().hex

        application = self._get_telnet_app()
        environment = self._quick_deploy(name, application)

        stack = self._get_stack(environment.id)
        self.assertIsNotNone(stack)

        self.muranoclient.environments.delete(environment.id)

        start_time = time.time()
        while stack is not None:
            if time.time() - start_time > 300:
                break
            time.sleep(5)
            stack = self._get_stack(environment.id)
        self.assertIsNone(stack, 'stack is not deleted')
