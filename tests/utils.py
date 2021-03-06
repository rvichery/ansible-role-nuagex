import json
import os
import time
import vcr

from ansible.compat.tests.mock import patch
from ansible.module_utils import basic, urls
from ansible.module_utils._text import to_bytes
from vcr_unittest import VCRMixin


class AnsibleExitJson(Exception):
    """Exception class to be raised by module.exit_json and caught by the test case"""
    pass


class AnsibleFailJson(Exception):
    """Exception class to be raised by module.fail_json and caught by the test case"""
    pass


class AnsibleVCRMixin(VCRMixin):
    """VCRMixin with patching for the custom HTTPSConnection class that Ansible is using"""
    def _get_vcr_kwargs(self):
        return {
            'custom_patches': ((urls, 'CustomHTTPSConnection', vcr.stubs.VCRHTTPSConnection),),
            'cassette_library_dir': os.path.join(os.path.dirname(os.path.realpath(__file__)), 'vcr_casettes'),
            'filter_post_data_parameters': [('username', 'USERNAME'), ('password', 'PASSWORD')]
        }

    def is_casette_recording(self):
        return not bool(self.cassette.requests)


class AnsibleUnittestingMixin(object):
    def setUp(self):
        self.mock_module_helper = patch.multiple(
            basic.AnsibleModule,
            exit_json=exit_json,
            fail_json=fail_json,
            tmpdir='/tmp',
        )
        self.mock_module_helper.start()
        self.addCleanup(self.mock_module_helper.stop)

    def prevent_sleeping(self):
        mock = patch.object(time, 'sleep')
        mock.start()
        self.addCleanup(mock.stop)

    def assertPresent(self, value):
        self.assertTrue(value, msg='Expected value, got {}'.format(value))

    def assertLabReturned(self, result):
        self.assertEqual(fetch_data(result, 'lab_name'), 'integration-tests')
        self.assertPresent(fetch_data(result, 'lab_id'))
        self.assertPresent(fetch_data(result, 'lab_ip'))

        web = fetch_data(result, 'lab_web')
        self.assertPresent(web)
        self.assertPresent(web.get('address'))
        self.assertPresent(web.get('org'))
        self.assertPresent(web.get('user'))
        self.assertPresent(web.get('password'))

        amqp = fetch_data(result, 'lab_amqp')
        self.assertPresent(amqp)
        self.assertPresent(amqp.get('address'))
        self.assertPresent(amqp.get('user'))
        self.assertPresent(amqp.get('password'))

    def assertNoLabReturned(self, result):
        self.assertFalse(fetch_data(result, 'lab_name'))
        self.assertFalse(fetch_data(result, 'lab_id'))


def set_module_args(args):
    """prepare arguments so that they will be picked up during module creation"""
    args = json.dumps({'ANSIBLE_MODULE_ARGS': args})
    basic._ANSIBLE_ARGS = to_bytes(args)


def exit_json(*args, **kwargs):
    """function to patch over exit_json; package return data into an exception"""
    if 'changed' not in kwargs:
        kwargs['changed'] = False
    raise AnsibleExitJson(kwargs)


def fail_json(*args, **kwargs):
    """function to patch over fail_json; package return data into an exception"""
    kwargs['failed'] = True
    raise AnsibleFailJson(kwargs)


def fetch_data(result_exception, key):
    """Fetch module result data out of AnsibleFailsJson exception"""
    return result_exception.exception.args[0].get(key, None)
