# #####################################################################################################################
#  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.                                                 #
#                                                                                                                     #
#  Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance     #
#  with the License. A copy of the License is located at                                                              #
#                                                                                                                     #
#  http://www.apache.org/licenses/LICENSE-2.0                                                                         #
#                                                                                                                     #
#  or in the 'license' file accompanying this file. This file is distributed on an 'AS IS' BASIS, WITHOUT WARRANTIES  #
#  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions     #
#  and limitations under the License.                                                                                 #
# #####################################################################################################################
import logging
import os
import pytest
from shared.logger import get_level, get_logger


@pytest.fixture(scope="function", autouse=True)
def rest_logger():
    if "LOG_LEVEL" in os.environ:
        os.environ.pop("LOG_LEVEL")


@pytest.mark.parametrize("log_level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_get_level(log_level):
    os.environ["LOG_LEVEL"] = log_level
    assert get_level() == log_level


def test_default_level():
    os.environ["LOG_LEVEL"] = "no_supported"
    assert get_level() == "WARNING"


def test_get_level_locally():
    logging.getLogger().handlers = []
    logger = get_logger(__name__)
    assert logger.level == 0
