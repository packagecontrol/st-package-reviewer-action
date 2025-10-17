import re
import tempfile
import os
import shutil
import zipfile
import pathlib
import subprocess
import json

from .package_control.providers import RepositoryProvider
from .package_control.download_manager import downloader, close_all_connections
from .package_control.downloaders.downloader_exception import DownloaderException
from .st_package_reviewer.check import file as file_checkers
from .st_package_reviewer.check.file.check_messages import CheckMessages


DOWNLOADER_SETTINGS = {
    'cache_length': 600,
    'debug': False,
    'timeout': 10,
    'user_agent': 'Package Control Default Channel Server',
    'install_prereleases': True
}


def format_report(report):
    if isinstance(report, str):
        return report

    if report.details:
        return '{}: {}'.format(report.message, ', '.join(report.details))

    return report.message


def run_tests(spec):
    """
    Runs repo tests for a repository

    :param spec:
        A dict of info for a single package, as loaded from a repository JSON file

    :return:

    """

    res, info = fetch_package_metadata(spec)
    if not res:
        print('::error title=FAIL ::{}'.format(info))
        return False

    name = info.get('name')
    if not isinstance(name, str) or '/' in name or '\\' in name:
        print('::error title=NAME ::Invalid package name')
        return False

    success = True
    tmpdir = None
    try:
        if 'sublime' in info['name'].lower():
            print('::error title=NAME ::Package name contains the word Sublime')
            success = False

        if not info['releases']:
            success = False
            if spec['releases']:
                print('::error title=RELEASE ::No releases found, ensure valid semver tags')
            else:
                print('::error title=RELEASE ::No releases found')
        else:
            for release_source in spec['releases']:
                if 'branch' in release_source:
                    print('::error title=RELEASE ::Branch-based releases are deprecated, use tags instead')
                    success = False
                platforms = release_source.get('platforms', [])
                if set(platforms) == {'windows', 'osx', 'linux'} or platforms == ['*']:
                    print('::error title=RELEASE ::All platforms are supported, omit the key')
                    success = False

        if info['readme'] is None:
            print('::error title=README ::No README found')
            success = False

        if not info['releases']:
            return False

        url = info['releases'][0]['url']
        name = info['name']

        if not isinstance(url, str) or not url.startswith('https://'):
            print('::error title=HTTP ::Packages must be served over HTTPS')
            return False

        tmpdir = tempfile.mkdtemp()
        if not tmpdir:
            print('::error title=FAIL ::Could not create temp dir')
            return False

        tmp_package_path = os.path.join(tmpdir, '%s.sublime-package' % name)
        tmp_package_dir = os.path.join(tmpdir, name)
        os.mkdir(tmp_package_dir)
        with open(tmp_package_path, 'wb') as package_file, downloader(url, DOWNLOADER_SETTINGS) as manager:
            try:
                package_file.write(manager.fetch(url, 'fetching package'))
            except DownloaderException as e:
                print('::error title=FAIL ::{}'.format(str(e)))
                return False

        with zipfile.ZipFile(tmp_package_path, 'r') as package_zip:

            # Scan through the root level of the zip file to gather some info
            root_level_paths = []
            last_path = None
            for path in package_zip.namelist():
                if not isinstance(path, str):
                    path = path.decode('utf-8', 'strict')
                path = path.replace('\\', '/')

                last_path = path

                if path.find('/') in [len(path) - 1, -1]:
                    root_level_paths.append(path)
                # Make sure there are no paths that look like security vulnerabilities
                if path[0] == '/' or '../' in path:
                    print('::error title=FAIL ::{} appears to be attempting to access other parts of the filesystem'.format(path))  # noqa: E501
                    return False

            if last_path and len(root_level_paths) == 0:
                root_level_paths.append(last_path[0:last_path.find('/') + 1])

            # If there is only a single directory at the top level, the file
            # is most likely a zip from BitBucket or GitHub and we need
            # to skip the top-level dir when extracting
            skip_root_dir = len(root_level_paths) == 1 and \
                root_level_paths[0].endswith('/')

            for path in package_zip.namelist():
                dest = path
                if not isinstance(dest, str):
                    dest = dest.decode('utf-8', 'strict')
                dest = dest.replace('\\', '/')

                # If there was only a single directory in the package, we remove
                # that folder name from the paths as we extract entries
                if skip_root_dir:
                    dest = dest[len(root_level_paths[0]):]

                dest = os.path.join(tmp_package_dir, dest)

                dest = os.path.abspath(dest)
                # Make sure there are no paths that look like security vulnerabilities
                if not dest.startswith(tmp_package_dir):
                    print('::error title=FAIL ::{} appears to be attempting to access other parts of the filesystem'.format(path))  # noqa: E501
                    return False

                if path.endswith('/'):
                    if not os.path.exists(dest):
                        os.makedirs(dest)
                else:
                    dest_dir = os.path.dirname(dest)
                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir)
                    with open(dest, 'wb') as f:
                        f.write(package_zip.read(path))

            tmp_package_dir_pathlib = pathlib.Path(tmp_package_dir)
            for checker in file_checkers.get_checkers():
                checker_obj = checker(tmp_package_dir_pathlib)
                if checker == CheckMessages:
                    for release_source in spec['releases']:
                        if isinstance(release_source.get('tags'), str):
                            checker_obj.add_prefix(release_source.get('tags'))

                checker_obj.perform_check()
                for failure in checker_obj.failures:
                    print('::error title=CHECK ::{}'.format(format_report(failure)))
                    success = False
                for warning in checker_obj.warnings:
                    print('::warning title=CHECK ::{}'.format(format_report(warning)))

        return success

    finally:
        if tmpdir and os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)


def fetch_package_metadata(spec):
    """
    Pull information about a package using the repository providers

    :param spec:
        A dict of info for a single package, as loaded from a repository JSON file

    :return:
        A two-element tuple, the first being True on success, or False on error.
        If successful, second element is a dict of info. If error, second element
        is a string error message.
    """

    def clean_message(exception):
        error = exception.args[0]
        return error.replace(' in the repository https://example.com', '')

    provider = RepositoryProvider('https://example.com', DOWNLOADER_SETTINGS)
    provider.schema_version = '3.0.0'
    provider.schema_major_version = 3
    provider.repo_info = {'schema_version': '3.0.0', 'packages': [spec], 'dependencies': []}

    try:
        for name, info in provider.get_packages():
            return (True, info)

        if provider.failed_sources:
            source, e = provider.failed_sources.popitem()
            return (False, clean_message(e))

        if provider.broken_packages:
            name, e = provider.broken_packages.popitem()
            return (False, clean_message(e))

    except (Exception) as e:
        return (False, clean_message(e))

    finally:
        close_all_connections()


def run(cmd, cwd=None):
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd
    )
    stdout, _ = proc.communicate()
    stdout = stdout.decode('utf-8').strip()
    returncode = proc.wait()
    return (returncode, stdout)


def package_name(data):
    if 'name' in data:
        return data['name']
    else:
        return os.path.basename(data['details'])


def test_pull_request(old_rev: str, current_rev: str):
    tmpdir = None
    try:
        tmpdir = tempfile.mkdtemp()
        if not tmpdir:
            raise EnvironmentError('Unable to create tmpdir')

        filenames = []
        code, files_changed = run(['git', 'diff', '--name-status', old_rev, current_rev])
        if code != 0:
            return {
                '__status_code__': 500,
                'result': 'error',
                'message': 'Unable to diff %s..%s' % (old_rev, current_rev)
            }

        for line in files_changed.splitlines():
            parts = re.split(r'\s+', line, 1)
            if len(parts) != 2:
                return {
                    '__status_code__': 500,
                    'result': 'error',
                    'message': 'git diff output included a line without status and filename\n\n%s' % files_changed
                }
            status, filename = parts
            if not filename.endswith('.json'):
                continue
            if not re.match(r'repository/(\w|0-9)\.json$', filename) and filename != 'repository.json' \
                    and filename != 'channel.json':
                continue
            if status != 'M':
                return {
                    '__status_code__': 500,
                    'result': 'error',
                    'message': 'Unsure how to test a change that adds or removes a file, aborting'
                }
            filenames.append(filename)

        modified_pkgs = set()
        added_pkgs = set()
        removed_pkgs = set()

        pkg_links = {}

        added_pkg_data = {}

        added_repositories = set()
        removed_repositories = set()

        for filename in filenames:
            code, old_version = run(['git', 'show', '%s:%s' % (old_rev, filename)])
            code, new_version = run(['git', 'show', '%s:%s' % (current_rev, filename)])
            old_json = json.loads(old_version)
            new_json = json.loads(new_version)
            if filename == 'channel.json':
                removed_repositories = set(old_json['repositories']) - set(new_json['repositories'])
                added_repositories = set(new_json['repositories']) - set(old_json['repositories'])
            else:
                old_packages = [json.dumps(p) for p in old_json['packages']]
                new_packages = [json.dumps(p) for p in new_json['packages']]
                deleted = set(old_packages) - set(new_packages)
                added = set(new_packages) - set(old_packages)
                deleted_indexes = [old_packages.index(op) for op in deleted]
                added_indexes = [new_packages.index(np) for np in added]
                if len(deleted_indexes) == len(added_indexes):
                    for index in added_indexes:
                        modified_pkgs.add(package_name(new_json['packages'][index]))
                elif len(deleted_indexes) == 0:
                    for index in added_indexes:
                        pkg_name = package_name(new_json['packages'][index])
                        added_pkgs.add(pkg_name)
                        added_pkg_data[pkg_name] = new_json['packages'][index]
                        if 'details' in added_pkg_data[pkg_name]:
                            pkg_links[pkg_name] = added_pkg_data[pkg_name]['details']
                else:
                    for index in deleted_indexes:
                        removed_pkgs.add(package_name(old_json['packages'][index]))

        success = True

        if removed_repositories:
            print('::notice title=REPO_ADDED ::{}'.format(', '.join(removed_repositories)))

        if added_repositories:
            print('::notice title=REPO_REMOVED ::{}'.format(', '.join(added_repositories)))

        if added_repositories:
            for repo in added_repositories:
                if not repo.startswith('http://') and not repo.startswith('https://'):
                    continue

                if repo.startswith('http://'):
                    success = False
                    print('::error title=HTTP ::Repositories must be served over HTTPS')
                    continue

                with downloader(repo, DOWNLOADER_SETTINGS) as manager:
                    try:
                        raw_data = manager.fetch(repo, 'fetching repository')
                    except DownloaderException as e:
                        success = False
                        print('::error title=FAIL ::%s' % str(e))
                        continue

                try:
                    raw_data = raw_data.decode('utf-8')
                except UnicodeDecodeError:
                    success = False
                    print('::error title=JSON ::Unable to decode JSON as UTF-8')
                    continue
                try:
                    repo_json = json.loads(raw_data)
                except ValueError:
                    success = False
                    print('::error title=JSON ::Unable to parse JSON')
                    continue

                missing_key = False
                for key in ['schema_version', 'packages']:
                    if key not in repo_json:
                        missing_key = True
                        print('::error title=SCHEMA ::Top-level key {} is missing'.format(key))
                        continue

                if missing_key:
                    success = False
                    continue

                if repo_json['schema_version'] != '3.0.0':
                    success = False
                    print('::error title=SCHEMA ::schema_version must be 3.0.0')
                    continue

                for pkg_info in repo_json['packages']:
                    pkg_name = package_name(pkg_info)
                    added_pkgs.add(pkg_name)
                    added_pkg_data[pkg_name] = pkg_info

        if removed_pkgs:
            print('::notice title=REMOVED ::{}'.format(', '.join(removed_pkgs)))

        if modified_pkgs:
            print('::notice title=MODIFIED ::{}'.format(', '.join(modified_pkgs)))

        if added_pkgs:
            print('::notice title=ADDED ::{}'.format(', '.join(added_pkgs)))

        if added_pkgs:
            for name in sorted(added_pkgs):
                data = added_pkg_data[name]
                passes = run_tests(data)
                if passes:
                    print('::notice title=PASS ::{}'.format(name))
                else:
                    success = False
                continue

        if success:
            return (0, 'All good')
        return (1, 'Errors occurred')

    finally:
        if tmpdir and os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)
