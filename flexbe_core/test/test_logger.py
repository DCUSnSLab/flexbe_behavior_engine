#!/usr/bin/env python3

# Copyright 2024 Christopher Newport University
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#
#    * Neither the name of the Philipp Schillinger, Team ViGIR, Christopher Newport University nor the names of its
#      contributors may be used to endorse or promote products derived from
#      this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


"""Test FlexBE Exception handling."""
import time
import unittest

import rclpy

from rclpy.executors import MultiThreadedExecutor
from flexbe_core import set_node, EventState, OperatableStateMachine
from flexbe_core.core.exceptions import StateError, StateMachineError, UserDataError
from flexbe_core.proxy import initialize_proxies, shutdown_proxies
from flexbe_core.logger import Logger 

class TestLogger(unittest.TestCase):
    """Test FlexBE Logger handling."""

    test = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setUp(self):
        TestLogger.test += 1
        self.context = rclpy.context.Context()
        rclpy.init(context=self.context)

        self.executor = MultiThreadedExecutor(context=self.context)
        self.node = rclpy.create_node("logger_test_" + str(self.test), context=self.context)
        self.node.get_logger().info(" set up logger test %d (%d) ... " % (self.test, self.context.ok()))
        self.executor.add_node(self.node)
        initialize_proxies(self.node)

    def tearDown(self):
        self.node.get_logger().info(" shutting down logger test %d (%d) ... " % (self.test, self.context.ok()))
        rclpy.spin_once(self.node, executor=self.executor, timeout_sec=0.1)

        self.node.get_logger().info("    shutting down proxies in logger test %d ... " % (self.test))
        shutdown_proxies()
        time.sleep(0.1)

        self.node.get_logger().info("    destroy node in core test %d ... " % (self.test))
        self.node.destroy_node()

        time.sleep(0.1)
        self.executor.shutdown()
        time.sleep(0.1)

        # Kill it with fire to make sure not stray published topics are available
        rclpy.shutdown(context=self.context)
        time.sleep(0.2)

    def test_throttle_logger_one(self):
        self.node.get_logger().info("test_throttle_logger_one ...")
        self.node.declare_parameter("max_throttle_logging_size", 100)
        self.node.declare_parameter("throttle_logging_clear_ratio", 0.25)
        set_node(self.node)  # Update the logger node

        rclpy.spin_once(self.node, executor=self.executor, timeout_sec=1)
        OperatableStateMachine.initialize_ros(self.node)
        node = self.node

        class ThrottleSingleLog(EventState):
            """Local Test state definition."""

            def __init__(self):
                self.initialize_ros(node)
                super().__init__(outcomes=['done'])
                self._trials = Logger.MAX_LAST_LOGGED_SIZE*2 
                Logger.logerr_throttle(0.0, "test")
 
            def execute(self, userdata):
                Logger.logerr_throttle(0.0, "test")
                self._trials -= 1
                if self._trials == 0:
                    return 'done'

        state_instance = ThrottleSingleLog()
        sm = OperatableStateMachine(outcomes=['done'])
        with sm:
            OperatableStateMachine.add('state', state_instance, transitions={'done': 'done'})
        outcome = None 
        self.assertEqual(Logger.MAX_LAST_LOGGED_SIZE, 100)  # default size
        self.assertAlmostEqual(Logger.LAST_LOGGED_CLEARING_RATIO, 0.25)  # default ratio
        self.assertEqual(state_instance._trials, Logger.MAX_LAST_LOGGED_SIZE*2 )
        while outcome is None:
            outcome = sm.execute(None)
            self.assertEqual(len(Logger._last_logged), 1)
        self.assertEqual(outcome, "done")
        self.assertEqual(state_instance._trials, 0 )
 
        self.assertIsNone(sm._last_exception)
        self.node.get_logger().info("test_throttle_logger_one  - OK! ")

    def test_throttle_logger_err_multi(self):
        self.node.get_logger().info("test_throttle_logger_err_multi ...")
        self.node.declare_parameter("max_throttle_logging_size", 200)
        self.node.declare_parameter("throttle_logging_clear_ratio", 0.35)
        set_node(self.node)  # Update the logger node

        rclpy.spin_once(self.node, executor=self.executor, timeout_sec=1)
        OperatableStateMachine.initialize_ros(self.node)
        node = self.node

        class ThrottleMultiLog(EventState):
            """Local Test state definition."""

            def __init__(self):
                self.initialize_ros(node)
                super().__init__(outcomes=['done'])
                self._trials = Logger.MAX_LAST_LOGGED_SIZE*2 
                Logger.logerr_throttle(0.01, f"0_test")
 
            def execute(self, userdata):
                Logger.logerr_throttle(0.01, f"{self._trials}_test")
                self._trials -= 1
                if self._trials == 0:
                    return 'done'

        state_instance = ThrottleMultiLog()
        sm = OperatableStateMachine(outcomes=['done'])
        with sm:
            OperatableStateMachine.add('state', state_instance, transitions={'done': 'done'})
        outcome = None 
        self.assertEqual(Logger.MAX_LAST_LOGGED_SIZE, 200)  # default size
        self.assertAlmostEqual(Logger.LAST_LOGGED_CLEARING_RATIO, 0.35)  # default ratio
        self.assertEqual(state_instance._trials, Logger.MAX_LAST_LOGGED_SIZE*2 )
        while outcome is None:
            outcome = sm.execute(None)
            self.assertTrue(1 < len(Logger._last_logged) <= Logger.MAX_LAST_LOGGED_SIZE)
        self.assertEqual(outcome, "done")
        self.assertEqual(state_instance._trials, 0)

        self.assertIsNone(sm._last_exception)
        self.node.get_logger().info("test_throttle_logger_err_multi  - OK! ")

    def test_throttle_logger_multiple_params(self):
        self.node.get_logger().info("test_throttle_logger_multiple_params ...")
        self.node.declare_parameter("max_throttle_logging_size", 100)
        self.node.declare_parameter("throttle_logging_clear_ratio", 0.7)

        set_node(self.node)  # Update the logger node

        rclpy.spin_once(self.node, executor=self.executor, timeout_sec=1)
        OperatableStateMachine.initialize_ros(self.node)
        node = self.node

        class ThrottleMultiLog(EventState):
            """Local Test state definition."""

            def __init__(self):
                self.initialize_ros(node)
                super().__init__(outcomes=['done'])
                self._trials = Logger.MAX_LAST_LOGGED_SIZE*2 
                Logger.logerr_throttle(0.01, f"0_test")
 
            def execute(self, userdata):
                Logger.logerr(f"{self._trials}_test")
                Logger.logerr_throttle(0.0, f"{self._trials}_test")
                Logger.logwarn_throttle(0.0, f"{self._trials}_test")
                Logger.loginfo_throttle(0.0, f"{self._trials}_test")
                Logger.loghint_throttle(0.0, f"{self._trials}_test")
                self._trials -= 1
                if self._trials == 0:
                    return 'done'

        state_instance = ThrottleMultiLog()
        sm = OperatableStateMachine(outcomes=['done'])
        with sm:
            OperatableStateMachine.add('state', state_instance, transitions={'done': 'done'})
        outcome = None 
        self.assertEqual(state_instance._trials, Logger.MAX_LAST_LOGGED_SIZE*2 )
        self.assertEqual(Logger.MAX_LAST_LOGGED_SIZE, 100)  # parameterized size
        self.assertAlmostEqual(Logger.LAST_LOGGED_CLEARING_RATIO, 0.7)  # parameterized
        while outcome is None:
            outcome = sm.execute(None)
            self.assertTrue(1 < len(Logger._last_logged) <= Logger.MAX_LAST_LOGGED_SIZE)
            rclpy.spin_once(self.node, executor=self.executor, timeout_sec=0.001)
        self.assertEqual(outcome, "done")
        self.assertEqual(state_instance._trials, 0)

        self.assertIsNone(sm._last_exception)
        self.node.get_logger().info("test_throttle_logger_multiple  - OK! ")

    def test_throttle_logger_multiple(self):
        self.node.get_logger().info("test_throttle_logger_multiple_params ...")
        self.node.declare_parameter("max_throttle_logging_size", 120)
        self.node.declare_parameter("throttle_logging_clear_ratio", 0.22)
        set_node(self.node)  # Update the logger node

        rclpy.spin_once(self.node, executor=self.executor, timeout_sec=1)
        OperatableStateMachine.initialize_ros(self.node)
        node = self.node

        class ThrottleMultiLog(EventState):
            """Local Test state definition."""

            def __init__(self):
                self.initialize_ros(node)
                super().__init__(outcomes=['done'])
                self._trials = Logger.MAX_LAST_LOGGED_SIZE*2 
                Logger.logerr_throttle(0.01, f"0_test")
 
            def execute(self, userdata):
                Logger.logerr(f"{self._trials}_test")
                Logger.logerr_throttle(0.0, f"{self._trials}_test")
                Logger.logwarn_throttle(0.0, f"{self._trials}_test")
                Logger.loginfo_throttle(0.0, f"{self._trials}_test")
                Logger.loghint_throttle(0.0, f"{self._trials}_test")
                self._trials -= 1
                if self._trials == 0:
                    return 'done'

        state_instance = ThrottleMultiLog()
        sm = OperatableStateMachine(outcomes=['done'])
        with sm:
            OperatableStateMachine.add('state', state_instance, transitions={'done': 'done'})
        outcome = None 
        self.assertEqual(state_instance._trials, Logger.MAX_LAST_LOGGED_SIZE*2 )
        self.assertEqual(Logger.MAX_LAST_LOGGED_SIZE, 120)  # default size
        self.assertAlmostEqual(Logger.LAST_LOGGED_CLEARING_RATIO, 0.22)  # default ratio
        while outcome is None:
            outcome = sm.execute(None)
            self.assertTrue(1 < len(Logger._last_logged) <= Logger.MAX_LAST_LOGGED_SIZE)
            rclpy.spin_once(self.node, executor=self.executor, timeout_sec=0.001)
        self.assertEqual(outcome, "done")
        self.assertEqual(state_instance._trials, 0)

        self.assertIsNone(sm._last_exception)
        self.node.get_logger().info("test_throttle_logger_multiple_params  - OK! ")

if __name__ == '__main__':
    unittest.main()