#!/usr/bin/env python3

#  Copyright (C) 2024 The Android Open Source Project
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""CLI uploader for Mobly test results to Resultstore."""

import argparse
import dataclasses
import datetime
import logging
import os
import pathlib
import platform
import shutil
import tempfile
from xml.etree import ElementTree

import google.auth
from google.cloud import storage
from google.cloud.storage import transfer_manager
from googleapiclient import discovery

import mobly_result_converter
import resultstore_client

_RESULTSTORE_SERVICE_NAME = 'resultstore'
_API_VERSION = 'v2'
_DISCOVERY_SERVICE_URL = (
    'https://{api}.googleapis.com/$discovery/rest?version={apiVersion}'
)
_TEST_XML = 'test.xml'
_TEST_LOGS = 'test.log'
_UNDECLARED_OUTPUTS = 'undeclared_outputs/'

_TEST_SUMMARY_YAML = 'test_summary.yaml'
_TEST_LOG_INFO = 'test_log.INFO'

_RUN_IDENTIFIER = 'run_identifier'

_ResultstoreTreeTags = mobly_result_converter.ResultstoreTreeTags
_ResultstoreTreeAttributes = mobly_result_converter.ResultstoreTreeAttributes

_Status = resultstore_client.Status


@dataclasses.dataclass()
class _TestResultInfo:
    """Info from the parsed test summary used for the Resultstore invocation."""

    # Aggregate status of the overall test run.
    status: _Status = _Status.UNKNOWN
    # Target ID for the test.
    target_id: str | None = None


def _convert_results(mobly_dir: str, dest_dir: str) -> _TestResultInfo:
    """Converts Mobly test results into a Resultstore artifacts."""
    test_result_info = _TestResultInfo()
    logging.info('Converting raw Mobly logs into Resultstore artifacts...')
    # Generate the test.xml
    mobly_yaml_path = os.path.join(mobly_dir, _TEST_SUMMARY_YAML)
    if os.path.isfile(mobly_yaml_path):
        test_xml = mobly_result_converter.convert(
            mobly_yaml_path, mobly_dir, mobly_dir
        )
        ElementTree.indent(test_xml)
        test_xml.write(
            os.path.join(dest_dir, _TEST_XML),
            encoding='utf-8',
            xml_declaration=True,
        )
        test_result_info = _get_test_result_info_from_test_xml(test_xml)

    # Copy test_log.INFO to test.log
    test_log_info = os.path.join(mobly_dir, _TEST_LOG_INFO)
    if os.path.isfile(test_log_info):
        shutil.copyfile(test_log_info, os.path.join(dest_dir, _TEST_LOGS))

    # Copy directory to undeclared_outputs/
    shutil.copytree(
        mobly_dir,
        os.path.join(dest_dir, _UNDECLARED_OUTPUTS),
        dirs_exist_ok=True,
    )
    return test_result_info


def _get_test_result_info_from_test_xml(
        test_xml: ElementTree.ElementTree,
) -> _TestResultInfo:
    """Parses a test_xml element into a _TestResultInfo."""
    test_result_info = _TestResultInfo()
    mobly_suite_element = test_xml.getroot().find(
        f'./{_ResultstoreTreeTags.TESTSUITE.value}'
    )
    if mobly_suite_element is None:
        return test_result_info
    # Set aggregate test status
    test_result_info.status = _Status.PASSED
    test_class_elements = mobly_suite_element.findall(
        f'./{_ResultstoreTreeTags.TESTSUITE.value}')
    failures = int(
        mobly_suite_element.get(_ResultstoreTreeAttributes.FAILURES.value)
    )
    errors = int(
        mobly_suite_element.get(_ResultstoreTreeAttributes.ERRORS.value))
    if failures or errors:
        test_result_info.status = _Status.FAILED
    else:
        all_skipped = all([test_case_element.get(
            _ResultstoreTreeAttributes.RESULT.value) == 'skipped' for
                           test_class_element in test_class_elements for
                           test_case_element in test_class_element.findall(
                f'./{_ResultstoreTreeTags.TESTCASE.value}')])
        if all_skipped:
            test_result_info.status = _Status.SKIPPED

    # Set target ID based on test class names and run_identifier property
    test_class_names = [
        test_class_element.get(_ResultstoreTreeAttributes.NAME.value)
        for test_class_element in test_class_elements
    ]
    target_id = '+'.join(test_class_names)
    properties_element = mobly_suite_element.find(
        f'./{_ResultstoreTreeTags.PROPERTIES.value}'
    )
    if properties_element is not None:
        run_identifier = properties_element.find(
            f'./{_ResultstoreTreeTags.PROPERTY.value}'
            f'[@{_ResultstoreTreeAttributes.NAME.value}="{_RUN_IDENTIFIER}"]'
        )
        if run_identifier is not None:
            run_identifier_value = run_identifier.get(
                _ResultstoreTreeAttributes.VALUE.value
            )
            target_id = f'{target_id} ({run_identifier_value})'
    test_result_info.target_id = target_id
    return test_result_info


def _upload_dir_to_gcs(
        src_dir: str, gcs_bucket: str, gcs_dir: str
) -> list[str]:
    """Uploads the given directory to a GCS bucket."""
    bucket_obj = storage.Client().bucket(gcs_bucket)

    glob = pathlib.Path(src_dir).expanduser().rglob('*')
    file_paths = [
        str(path.relative_to(src_dir).as_posix())
        for path in glob
        if path.is_file()
    ]

    logging.info(
        'Uploading %s files from %s to Cloud Storage bucket %s/%s...',
        len(file_paths),
        src_dir,
        gcs_bucket,
        gcs_dir,
    )
    # Ensure that the destination directory has a trailing '/'.
    blob_name_prefix = gcs_dir
    if blob_name_prefix and not blob_name_prefix.endswith('/'):
        blob_name_prefix += '/'

    # If running on Windows, disable multiprocessing for upload.
    worker_type = (
        transfer_manager.THREAD
        if platform.system() == 'Windows'
        else transfer_manager.PROCESS
    )
    results = transfer_manager.upload_many_from_filenames(
        bucket_obj,
        file_paths,
        source_directory=src_dir,
        blob_name_prefix=blob_name_prefix,
        worker_type=worker_type,
    )

    success_paths = []
    for file_name, result in zip(file_paths, results):
        if isinstance(result, Exception):
            logging.warning('Failed to upload %s. Error: %s', file_name, result)
        else:
            logging.debug('Uploaded %s.', file_name)
            success_paths.append(file_name)
    return success_paths


def _upload_to_resultstore(
        gcs_bucket: str,
        gcs_dir: str,
        file_paths: list[str],
        status: _Status,
        target_id: str | None,
) -> None:
    """Uploads test results to Resultstore."""
    logging.info('Generating Resultstore link...')
    service = discovery.build(
        _RESULTSTORE_SERVICE_NAME,
        _API_VERSION,
        discoveryServiceUrl=_DISCOVERY_SERVICE_URL,
    )
    creds, project_id = google.auth.default()
    client = resultstore_client.ResultstoreClient(service, creds, project_id)
    client.create_invocation()
    client.create_default_configuration()
    client.create_target(target_id)
    client.create_configured_target()
    client.create_action(f'gs://{gcs_bucket}/{gcs_dir}', file_paths)
    client.set_status(status)
    client.merge_configured_target()
    client.finalize_configured_target()
    client.merge_target()
    client.finalize_target()
    client.merge_invocation()
    client.finalize_invocation()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-v', '--verbose', action='store_true', help='Enable debug logs.'
    )
    parser.add_argument(
        '--mobly_dir',
        required=True,
        help='Directory on host where Mobly results are stored.',
    )
    parser.add_argument(
        '--gcs_bucket',
        required=True,
        help='Bucket in GCS where test artifacts are uploaded.',
    )
    parser.add_argument(
        '--gcs_dir',
        help=(
            'Directory to save test artifacts in GCS. Specify empty string to '
            'store the files in the bucket root. If unspecified, use the '
            'current timestamp as the GCS directory name.'
        ),
    )
    parser.add_argument('--target_id', help='Custom target ID.')

    args = parser.parse_args()
    logging.basicConfig(level=(logging.DEBUG if args.verbose else logging.INFO))
    gcs_dir_name = (
        datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        if args.gcs_dir is None
        else args.gcs_dir
    )
    with tempfile.TemporaryDirectory() as tmp:
        test_result_info = _convert_results(args.mobly_dir, tmp)
        gcs_files = _upload_dir_to_gcs(tmp, args.gcs_bucket, gcs_dir_name)
    _upload_to_resultstore(
        args.gcs_bucket,
        gcs_dir_name,
        gcs_files,
        test_result_info.status,
        args.target_id or test_result_info.target_id,
    )


if __name__ == '__main__':
    main()
