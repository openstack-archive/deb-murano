#    Copyright (c) 2014 Mirantis, Inc.
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

import mock

from murano.dsl import murano_method
from murano.dsl import serializer
from murano.services import actions
from murano.tests.unit import base


class TestActionsSerializer(base.MuranoTestCase):
    def setUp(self):
        super(TestActionsSerializer, self).setUp()

    def test_old_actions_deletion(self):
        old = {
            'action1': {'name': 'name1', 'enabled': True},
            'action2': {'name': 'name2', 'enabled': True},
            'action3': {'name': 'name3', 'enabled': True},
        }
        new = {
            'action2': {'name': 'name2', 'enabled': False},
            'action3': {'name': 'name3', 'enabled': True},
        }

        result = serializer._merge_actions(old, new)

        self.assertEqual(2, len(result))
        self.assertNotIn('action1', result)

    def test_actions_state_update(self):
        old = {
            'action1': {'name': 'name1', 'enabled': True},
            'action2': {'name': 'name2', 'enabled': True},
        }
        new = {
            'action1': {'name': 'name2', 'enabled': False},
            'action2': {'name': 'name3', 'enabled': True},
        }

        result = serializer._merge_actions(old, new)

        self.assertFalse(result['action1']['enabled'])

    def _get_mocked_obj(self):
        method1 = mock.Mock()
        method1.usage = murano_method.MethodUsages.Action
        method2 = mock.Mock()
        method2.usage = murano_method.MethodUsages.Runtime
        method3 = mock.Mock()
        method3.usage = murano_method.MethodUsages.Action

        obj2_type = mock.Mock()
        obj2_type.parents = []
        obj2_type.methods = {'method3': method3}

        obj = mock.Mock()
        obj.object_id = 'id1'
        obj.type.parents = [obj2_type]
        obj.type.methods = {'method1': method1, 'method2': method2}

        return obj

    def test_object_actions_serialization(self):
        obj = self._get_mocked_obj()

        obj_actions = serializer._serialize_available_action(obj)

        expected_result = {'name': 'method1', 'enabled': True}
        self.assertIn('id1_method1', obj_actions)
        self.assertEqual(expected_result, obj_actions['id1_method1'])

    def test_that_only_actions_are_serialized(self):
        obj = self._get_mocked_obj()
        obj_actions = serializer._serialize_available_action(obj)
        self.assertNotIn('id1_method2', obj_actions)

    def test_parent_actions_are_serialized(self):
        obj = self._get_mocked_obj()

        obj_actions = serializer._serialize_available_action(obj)

        expected_result = {'name': 'method3', 'enabled': True}
        self.assertIn('id1_method3', obj_actions)
        self.assertEqual(expected_result, obj_actions['id1_method3'])


class TestActionFinder(base.MuranoTestCase):
    def setUp(self):
        super(TestActionFinder, self).setUp()

    def test_simple_root_level_search(self):
        model = {
            '?': {
                'id': 'id1',
                '_actions': {
                    'ad_deploy': {
                        'enabled': True,
                        'name': 'deploy'
                    }
                }
            }
        }
        action = actions.ActionServices.find_action(model, 'ad_deploy')
        self.assertEqual('deploy', action[1]['name'])

    def test_recursive_action_search(self):
        model = {
            '?': {
                'id': 'id1',
                '_actions': {'ad_deploy': {'enabled': True, 'name': 'deploy'}}
            },
            'property': {
                '?': {
                    'id': 'id2',
                    '_actions': {
                        'ad_scale': {'enabled': True, 'name': 'scale'}
                    }
                },
            }
        }
        action = actions.ActionServices.find_action(model, 'ad_scale')
        self.assertEqual('scale', action[1]['name'])
