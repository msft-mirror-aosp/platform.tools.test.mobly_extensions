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

"""Helper utilities for coverage."""

from collections.abc import Sequence
import dataclasses
import re

from mobly.controllers import android_device


# Sample output:
# ```
# USER           PID  PPID        VSZ    RSS WCHAN            ADDR S NAME
# root             1     0   10929596   4324 0                   0 S init
# ```
_PS_PATTERN = re.compile(
    r"^\s*(\S+)\s+(\d+)\s+(?:\d+)\s+(?:\d+)\s+(?:\d+)\s+(?:\d+)\s+(?:\d+)\s+(?:\S+)\s+(\S+)\s*$"
)
_PM_PACKAGE_PREFIX = "package:"


@dataclasses.dataclass
class ProcessInfo:
  """Information about a running process."""

  user: str
  name: str
  pid: int


def get_running_processes(
    device: android_device.AndroidDevice,
) -> Sequence[ProcessInfo]:
  """Returns information about all running processes on the device."""
  processes = []
  raw_output = device.adb.shell("ps -e")
  ps_lines = raw_output.decode().split("\n")
  for line in ps_lines:
    match = _PS_PATTERN.match(line)
    if not match:
      continue
    processes.append(
        ProcessInfo(
            user=match.group(1), pid=int(match.group(2)), name=match.group(3)
        )
    )
  return processes


def get_all_packages(device: android_device.AndroidDevice) -> Sequence[str]:
  """Retrieves the names of all installed packages on the device."""
  packages = []
  raw_output = device.adb.shell(["pm", "list", "packages", "-a"])
  output_lines = raw_output.decode().split("\n")
  for line in output_lines:
    line = line.strip()
    if not line:
      continue
    if line.startswith(_PM_PACKAGE_PREFIX):
      packages.append(line[len(_PM_PACKAGE_PREFIX) :])
  return packages
