#!/usr/bin/env python3

# Copyright (C) 2023 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility for accessing aconfig and device_config flag values on a device."""

import os
import tempfile
from typing import Any, Dict, Optional

from google.protobuf import text_format
from mobly.controllers import android_device
from protos import aconfig_pb2

_ACONFIG_PARTITIONS = ('product', 'system', 'system_ext', 'vendor')
_ACONFIG_TEXTPROTO_FILE = 'aconfig_flags.textproto'

_DEVICE_CONFIG_GET_CMD = 'device_config get'

_READ_ONLY = aconfig_pb2.flag_permission.READ_ONLY
_ENABLED = aconfig_pb2.flag_state.ENABLED

class DeviceFlags:
    """Provides access to aconfig and device_config flag values of a device."""

    def __init__(self, ad: android_device.AndroidDevice):
        self._ad = ad
        self._aconfig_flags = None

    def get_value(self, namespace: str, name: str) -> Optional[str]:
        """Gets the value of the requested flag.

        Flags must be specified by both its namespace and name.

        The method will first look for the flag from the device's
        aconfig_flags.textproto files, and, if not found or the flag is
        READ_WRITE, then retrieve the value from 'adb device_config get'.

        All values are returned as strings, e.g. 'true', '3'.

        Args:
            namespace: The namespace of the flag.
            name: The full name of the flag.
                For aconfig flags, it is equivalent to '{package}.{name}' from
                    the aconfig proto.
                For device_config flags, it is equivalent to '{KEY}' from the
                    "device_config shell" command.

        Returns:
            The flag value as a string.
        """
        # Check aconfig
        aconfig_val = None
        aconfig_flag = self._get_aconfig_flags().get(
            '%s/%s' % (namespace, name))
        if aconfig_flag is not None:
            aconfig_val = 'true' if aconfig_flag.state == _ENABLED else 'false'
            if aconfig_flag.permission == _READ_ONLY:
                return aconfig_val

        # If missing or READ_WRITE, also check device_config
        device_config_val = self._ad.adb.shell(
            '%s %s %s' % (_DEVICE_CONFIG_GET_CMD, namespace, name)
        ).decode('utf8').strip()
        return device_config_val if device_config_val != 'null' else aconfig_val

    def get_bool(self, namespace: str, name: str) -> bool:
        """Gets the value of the requested flag as a boolean.

        See get_value() for details.

        Args:
            namespace: The namespace of the flag.
            name: The key of the flag.

        Returns:
            The flag value as a boolean.

        Raises:
            ValueError if the flag value cannot be expressed as a boolean.
        """
        val = self.get_value(namespace, name)
        if val.lower() == 'true':
            return True
        if val.lower() == 'false':
            return False
        raise ValueError('Flag %s/%s is not a boolean (value: %s).'
                         % (namespace, name, val))

    def _get_aconfig_flags(self) -> Dict[str, Any]:
        """Gets the aconfig flags as a dict. Loads from proto if necessary."""
        if self._aconfig_flags is None:
            self._load_aconfig_flags()
        return self._aconfig_flags

    def _load_aconfig_flags(self) -> None:
        """Pull aconfig proto files from device, then load the flag info."""
        self._aconfig_flags = {}
        with tempfile.TemporaryDirectory() as tmp_dir:
            for partition in _ACONFIG_PARTITIONS:
                device_path = os.path.join(
                    '/', partition, 'etc', _ACONFIG_TEXTPROTO_FILE)
                host_path = os.path.join(
                    tmp_dir, '%s_%s' % (partition, _ACONFIG_TEXTPROTO_FILE))
                self._ad.adb.pull([device_path, host_path])
                with open(host_path) as f:
                    parsed_flags = text_format.Parse(
                        f.read(), aconfig_pb2.parsed_flags())
                for flag in parsed_flags.parsed_flag:
                    full_name = '%s/%s.%s' % (
                        flag.namespace, flag.package, flag.name)
                    self._aconfig_flags[full_name] = flag
