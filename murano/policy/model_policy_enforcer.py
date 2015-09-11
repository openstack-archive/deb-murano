# Copyright (c) 2014 OpenStack Foundation.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
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

import re

from oslo_log import log as logging

from murano.common.i18n import _, _LI
from murano.policy import congress_rules
from murano.policy.modify.actions import action_manager as am


LOG = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised for validation errors."""
    pass


class ModelPolicyEnforcer(object):
    """Policy Enforcer Implementation using Congress client

    Converts murano model to list of congress data rules.

    We ask congress using simulation api of congress rest client
    to resolve "murano_system:predeploy_errors(env_id, obj_id, msg)"
    table along with congress data rules to return validation results.
    """

    def __init__(self, environment, action_manager=None):
        self._environment = environment
        self._client_manager = environment.clients
        self._action_manager = action_manager or am.ModifyActionManager()

    def modify(self, obj, package_loader=None):
        """Modifies model using Congress rule engine.

        @type obj: object model
        @param obj: Representation of model starting on
                      environment level (['Objects'])
        @type class_loader: murano.dsl.class_loader.MuranoClassLoader
        @param class_loader: Optional. Used for evaluating parent class types
        @raises ValidationError in case validation was not successful
        """

        model = obj.to_dictionary()

        LOG.debug('Modifying model')
        LOG.debug(model)

        env_id = model['?']['id']

        result = self._execute_simulation(package_loader, env_id, model,
                                          'predeploy_modify(eid, oid, action)')

        raw_actions = result["result"]
        if raw_actions:
            actions = self._parse_simulation_result('predeploy_modify',
                                                    env_id, raw_actions)
            for action in actions:
                self._action_manager.apply_action(obj, action)

    def validate(self, model, package_loader=None):
        """Validate model using Congress rule engine.

        @type model: dict
        @param model: Dictionary representation of model starting on
                      environment level (['Objects'])
        @type package_loader: murano.dsl.package_loader.MuranoPackageLoader
        @param package_loader: Optional. Used for evaluating parent class types
        @raises ValidationError in case validation was not successful
        """

        if model is None:
            return

        env_id = model['?']['id']

        validation_result = self._execute_simulation(
            package_loader, env_id, model,
            'predeploy_errors(eid, oid, msg)')

        if validation_result["result"]:

            messages = self._parse_simulation_result(
                'predeploy_errors', env_id,
                validation_result["result"])

            if messages:
                result_str = "\n  ".join(map(str, messages))
                msg = _("Murano object model validation failed: {0}").format(
                    "\n  " + result_str)
                LOG.error(msg)
                raise ValidationError(msg)
        else:
            LOG.info(_LI('Model valid'))

    def _execute_simulation(self, package_loader, env_id, model, query):
        rules = congress_rules.CongressRulesManager().convert(
            model, package_loader, self._environment.tenant_id)
        rules_str = map(str, rules)
        # cleanup of data populated by murano driver
        rules_str.insert(0, 'deleteEnv("{0}")'.format(env_id))
        rules_line = " ".join(rules_str)
        LOG.debug('Congress rules: \n  {rules} '
                  .format(rules='\n  '.join(rules_str)))

        client = self._check_client()

        validation_result = client.execute_policy_action(
            "murano_system",
            "simulate",
            False,
            False,
            {'query': query,
             'action_policy': 'murano_action',
             'sequence': rules_line})
        return validation_result

    def _check_client(self):
        client = self._client_manager.get_congress_client(self._environment)
        if not client:
            raise ValueError(_('Congress client is not configured!'))
        return client

    @staticmethod
    def _parse_simulation_result(query, env_id, results):
        """Transforms list of strings in format
            ['predeploy_errors("env_id_1", "obj_id_1", "message1")',
            'predeploy_errors("env_id_2", "obj_id_2", "message2")']
        to list of strings with message only filtered to provided
        env_id (e.g. 'env_id_1'):
            ['message2']
        """

        messages = []
        regexp = query + '\("([^"]*)",\s*"([^"]*)",\s*"(.*)"\)'
        for result in results:
            match = re.search(regexp, result)
            if match:
                if env_id in match.group(1):
                    messages.append(match.group(3))

        return messages
