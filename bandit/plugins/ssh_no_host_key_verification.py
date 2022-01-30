# Copyright (c) 2018 VMware, Inc.
#
# SPDX-License-Identifier: Apache-2.0

r"""
==========================================
B507: Test for missing host key validation
==========================================

Encryption in general is typically critical to the security of many
applications.  Using SSH can greatly increase security by guaranteeing the
identity of the party you are communicating with.  This is accomplished by one
or both parties presenting trusted host keys during the connection
initialization phase of SSH.

When paramiko methods are used, host keys are verified by default. If host key
verification is disabled, Bandit will return a HIGH severity error.

:Example:

.. code-block:: none

    >> Issue: [B507:ssh_no_host_key_verification] Paramiko call with policy set
    to automatically trust the unknown host key.
    Severity: High   Confidence: Medium
    Location: examples/no_host_key_verification.py:4
    3   ssh_client = client.SSHClient()
    4   ssh_client.set_missing_host_key_policy(client.AutoAddPolicy)
    5   ssh_client.set_missing_host_key_policy(client.WarningPolicy)


.. versionadded:: 1.5.1

"""

import bandit
from bandit.core import cwemap
from bandit.core import test_properties as test


@test.checks('Call')
@test.test_id('B507')
def ssh_no_host_key_verification(context):
    if (context.is_module_imported_like('paramiko') and
            context.call_function_name == 'set_missing_host_key_policy'):
        if (context.call_args and
                context.call_args[0] in ['AutoAddPolicy', 'WarningPolicy']):
            issue = bandit.Issue(
                severity=bandit.HIGH,
                cwe=cwemap.CWEMAP["B507"],
                confidence=bandit.MEDIUM,
                text='Paramiko call with policy set to automatically trust '
                     'the unknown host key.',
                lineno=context.get_lineno_for_call_arg(
                    'set_missing_host_key_policy'),
            )
            return issue
