# -*- coding:utf-8 -*-
#
# Copyright 2014 Hewlett-Packard Development Company, L.P.
#
# SPDX-License-Identifier: Apache-2.0
import argparse
import fnmatch
import logging
import os
import sys
import textwrap

import bandit
from bandit.core import config as b_config
from bandit.core import constants
from bandit.core import manager as b_manager
from bandit.core import utils

BASE_CONFIG = 'bandit.yaml'
LOG = logging.getLogger()


def _init_logger(log_level=logging.INFO, log_format=None):
    '''Initialize the logger

    :param debug: Whether to enable debug mode
    :return: An instantiated logging instance
    '''
    LOG.handlers = []

    if not log_format:
        # default log format
        log_format_string = constants.log_format_string
    else:
        log_format_string = log_format

    logging.captureWarnings(True)

    LOG.setLevel(log_level)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(log_format_string))
    LOG.addHandler(handler)
    LOG.debug("logging initialized")


def _get_options_from_ini(ini_path, target):
    """Return a dictionary of config options or None if we can't load any."""
    ini_file = None

    if ini_path:
        ini_file = ini_path
    else:
        bandit_files = []

        for t in target:
            for root, _, filenames in os.walk(t):
                for filename in fnmatch.filter(filenames, '.bandit'):
                    bandit_files.append(os.path.join(root, filename))

        if len(bandit_files) > 1:
            LOG.error('Multiple .bandit files found - scan separately or '
                      'choose one with --ini\n\t%s', ', '.join(bandit_files))
            sys.exit(2)

        elif len(bandit_files) == 1:
            ini_file = bandit_files[0]
            LOG.info('Found project level .bandit file: %s', bandit_files[0])

    if ini_file:
        return utils.parse_ini_file(ini_file)
    else:
        return None


def _init_extensions():
    from bandit.core import extension_loader as ext_loader
    return ext_loader.MANAGER


def _log_option_source(arg_val, ini_val, option_name):
    """It's useful to show the source of each option."""
    if arg_val:
        LOG.info("Using command line arg for %s", option_name)
        return arg_val
    elif ini_val:
        LOG.info("Using ini file for %s", option_name)
        return ini_val
    else:
        return None


def _running_under_virtualenv():
    if hasattr(sys, 'real_prefix'):
        return True
    elif sys.prefix != getattr(sys, 'base_prefix', sys.prefix):
        return True


def _get_profile(config, profile_name, config_path):
    profile = {}
    if profile_name:
        profiles = config.get_option('profiles') or {}
        profile = profiles.get(profile_name)
        if profile is None:
            raise utils.ProfileNotFound(config_path, profile_name)
        LOG.debug("read in legacy profile '%s': %s", profile_name, profile)
    else:
        profile['include'] = set(config.get_option('tests') or [])
        profile['exclude'] = set(config.get_option('skips') or [])
    return profile


def _log_info(args, profile):
    inc = ",".join([t for t in profile['include']]) or "None"
    exc = ",".join([t for t in profile['exclude']]) or "None"
    LOG.info("profile include tests: %s", inc)
    LOG.info("profile exclude tests: %s", exc)
    LOG.info("cli include tests: %s", args.tests)
    LOG.info("cli exclude tests: %s", args.skips)


def main():
    # bring our logging stuff up as early as possible
    debug = (logging.DEBUG if '-d' in sys.argv or '--debug' in sys.argv else
             logging.INFO)
    _init_logger(debug)
    extension_mgr = _init_extensions()

    baseline_formatters = [f.name for f in filter(lambda x:
                                                  hasattr(x.plugin,
                                                          '_accepts_baseline'),
                                                  extension_mgr.formatters)]

    # now do normal startup
    parser = argparse.ArgumentParser(
        description='Bandit - a Python source code security analyzer',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'targets', metavar='targets', type=str, nargs='*',
        help='source file(s) or directory(s) to be tested'
    )
    parser.add_argument(
        '-r', '--recursive', dest='recursive',
        action='store_true', help='find and process files in subdirectories'
    )
    parser.add_argument(
        '-a', '--aggregate', dest='agg_type',
        action='store', default='file', type=str,
        choices=['file', 'vuln'],
        help='aggregate output by vulnerability (default) or by filename'
    )
    parser.add_argument(
        '-n', '--number', dest='context_lines',
        action='store', default=3, type=int,
        help='maximum number of code lines to output for each issue'
    )
    parser.add_argument(
        '-c', '--configfile', dest='config_file',
        action='store', default=None, type=str,
        help='optional config file to use for selecting plugins and '
             'overriding defaults'
    )
    parser.add_argument(
        '-p', '--profile', dest='profile',
        action='store', default=None, type=str,
        help='profile to use (defaults to executing all tests)'
    )
    parser.add_argument(
        '-t', '--tests', dest='tests',
        action='store', default=None, type=str,
        help='comma-separated list of test IDs to run'
    )
    parser.add_argument(
        '-s', '--skip', dest='skips',
        action='store', default=None, type=str,
        help='comma-separated list of test IDs to skip'
    )
    parser.add_argument(
        '-l', '--level', dest='severity', action='count',
        default=1, help='report only issues of a given severity level or '
                        'higher (-l for LOW, -ll for MEDIUM, -lll for HIGH)'
    )
    parser.add_argument(
        '-i', '--confidence', dest='confidence', action='count',
        default=1, help='report only issues of a given confidence level or '
                        'higher (-i for LOW, -ii for MEDIUM, -iii for HIGH)'
    )
    output_format = 'screen' if sys.stdout.isatty() else 'txt'
    # Instead of specifying a default here, we check if the
    # argument list is empty and then attach the default
    # Python Issue 16399
    parser.add_argument(
        '-f', '--format', dest='output_format', action='append',
        choices=sorted(extension_mgr.formatter_names),
        help='specify output format, can be specified '
             'multiple times to output multiple '
             'formats'
    )
    parser.add_argument(
        '--msg-template', action='store',
        default=None, help='specify output message template'
                           ' (only usable with --format custom),'
                           ' see CUSTOM FORMAT section'
                           ' for list of available values',
    )
    # Instead of specifying a default here, we check if the
    # argument list is empty and then attach the default
    # Python Issue 16399
    parser.add_argument(
        '-o', '--output', dest='output_file', action='append',
        type=argparse.FileType('w'),
        help='write report to filename, should be used the same number of '
             'times as -f argument. If only 1 format is specified '
             'and no output is specified, then STDOUT will be used '
             'as the default output.'
    )
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        '-v', '--verbose', dest='verbose', action='store_true',
        help='output extra information like excluded and included files'
    )
    parser.add_argument(
        '-d', '--debug', dest='debug', action='store_true',
        help='turn on debug mode'
    )
    group.add_argument(
        '-q', '--quiet', '--silent', dest='quiet', action='store_true',
        help='only show output in the case of an error'
    )
    parser.add_argument(
        '--ignore-nosec', dest='ignore_nosec', action='store_true',
        help='do not skip lines with # nosec comments'
    )
    parser.add_argument(
        '-x', '--exclude', dest='excluded_paths', action='store',
        default=','.join(constants.EXCLUDE),
        help='comma-separated list of paths (glob patterns '
             'supported) to exclude from scan '
             '(note that these are in addition to the excluded '
             'paths provided in the config file) (default: ' +
        ','.join(constants.EXCLUDE) + ')'
    )
    parser.add_argument(
        '-b', '--baseline', dest='baseline', action='store',
        default=None, help='path of a baseline report to compare against '
                           '(only JSON-formatted files are accepted)'
    )
    parser.add_argument(
        '--ini', dest='ini_path', action='store', default=None,
        help='path to a .bandit file that supplies command line arguments'
    )
    parser.add_argument('--exit-zero', action='store_true', dest='exit_zero',
                        default=False, help='exit with 0, '
                                            'even with results found')
    python_ver = sys.version.replace('\n', '')
    parser.add_argument(
        '--version', action='version',
        version='%(prog)s {version}\n  python version = {python}'.format(
            version=bandit.__version__, python=python_ver)
    )

    parser.set_defaults(debug=False)
    parser.set_defaults(verbose=False)
    parser.set_defaults(quiet=False)
    parser.set_defaults(ignore_nosec=False)

    plugin_info = ["%s\t%s" % (a[0], a[1].name) for a in
                   extension_mgr.plugins_by_id.items()]
    blacklist_info = []
    for a in extension_mgr.blacklist.items():
        for b in a[1]:
            blacklist_info.append('%s\t%s' % (b['id'], b['name']))

    plugin_list = '\n\t'.join(sorted(set(plugin_info + blacklist_info)))
    dedent_text = textwrap.dedent('''
    CUSTOM FORMATTING
    -----------------

    Available tags:

        {abspath}, {relpath}, {line},  {test_id},
        {severity}, {msg}, {confidence}, {range}

    Example usage:

        Default template:
        bandit -r examples/ --format custom --msg-template \\
        "{abspath}:{line}: {test_id}[bandit]: {severity}: {msg}"

        Provides same output as:
        bandit -r examples/ --format custom

        Tags can also be formatted in python string.format() style:
        bandit -r examples/ --format custom --msg-template \\
        "{relpath:20.20s}: {line:03}: {test_id:^8}: DEFECT: {msg:>20}"

        See python documentation for more information about formatting style:
        https://docs.python.org/3/library/string.html

    The following tests were discovered and loaded:
    -----------------------------------------------
    ''')
    parser.epilog = dedent_text + "\t{0}".format(plugin_list)

    # setup work - parse arguments, and initialize BanditManager
    args = parser.parse_args()

    # Assign our default, if no argument was specified
    if args.output_format is None or len(args.output_format) == 0:
        args.output_format = [output_format]

    # Assign our default, if no argument was specified
    if args.output_file is None or len(args.output_file) == 0:
        args.output_file = [sys.stdout]

    # Before we error check, check if screen was specified and if
    # there was no stdout specified
    if any(f == 'screen' for f in args.output_format) \
            and all(o != sys.stdout for o in args.output_file):
        # Lets specify stdout for the screen format
        # We'll remove all instances of screen, and insert it back in
        # Screen should only be specified once, so we don't care if
        # we remove duplicates
        args.output_format = list(filter(
            lambda f: f != 'screen', args.output_format))

        # Now append both screen and stdout to the end
        args.output_format.append('screen')
        args.output_file.append(sys.stdout)

    # Ensure we have the same number of formats and outputs. If we don't
    # then error
    if len(args.output_format) != len(args.output_file):
        LOG.warning('You must specify an output for each format. '
                    'formats: ' + str(args.output_format)
                    + ' outputs: ' + str(args.output_file))
        sys.exit(2)

    # Check if `--msg-template` is not present without custom formatter
    if 'custom' not in args.output_format and args.msg_template is not None:
        parser.error("--msg-template can only be used with --format=custom")

    try:
        b_conf = b_config.BanditConfig(config_file=args.config_file)
    except utils.ConfigError as e:
        LOG.error(e)
        sys.exit(2)

    # Handle .bandit files in projects to pass cmdline args from file
    ini_options = _get_options_from_ini(args.ini_path, args.targets)
    if ini_options:
        # prefer command line, then ini file
        args.excluded_paths = _log_option_source(
            args.excluded_paths,
            ini_options.get('exclude'),
            'excluded paths')

        args.skips = _log_option_source(
            args.skips,
            ini_options.get('skips'),
            'skipped tests')

        args.tests = _log_option_source(
            args.tests,
            ini_options.get('tests'),
            'selected tests')

        ini_targets = ini_options.get('targets')
        if ini_targets:
            ini_targets = ini_targets.split(',')

        args.targets = _log_option_source(
            args.targets,
            ini_targets,
            'selected targets')

        # TODO(tmcpeak): any other useful options to pass from .bandit?

        args.recursive = _log_option_source(
            args.recursive,
            ini_options.get('recursive'),
            'recursive scan')

        args.agg_type = _log_option_source(
            args.agg_type,
            ini_options.get('aggregate'),
            'aggregate output type')

        args.context_lines = _log_option_source(
            args.context_lines,
            ini_options.get('number'),
            'max code lines output for issue')

        args.profile = _log_option_source(
            args.profile,
            ini_options.get('profile'),
            'profile')

        args.severity = _log_option_source(
            args.severity,
            ini_options.get('level'),
            'severity level')

        args.confidence = _log_option_source(
            args.confidence,
            ini_options.get('confidence'),
            'confidence level')

        args.output_format = _log_option_source(
            args.output_format,
            ini_options.get('format'),
            'output format')

        args.msg_template = _log_option_source(
            args.msg_template,
            ini_options.get('msg-template'),
            'output message template')

        args.output_file = _log_option_source(
            args.output_file,
            ini_options.get('output'),
            'output file')

        args.verbose = _log_option_source(
            args.verbose,
            ini_options.get('verbose'),
            'output extra information')

        args.debug = _log_option_source(
            args.debug,
            ini_options.get('debug'),
            'debug mode')

        args.quiet = _log_option_source(
            args.quiet,
            ini_options.get('quiet'),
            'silent mode')

        args.ignore_nosec = _log_option_source(
            args.ignore_nosec,
            ini_options.get('ignore-nosec'),
            'do not skip lines with # nosec')

        args.baseline = _log_option_source(
            args.baseline,
            ini_options.get('baseline'),
            'path of a baseline report')

    if not args.targets:
        LOG.error("No targets found in CLI or ini files, exiting.")
        sys.exit(2)
    # if the log format string was set in the options, reinitialize
    if b_conf.get_option('log_format'):
        log_format = b_conf.get_option('log_format')
        _init_logger(log_level=logging.DEBUG, log_format=log_format)

    if args.quiet:
        _init_logger(log_level=logging.WARN)

    try:
        profile = _get_profile(b_conf, args.profile, args.config_file)
        _log_info(args, profile)

        profile['include'].update(args.tests.split(',') if args.tests else [])
        profile['exclude'].update(args.skips.split(',') if args.skips else [])
        extension_mgr.validate_profile(profile)

    except (utils.ProfileNotFound, ValueError) as e:
        LOG.error(e)
        sys.exit(2)

    b_mgr = b_manager.BanditManager(b_conf, args.agg_type, args.debug,
                                    profile=profile, verbose=args.verbose,
                                    quiet=args.quiet,
                                    ignore_nosec=args.ignore_nosec)

    if args.baseline is not None:
        try:
            with open(args.baseline) as bl:
                data = bl.read()
                b_mgr.populate_baseline(data)
        except IOError:
            LOG.warning("Could not open baseline report: %s", args.baseline)
            sys.exit(2)

        if any(x not in baseline_formatters for x in args.output_format):
            LOG.warning('Baseline must be used with one of the following '
                        'formats: ' + str(baseline_formatters))
            sys.exit(2)

    if "json" not in args.output_format:
        if args.config_file:
            LOG.info("using config: %s", args.config_file)

        LOG.info("running on Python %d.%d.%d", sys.version_info.major,
                 sys.version_info.minor, sys.version_info.micro)

    # initiate file discovery step within Bandit Manager
    b_mgr.discover_files(args.targets, args.recursive, args.excluded_paths)

    if not b_mgr.b_ts.tests:
        LOG.error('No tests would be run, please check the profile.')
        sys.exit(2)

    # initiate execution of tests within Bandit Manager
    b_mgr.run_tests()
    LOG.debug(b_mgr.b_ma)
    LOG.debug(b_mgr.metrics)

    # trigger output of results by Bandit Manager
    sev_level = constants.RANKING[args.severity - 1]
    conf_level = constants.RANKING[args.confidence - 1]

    # The following will always be true:
    # len(args.output_format) == len(args.output_file)
    # Loop through each format and output, and report the result
    for i in range(len(args.output_format)):
        out_format = args.output_format[i]
        out_file = args.output_file[i]

        b_mgr.output_results(args.context_lines,
                             sev_level,
                             conf_level,
                             out_file,
                             out_format,
                             args.msg_template if out_format == 'custom'
                             else None)

    if (b_mgr.results_count(sev_filter=sev_level, conf_filter=conf_level) > 0
            and not args.exit_zero):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
