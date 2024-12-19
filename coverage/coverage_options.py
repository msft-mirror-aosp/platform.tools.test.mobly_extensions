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

"""Options for controlling code coverage."""

from collections.abc import Sequence
import dataclasses


@dataclasses.dataclass
class CoverageOptions:
  """Options to control code coverage.

  Mirrors
  https://cs.android.com/android/platform/superproject/main/+/main:tools/tradefederation/core/src/com/android/tradefed/testtype/coverage/CoverageOptions.java
  """

  coverage: bool = False
  # TODO(b/383557170): Handle remaining options if requested.
  coverage_flush: bool = False
  coverage_processes: Sequence[str] = dataclasses.field(
      default_factory=lambda: []
  )
  merge_coverage: bool = False
  reset_coverage_before_test: bool = True
  llvm_profdata_path: str | None = None
  profraw_filter: str = ".*\\.profraw"
  pull_timeout: int = 20 * 60 * 1000
  jacocoagent_path: str | None = None
  device_coverage_paths: Sequence[str] = dataclasses.field(
      default_factory=lambda: [
          "/data/misc/trace",
          "/data/local/tmp",
      ]
  )
