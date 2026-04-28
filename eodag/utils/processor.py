# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import signal
import threading
import time
from threading import Lock, Thread
from typing import Any, Callable, Optional, Union

logger = logging.getLogger("eodag.utils.processor")


class Processor:
    """Use to run routine paralellized"""

    _initialized: bool = False
    _terminating: bool = False
    _queue: list = []
    _mutex = Lock()
    _task_id: int = 0
    _inprogress: dict[str, Thread] = {}
    _processing = False

    @staticmethod
    def init():
        """Static init, handler main program exit to interrupt process loops and stop subtreads"""
        if isinstance(threading.current_thread(), threading._MainThread):
            if not Processor._initialized:
                Processor._initialized = True

                # Catch end of main process to internal status
                def signal_handler(sig, frame):
                    logger.debug("Processor signal capture #{}".format(sig))
                    if not Processor._terminating:
                        Processor._terminating = True
                        Processor.stop(force=True)

                signal.signal(signal.SIGINT, signal_handler)
                signal.signal(signal.SIGTERM, signal_handler)
                logger.debug("Processor signal listener set")

        return Processor

    @staticmethod
    def is_terminating() -> bool:
        """Return is main program is terminating"""
        return Processor._terminating

    @staticmethod
    def queue(
        routine: Callable,
        *args,
        q_callback: Optional[Callable] = None,
        q_callback_kwargs: Optional[dict[str, Any]] = None,
        q_timeout: int = -1,
        q_parallelize: Optional[int] = None,
        **kwargs
    ) -> int:
        """Add function in todo queue

        :param routine       function to run, with args and kwargs
        :param q_callback    [optinal] function run when routine finished
        :param q_timeout     [optional] time limit of a run (seconds)
        :param q_parallelize [optional] parallelization restriction with this item
        :return taskid
        """

        if Processor._terminating:
            return -1

        if q_callback_kwargs is None:
            q_callback_kwargs = {}

        max_paralellize: int = os.cpu_count() or 1
        if not isinstance(q_parallelize, int):
            q_parallelize = max_paralellize
        q_parallelize = max(min(int(q_parallelize), max_paralellize), 1)

        with Processor._mutex:
            Processor._task_id = (Processor._task_id + 1) % 65536
            taskid = 0 + Processor._task_id

        # Scope of defer routine
        def build_wrapper_routine(id: int) -> Callable:

            # Shared data in wrapper routine
            shared = {"id": id, "complete": False}

            # Routine callback handler
            def wrapped_callback(data, error):

                run_callback = False
                with Processor._mutex:
                    if not shared["complete"]:
                        shared["complete"] = True
                        run_callback = True

                        # Remove queue "inprogress"
                        if shared["id"] in Processor._inprogress:
                            del Processor._inprogress[shared["id"]]
                        else:
                            error = InterruptedError("Process interrupted")

                        # Tag as complete to not trigger again on timeout
                        if error is None:
                            logger.debug(
                                "Processor complete task #{}".format(shared["id"])
                            )
                        else:
                            logger.debug(
                                "Processor complete task #{} with error {}".format(
                                    shared["id"], error.__class__.__name__
                                )
                            )
                if callable(q_callback) and run_callback:
                    q_callback(data, error, **q_callback_kwargs)

            # Only start count timeout when routine starts
            def routine_timeout():
                local_timeout = 0 + q_timeout
                with Processor._mutex:
                    processing = Processor._processing
                while (
                    not Processor._terminating
                    and processing
                    and not shared["complete"]
                    and local_timeout >= 0
                ):
                    local_timeout -= 0.01
                    time.sleep(0.01)
                    with Processor._mutex:
                        processing = Processor._processing

                wrapped_callback(None, TimeoutError("Routine timeout"))

            # Wrap routine/callback + routine ack
            def wrapped_routine(*args, **kwargs):
                result = None
                error = None
                routine_name = "routine"
                try:
                    routine_name = routine.__name__
                except AttributeError:
                    pass

                logger.debug(
                    "Processor start task #{} (func: {})".format(
                        shared["id"], routine_name
                    )
                )
                if q_timeout >= 0:
                    Thread(target=routine_timeout, args=()).start()
                try:
                    result = routine(*args, **kwargs)
                except Exception as e:
                    error = e
                wrapped_callback(result, error)

            return wrapped_routine

        run_process = False
        with Processor._mutex:
            Processor._queue.append(
                {
                    "routine": build_wrapper_routine(taskid),
                    "parallelize": q_parallelize,
                    "id": taskid,
                    "args": args,
                    "kwargs": kwargs,
                }
            )
            if not Processor._processing:
                Processor._processing = True
                run_process = True

        if run_process:
            Thread(target=Processor._process).start()
        return taskid

    @staticmethod
    def _process():
        """Processing loop"""

        with Processor._mutex:
            processing = Processor._processing

        while processing and not Processor._terminating:

            # Identify next items, considering paralellize restriction
            if len(Processor._queue) > 0:

                # Gather new routine to run
                with Processor._mutex:

                    select_queue: list[dict[str, Any]] = []  # type: ignore
                    carry_queue: list[dict[str, Any]] = []  # type: ignore
                    for task in Processor._queue:
                        # Add element in process queue if count of current allow parallize
                        #  process < this task max allow paralellized process
                        if len(Processor._inprogress) < task["parallelize"]:
                            Processor._inprogress[task["id"]] = None
                            select_queue.append(task)
                        else:
                            carry_queue.append(task)

                    # Do not replace Processor._queue reference,
                    # else current routine curring ll be cleared by garbage collector
                    for i in range(0, len(carry_queue)):
                        Processor._queue[i] = carry_queue[i]
                    Processor._queue = Processor._queue[0 : len(carry_queue)]

                # Each routine to strat in a thread
                for item in select_queue:
                    thread = Thread(
                        target=item["routine"], args=item["args"], kwargs=item["kwargs"]
                    )
                    thread.daemon = False
                    Processor._inprogress[task["id"]] = thread
                    thread.start()

            with Processor._mutex:
                if len(Processor._queue) == 0 and len(Processor._inprogress) == 0:
                    Processor._processing = False
                processing = Processor._processing

            time.sleep(0.01)

    @staticmethod
    def stop(force: bool = False):
        """Stop all processes"""
        with Processor._mutex:
            if Processor._processing:
                logger.debug("Processor global interruption")
                Processor._processing = False
                Processor._queue = []
                if force:
                    for key in Processor._inprogress:
                        if isinstance(Processor._inprogress[key], Thread):
                            try:
                                pid = Processor._inprogress[key].native_id
                                if pid is not None:
                                    logger.debug("Force kill pid #{}".format(pid))
                                    os.kill(pid, signal.SIGTERM)
                            except OSError:
                                pass
                Processor._inprogress = {}
        return Processor

    @staticmethod
    def wait(id: Optional[Union[int, list[int]]] = None) -> "Processor":
        """Wait for tasks complete
        :param id            wait after specific one or many ids, wait for all if None
        :return Processor
        """
        processing = True
        while processing and not Processor._terminating:
            with Processor._mutex:
                if id is None:
                    # Wait after all process
                    processing = Processor._processing
                else:

                    # Wait a list of taskid
                    if isinstance(id, int):
                        id = [id]
                    if not isinstance(id, list):
                        return Processor

                    # Wait after process with a id
                    count = 0
                    for idv in id:
                        if isinstance(idv, int) and idv >= 0:
                            for task in Processor._queue:
                                if task["id"] == idv:
                                    count += 1
                            if idv in Processor._inprogress:
                                count += 1
                    processing = count > 0
            if processing:
                time.sleep(0.1)

        return Processor  # type: ignore


Processor.init()
