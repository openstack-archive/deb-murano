# Copyright (c) 2016 Mirantis, Inc.
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

from keystoneauth1 import identity
from keystoneauth1 import loading as ka_loading
from keystoneclient.v3 import client as ks_client
from oslo_config import cfg

from murano.dsl import helpers


CFG_KEYSTONE_GROUP = 'keystone_authtoken'

cfg.CONF.import_group(CFG_KEYSTONE_GROUP, 'keystonemiddleware.auth_token')


def _get_keystone_auth(trust_id=None):
    if not cfg.CONF[CFG_KEYSTONE_GROUP].auth_type:
        # Fallback to legacy v2 options if no auth_type is set.
        # If auth_type is set, it is possible to use the auth loader
        # from keystoneauth1. This is the same fallback as keystonemiddleware
        # uses.
        kwargs = {
            'auth_url':
                cfg.CONF[CFG_KEYSTONE_GROUP].auth_uri.replace('v2.0', 'v3'),
            'username': cfg.CONF[CFG_KEYSTONE_GROUP].admin_user,
            'password': cfg.CONF[CFG_KEYSTONE_GROUP].admin_password,
            'user_domain_name': "Default"
        }
        if not trust_id:
            kwargs['project_name'] = \
                cfg.CONF[CFG_KEYSTONE_GROUP].admin_tenant_name
            kwargs['project_domain_name'] = "Default"
        else:
            kwargs['trust_id'] = trust_id
        auth = identity.Password(**kwargs)
    else:
        kwargs = {}
        if trust_id:
            # Remove project_name and project_id, since we need a trust scoped
            # auth object
            kwargs['project_name'] = None
            kwargs['project_domain_name'] = None
            kwargs['project_id'] = None
            kwargs['trust_id'] = trust_id
        auth = ka_loading.load_auth_from_conf_options(
            cfg.CONF,
            CFG_KEYSTONE_GROUP,
            **kwargs)
    return auth


def _create_keystone_admin_client():
    auth = _get_keystone_auth()
    session = _get_session(
        auth=auth,
        conf_section=cfg.CONF[CFG_KEYSTONE_GROUP])
    return ks_client.Client(session=session)


def get_client_session(execution_session=None, conf=None):
    if not execution_session:
        execution_session = helpers.get_execution_session()
    trust_id = execution_session.trust_id
    if trust_id is None:
        return get_token_client_session(
            token=execution_session.token,
            project_id=execution_session.project_id)
    auth = _get_keystone_auth(trust_id)
    session = _get_session(auth=auth, conf_section=conf)
    return session


def get_token_client_session(token=None, project_id=None, conf=None):
    auth_url = cfg.CONF[CFG_KEYSTONE_GROUP].auth_uri.replace('v2.0', 'v3')
    if token is None or project_id is None:
        execution_session = helpers.get_execution_session()
        token = execution_session.token
        project_id = execution_session.project_id
    token_auth = identity.Token(
        auth_url,
        token=token,
        project_id=project_id)
    session = _get_session(auth=token_auth, conf_section=conf)
    return session


def create_keystone_client(token=None, project_id=None, conf=None):
    return ks_client.Client(session=get_token_client_session(
        token=token, project_id=project_id, conf=conf))


def create_trust(trustee_token=None, trustee_project_id=None):
    admin_client = _create_keystone_admin_client()
    user_client = create_keystone_client(
        token=trustee_token, project_id=trustee_project_id)
    trustee_user = admin_client.session.auth.get_user_id(admin_client.session)
    auth_ref = user_client.session.auth.get_access(user_client.session)
    trustor_user = auth_ref.user_id
    project = auth_ref.project_id
    roles = auth_ref.role_names
    trust = user_client.trusts.create(
        trustor_user=trustor_user,
        trustee_user=trustee_user,
        impersonation=True,
        role_names=roles,
        project=project)
    return trust.id


def delete_trust(trust):
    user_client = _create_keystone_admin_client()
    user_client.trusts.delete(trust)


def _get_config_option(conf_section, option_names, default=None):
    if not isinstance(option_names, (list, tuple)):
        option_names = (option_names,)
    for name in option_names:
        if hasattr(conf_section, name):
            return getattr(conf_section, name)
    return default


def _get_session(auth, conf_section):
    # Fallback to keystone_authtoken section for TLS parameters
    # if no other conf_section supplied
    if not conf_section:
        conf_section = cfg.CONF[CFG_KEYSTONE_GROUP]
    session = ka_loading.session.Session().load_from_options(
        auth=auth,
        insecure=_get_config_option(conf_section, 'insecure', False),
        cacert=_get_config_option(
            conf_section,
            ('ca_file', 'cafile', 'cacert')),
        key=_get_config_option(conf_section, ('key_file', 'keyfile')),
        cert=_get_config_option(conf_section, ('cert_file', 'certfile')))
    return session


def get_session_client_parameters(service_type=None,
                                  region='',
                                  interface=None,
                                  service_name=None,
                                  conf=None,
                                  session=None,
                                  execution_session=None):
    if region == '':
        region = cfg.CONF.home_region
    result = {
        'session': session or get_client_session(
            execution_session=execution_session, conf=conf)
    }

    url = _get_config_option(conf, 'url')
    if url:
        result['endpoint_override'] = url
    else:
        if not interface:
            interface = _get_config_option(conf, 'endpoint_type')
        result.update({
            'service_type': service_type,
            'service_name': service_name,
            'interface': interface,
            'region_name': region
        })
    return result
