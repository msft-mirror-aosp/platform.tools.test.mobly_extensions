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
import enum
import logging
import posixpath
import urllib.parse
import uuid

from google.auth import credentials
import google_auth_httplib2
from googleapiclient import discovery
import httplib2

_DEFAULT_CONFIGURATION = 'default'
_RESULTSTORE_BASE_LINK = 'https://btx.cloud.google.com/invocations'


class Status(enum.Enum):
    """Aggregate status of the Resultstore invocation and target."""
    PASSED = 'PASSED'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'
    UNKNOWN = 'UNKNOWN'


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
        self._encoded_target_id = ''

        self._status = Status.UNKNOWN

    @property
    def _invocation_name(self):
        """The resource name for the invocation."""
        if not self._invocation_id:
            return ''
        return f'invocations/{self._invocation_id}'

    @property
    def _target_name(self):
        """The resource name for the target."""
        if not (self._invocation_name or self._encoded_target_id):
            return ''
        return f'{self._invocation_name}/targets/{self._encoded_target_id}'

    @property
    def _configured_target_name(self):
        """The resource name for the configured target."""
        if not self._target_name:
            return
        return f'{self._target_name}/configuredTargets/{_DEFAULT_CONFIGURATION}'

    def set_status(self, status: Status) -> None:
        """Sets the overall test run status."""
        self._status = status

    def create_invocation(self) -> str:
        """Creates an invocation.

        Returns:
          The invocation ID.
        """
        logging.debug('creating invocation...')
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
        logging.debug('creating default configuration...')
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
        logging.debug('creating target in %s...', self._invocation_name)
        if self._target_id:
            logging.warning(
                'target %s already exists, skipping creation...',
                self._target_id,
            )
            return
        self._target_id = target_id or str(uuid.uuid4())
        self._encoded_target_id = urllib.parse.quote(self._target_id, safe='')
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
                parent=self._invocation_name,
                targetId=self._target_id,
                authorizationToken=self._authorization_token,
            )
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.targets.create: %s', res)
        return self._target_id

    def create_configured_target(self) -> None:
        """Creates a configured target."""
        logging.debug('creating configured target in %s...', self._target_name)
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
                parent=self._target_name,
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
        logging.debug('creating action in %s...', self._configured_target_name)
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
                parent=self._configured_target_name,
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
        logging.debug('merging configured target %s...',
                      self._configured_target_name)
        merge_request = {
            'configuredTarget': {
                'statusAttributes': {'status': self._status.value},
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
                name=self._configured_target_name,
            )
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.targets.configuredTargets.merge: %s', res)

    def finalize_configured_target(self):
        """Finalizes a configured target."""
        logging.debug('finalizing configured target %s...',
                      self._configured_target_name)
        finalize_request = {
            'authorizationToken': self._authorization_token,
        }
        request = (
            self._service.invocations()
            .targets()
            .configuredTargets()
            .finalize(
                body=finalize_request,
                name=self._configured_target_name,
            )
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.targets.configuredTargets.finalize: %s', res)

    def merge_target(self):
        """Merges a target."""
        logging.debug('merging target %s...', self._target_name)
        merge_request = {
            'target': {
                'statusAttributes': {'status': self._status.value},
            },
            'authorizationToken': self._authorization_token,
            'updateMask': 'statusAttributes',
        }
        request = (
            self._service.invocations()
            .targets()
            .merge(
                body=merge_request,
                name=self._target_name,
            )
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.targets.merge: %s', res)

    def finalize_target(self):
        """Finalizes a target."""
        logging.debug('finalizing target %s...', self._target_name)
        finalize_request = {
            'authorizationToken': self._authorization_token,
        }
        request = (
            self._service.invocations()
            .targets()
            .finalize(
                body=finalize_request,
                name=self._target_name,
            )
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.targets.finalize: %s', res)
        self._target_id = ''
        self._encoded_target_id = ''

    def merge_invocation(self):
        """Merges an invocation."""
        logging.debug('merging invocation %s...', self._invocation_name)
        merge_request = {
            'invocation': {'statusAttributes': {'status': self._status.value}},
            'updateMask': 'statusAttributes',
            'authorizationToken': self._authorization_token,
        }
        request = self._service.invocations().merge(body=merge_request,
                                                    name=self._invocation_name)
        res = request.execute(http=self._http)
        logging.debug('invocations.merge: %s', res)

    def finalize_invocation(self):
        """Finalizes an invocation."""
        logging.debug('finalizing invocation %s...', self._invocation_name)
        finalize_request = {
            'authorizationToken': self._authorization_token,
        }
        request = self._service.invocations().finalize(
            body=finalize_request, name=self._invocation_name
        )
        res = request.execute(http=self._http)
        logging.debug('invocations.finalize: %s', res)
        print('---------------------')
        print(f'See results in {_RESULTSTORE_BASE_LINK}/{self._invocation_id}')
        self._request_id = ''
        self._invocation_id = ''
        self._authorization_token = ''
