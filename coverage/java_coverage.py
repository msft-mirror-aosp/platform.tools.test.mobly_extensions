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

import glob
import os
import shutil
import subprocess
import tarfile
import tempfile

from mobly.controllers import android_device
from mobly.coverage import coverage_options
from mobly.coverage import device_utils


_COVERAGE_DIRECTORY = "/data/misc/trace"
_FIND_COVERAGE_FILES = f"find {_COVERAGE_DIRECTORY} -name '*.ec'"
_COMPRESS_COVERAGE_FILES = (
    f"{_FIND_COVERAGE_FILES} | tar -czf - -T - 2>/dev/null"
)


def collect_coverage(
    device: android_device.AndroidDevice,
    options: coverage_options.CoverageOptions,
    output_path: str,
) -> None:
  """Collects Java code coverage from the device.

  Args:
    device: The device to collect coverage from.
    options: The coverage options to use.
    output_path: The path to save the coverage data to.
  """
  try:
    _collect_coverage(device, options, output_path)
  finally:
    _clean_up_device_coverage_files(device)


def _collect_coverage(
    device: android_device.AndroidDevice,
    options: coverage_options.CoverageOptions,
    output_path: str,
) -> None:
  """Collects Java code coverage for a test."""
  if not options.coverage:
    return
  # TODO(b/383557170): Handle merged merged and flushed coverage if requested.
  device.adb.root()
  with tempfile.TemporaryDirectory() as temp_dir:
    coverage_tar_gz = os.path.join(temp_dir, "java_coverage.tar.gz")
    with open(coverage_tar_gz, "wb") as f:
      command = f'adb -s {device.serial} shell "{_COMPRESS_COVERAGE_FILES}"'
      subprocess.run(command, shell=True, stdout=f, timeout=1200, check=True)
    coverage_dir = os.path.join(temp_dir, "java_coverage")
    tarfile.open(coverage_tar_gz, "r:gz").extractall(coverage_dir)
    for filename in glob.glob(f"{coverage_dir}/**/*.ec", recursive=True):
      if not filename.endswith(".ec"):
        continue
      _save_coverage_measurement(filename, output_path)


def _save_coverage_measurement(coverage_file: str, output_path: str) -> None:
  """Saves Java coverage file data."""
  shutil.move(coverage_file, output_path)
  # TODO(b/383557170): Handle merged coverage if requested.


def _clean_up_device_coverage_files(
    device: android_device.AndroidDevice,
) -> None:
  """Cleans up coverage files on the device."""
  processes = device_utils.get_running_processes(device)
  active_pids = [process.pid for process in processes]
  coverage_output = device.adb.shell(_FIND_COVERAGE_FILES).decode()
  for coverage_output_line in coverage_output.split("\n"):
    line = coverage_output_line.strip()
    if not line:
      continue
    if not line.endswith(".mm.ec"):
      device.adb.shell(f"rm {line}", shell=True)
      continue
    pid = int(line[line.index("-") + 1 : line.index(".")])
    if pid not in active_pids:
      device.adb.shell(f"rm {line}", shell=True)
