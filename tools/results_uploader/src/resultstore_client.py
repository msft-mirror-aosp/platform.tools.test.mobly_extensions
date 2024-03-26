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

"""Resultstore client for Mobly tests."""

import datetime
import logging
import posixpath
import uuid

from google.auth import credentials
import google_auth_httplib2
from googleapiclient import discovery
import httplib2

_DEFAULT_CONFIGURATION = 'default'
_RESULTSTORE_BASE_LINK = 'https://btx.cloud.google.com/invocations'

_STATUS_PASSED = 'PASSED'
_STATUS_FAILED = 'FAILED'
_STATUS_UNKNOWN = 'UNKNOWN'


def _get_status(passed: bool) -> str:
    """Get the corresponding status depending on if the test run passed."""
    return _STATUS_PASSED if passed else _STATUS_FAILED


class ResultstoreClient:
    """Resultstore client for Mobly tests."""

    def __init__(
            self,
            service: discovery.Resource,
            creds: credentials.Credentials,
            project_id: str,
    ):
        """Creates a ResultstoreClient.

        Args:
          service: discovery.Resource object for interacting with the API.
          creds: credentials to add to HTTP request.
          project_id: GCP project ID for Resultstore.
        """
        self._service = service
        self._http = google_auth_httplib2.AuthorizedHttp(
            creds, http=httplib2.Http(timeout=30)
        )
        self._project_id = project_id

        self._request_id = ''
        self._invocation_id = ''
        self._authorization_token = ''
        self._target_id = ''

        self._status = _STATUS_UNKNOWN

    def set_status(self, passed: bool) -> None:
        """Sets the status depending on if the test run passed."""
        self._status = _get_status(passed)

    def create_invocation(self) -> str:
        """Creates an invocation.

        Returns:
          The invocation ID.
        """
        logging.info('creating invocation...')
        if self._invocation_id:
            logging.warning(
                'invocation %s already exists, skipping creation...',
                self._invocation_id,
            )
            return None
        invocation = {
            'timing': {
                'startTime': datetime.datetime.utcnow().isoformat() + 'Z'},
            'invocationAttributes': {'projectId': self._project_id},
        }
        self._request_id = str(uuid.uuid4())
        self._invocation_id = str(uuid.uuid4())
        self._authorization_token = str(uuid.uuid4())
        request = self._service.invocations().create(
            body=invocation,
            requestId=self._request_id,
            invocationId=self._invocation_id,
            authorizationToken=self._authorization_token,
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.create: %s', res)
        return self._invocation_id

    def create_default_configuration(self) -> None:
        """Creates a default configuration."""
        logging.info('creating default configuration...')
        configuration = {
            'id': {
                'invocationId': self._invocation_id,
                'configurationId': _DEFAULT_CONFIGURATION,
            }
        }
        request = (
            self._service.invocations()
            .configs()
            .create(
                body=configuration,
                parent=f'invocations/{self._invocation_id}',
                configId=_DEFAULT_CONFIGURATION,
                authorizationToken=self._authorization_token,
            )
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.configs.create: %s', res)

    def create_target(self, target_id: str | None = None) -> str:
        """Creates a target.

        Args:
          target_id: An optional custom target ID.

        Returns:
          The target ID.
        """
        parent = f'invocations/{self._invocation_id}'
        logging.info('creating target in %s...', parent)
        if self._target_id:
            logging.warning(
                'target %s already exists, skipping creation...',
                self._target_id,
            )
            return
        self._target_id = target_id or str(uuid.uuid4())
        target = {
            'id': {
                'invocationId': self._invocation_id,
                'targetId': self._target_id,
            },
            'targetAttributes': {'type': 'TEST', 'language': 'PY'},
        }
        request = (
            self._service.invocations()
            .targets()
            .create(
                body=target,
                parent=parent,
                targetId=self._target_id,
                authorizationToken=self._authorization_token,
            )
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.targets.create: %s', res)
        return self._target_id

    def create_configured_target(self) -> None:
        """Creates a configured target."""
        parent = f'invocations/{self._invocation_id}/targets/{self._target_id}'
        logging.info('creating configured target in %s...', parent)
        configured_target = {
            'id': {
                'invocationId': self._invocation_id,
                'targetId': self._target_id,
                'configurationId': _DEFAULT_CONFIGURATION,
            },
        }
        request = (
            self._service.invocations()
            .targets()
            .configuredTargets()
            .create(
                body=configured_target,
                parent=parent,
                configId=_DEFAULT_CONFIGURATION,
                authorizationToken=self._authorization_token,
            )
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.targets.configuredTargets.create: %s', res)

    def create_action(self, gcs_path: str, artifacts: list[str]) -> str:
        """Creates an action.

        Args:
          gcs_path: The directory in GCS where artifacts are stored.
          artifacts: List of paths (relative to gcs_path) to the test artifacts.

        Returns:
          The action ID.
        """
        parent = (
            f'invocations/{self._invocation_id}/targets/{self._target_id}/'
            'configuredTargets/default'
        )
        logging.info('creating action in %s...', parent)
        action_id = str(uuid.uuid4())
        files = [
            {'uid': path, 'uri': posixpath.join(gcs_path, path)}
            for path in artifacts
        ]
        action = {
            'id': {
                'invocationId': self._invocation_id,
                'targetId': self._target_id,
                'configurationId': _DEFAULT_CONFIGURATION,
                'actionId': action_id,
            },
            'testAction': {},
            'files': files,
        }
        request = (
            self._service.invocations()
            .targets()
            .configuredTargets()
            .actions()
            .create(
                body=action,
                parent=parent,
                actionId=action_id,
                authorizationToken=self._authorization_token,
            )
        )
        res = request.execute(http=self._http)
        logging.debug(
            'invocations.targets.configuredTargets.actions.create: %s', res
        )
        return action_id

    def merge_configured_target(self):
        """Merges a configured target."""
        name = (
            f'invocations/{self._invocation_id}/targets/{self._target_id}/'
            'configuredTargets/default'
        )
        logging.info('merging configured target %s...', name)
        merge_request = {
            'configuredTarget': {
                'statusAttributes': {'status': self._status},
            },
            'authorizationToken': self._authorization_token,
            'updateMask': 'statusAttributes',
        }
        request = (
            self._service.invocations()
            .targets()
            .configuredTargets()
            .merge(
                body=merge_request,
                name=name,
            )
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.targets.configuredTargets.merge: %s', res)

    def finalize_configured_target(self):
        """Finalizes a configured target."""
        name = (
            f'invocations/{self._invocation_id}/targets/{self._target_id}/'
            'configuredTargets/default'
        )
        logging.info('finalizing configured target %s...', name)
        finalize_request = {
            'authorizationToken': self._authorization_token,
        }
        request = (
            self._service.invocations()
            .targets()
            .configuredTargets()
            .finalize(
                body=finalize_request,
                name=name,
            )
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.targets.configuredTargets.finalize: %s', res)

    def merge_target(self):
        """Merges a target."""
        name = f'invocations/{self._invocation_id}/targets/{self._target_id}'
        logging.info('merging target %s...', name)
        merge_request = {
            'target': {
                'statusAttributes': {'status': self._status},
            },
            'authorizationToken': self._authorization_token,
            'updateMask': 'statusAttributes',
        }
        request = (
            self._service.invocations()
            .targets()
            .merge(
                body=merge_request,
                name=name,
            )
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.targets.merge: %s', res)

    def finalize_target(self):
        """Finalizes a target."""
        name = f'invocations/{self._invocation_id}/targets/{self._target_id}'
        logging.info('finalizing target %s...', name)
        finalize_request = {
            'authorizationToken': self._authorization_token,
        }
        request = (
            self._service.invocations()
            .targets()
            .finalize(
                body=finalize_request,
                name=(
                    f'invocations/{self._invocation_id}/targets/'
                    f'{self._target_id}'
                ),
            )
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.targets.finalize: %s', res)
        self._target_id = ''

    def merge_invocation(self):
        """Merges an invocation."""
        name = f'invocations/{self._invocation_id}'
        logging.info('merging invocation %s...', name)
        merge_request = {
            'invocation': {'statusAttributes': {'status': self._status}},
            'updateMask': 'statusAttributes',
            'authorizationToken': self._authorization_token,
        }
        request = self._service.invocations().merge(body=merge_request,
                                                    name=name)
        res = request.execute(http=self._http)
        logging.debug('invocations.merge: %s', res)

    def finalize_invocation(self):
        """Finalizes an invocation."""
        name = f'invocations/{self._invocation_id}'
        logging.info('finalizing invocation %s...', name)
        finalize_request = {
            'authorizationToken': self._authorization_token,
        }
        request = self._service.invocations().finalize(
            body=finalize_request, name=name
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.finalize: %s', res)
        logging.info(
            '----------\nresultstore link is %s/%s',
            _RESULTSTORE_BASE_LINK,
            self._invocation_id,
        )
        self._request_id = ''
        self._invocation_id = ''
        self._authorization_token = ''
