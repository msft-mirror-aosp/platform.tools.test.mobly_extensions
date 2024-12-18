#!/usr/bin/env python3

# Copyright (C) 2024 The Android Open Source Project
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

import unittest
from unittest import mock

from mobly.controllers import android_device

from mobly.coverage import device_utils


_PS_E_OUTPUT = """USER           PID  PPID        VSZ    RSS WCHAN            ADDR S NAME
root             1     0   10929596   4136 0                   0 S init
root             2     0          0      0 0                   0 S [kthreadd]
root             3     2          0      0 0                   0 I [rcu_gp]
"""

_LIST_PACKAGES_OUTPUT = """package:com.android.systemui.auto_generated_rro_vendor__
package:com.google.android.retaildemo
package:com.clozemaster.v2
package:com.google.android.overlay.googlewebview
"""


def _create_mock_android_device(shell_output: str):
  device = mock.create_autospec(
      android_device.AndroidDevice, instance=True, spec_set=False
  )
  mock_adb = mock.Mock()
  device.adb = mock_adb
  mock_adb.shell.return_value = shell_output.encode("utf-8")
  return device


class DeviceUtilsTest(unittest.TestCase):

  def test_get_all_packages(self):
    device = _create_mock_android_device(_LIST_PACKAGES_OUTPUT)
    self.assertEqual(
        device_utils.get_all_packages(device),
        [
            "com.android.systemui.auto_generated_rro_vendor__",
            "com.google.android.retaildemo",
            "com.clozemaster.v2",
            "com.google.android.overlay.googlewebview",
        ],
    )

  def test_get_running_processes(self):
    device = _create_mock_android_device(_PS_E_OUTPUT)
    self.assertEqual(
        device_utils.get_running_processes(device),
        [
            device_utils.ProcessInfo("root", "init", 1),
            device_utils.ProcessInfo("root", "[kthreadd]", 2),
            device_utils.ProcessInfo("root", "[rcu_gp]", 3),
        ],
    )


if __name__ == "__main__":
  unittest.main()
