# SPDX-License-Identifier: Apache-2.0

r"""
=======================================
B113: Test for missing requests timeout
=======================================

This plugin test checks for ``requests`` calls without a timeout specified.

Nearly all production code should use this parameter in nearly all requests,
Failure to do so can cause your program to hang indefinitely.

When request methods are used without the timeout parameter set,
Bandit will return a MEDIUM severity error.


:Example:

.. code-block:: none

    >> Issue: [B113:request_without_timeout] Requests call without timeout
       Severity: Medium   Confidence: High
       Location: examples/requests-missing-timeout.py:3:0
       More Info: https://bandit.readthedocs.io/en/latest/plugins/b113_request_without_timeout.html
    2
    3	requests.get('https://gmail.com')
    4	requests.get('https://gmail.com', timeout=None)

    --------------------------------------------------
    >> Issue: [B113:request_without_timeout] Requests call with timeout set to None
       Severity: Medium   Confidence: High
       Location: examples/requests-missing-timeout.py:4:0
       More Info: https://bandit.readthedocs.io/en/latest/plugins/b113_request_without_timeout.html
    3	requests.get('https://gmail.com')
    4	requests.get('https://gmail.com', timeout=None)
    5	requests.get('https://gmail.com', timeout=5)

.. seealso::

 - https://2.python-requests.org/en/master/user/quickstart/#timeouts
    .. versionadded:: 1.7.1

"""  # noqa: E501

import bandit
from bandit.core import test_properties as test


@test.checks('Call')
@test.test_id('B113')
def request_without_timeout(context):
    http_verbs = ('get', 'options', 'head', 'post', 'put', 'patch', 'delete')
    if ('requests' in context.call_function_name_qual and
            context.call_function_name in http_verbs):
        # check for missing timeout
        if context.check_call_arg_value('timeout') is None:
            issue = bandit.Issue(
                severity=bandit.MEDIUM,
                confidence=bandit.LOW,
                text="Requests call without timeout"
            )
            return issue
        # check for timeout=None
        if context.check_call_arg_value('timeout', 'None'):
            issue = bandit.Issue(
                severity=bandit.MEDIUM,
                confidence=bandit.LOW,
                text="Requests call with timeout set to None"
            )
            return issue
