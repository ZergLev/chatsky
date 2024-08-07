"""
Message Interfaces
------------------
The Message Interfaces module contains several basic classes that define the message interfaces.
These classes provide a way to define the structure of the messengers that are used to communicate with Chatsky.
"""

from __future__ import annotations
import abc
import asyncio
import logging
from pathlib import Path
from tempfile import gettempdir
import signal
from functools import partial
import time  # Don't forget to remove this
import contextlib

from typing import Optional, Any, List, Tuple, Hashable, TYPE_CHECKING, Type

if TYPE_CHECKING:
    from chatsky.script import Context, Message
    from chatsky.pipeline.types import PipelineRunnerFunction
    from chatsky.messengers.common.types import PollingInterfaceLoopFunction
    from chatsky.script.core.message import Attachment
    from chatsky.pipeline.pipeline.pipeline import Pipeline

logger = logging.getLogger(__name__)


class MessengerInterface(abc.ABC):
    """
    Class that represents a message interface used for communication between pipeline and users.
    It is responsible for connection between user and pipeline, as well as for request-response transactions.
    """

    def __init__(self):
        self.task = None
        self.pipeline = None
        self.running_in_foreground = False
        self.running = True
        self.finished_working = False

    @abc.abstractmethod
    async def connect(
        self,
        pipeline_runner: PipelineRunnerFunction,
        loop: PollingInterfaceLoopFunction = lambda: True,
        poll_timeout: float = None,
        worker_timeout: float = None,
        timeout: float = 0,
    ):
        """
        Method invoked when message interface is instantiated and connection is established.
        May be used for sending an introduction message or displaying general bot information.

        :param pipeline_runner: A function that should process user request and return context;
            usually it's a :py:meth:`~chatsky.pipeline.pipeline.pipeline.Pipeline._run_pipeline` function.
        """
        raise NotImplementedError

    async def cleanup(self):
        """
        A placeholder method for any cleanup code you want to be
        called before shutting down the program.
        You can redefine this method in your class.
        Note you need to call cleanup() of the parent class.
        """
        pass

    async def run_in_foreground(
        self,
        pipeline: Pipeline,
        pipeline_runner: PipelineRunnerFunction,
        loop: PollingInterfaceLoopFunction = lambda: True,
        poll_timeout: float = None,
        worker_timeout: float = None,
        timeout: float = 0,
    ):
        self.running_in_foreground = True
        self.pipeline = pipeline

        # Functionally looks about the same as the other option, just not pretty
        def placeholder_func(signum, frame):
            pipeline.sigint_handler(async_loop)

        async_loop = asyncio.get_running_loop()
        signal.signal(signal.SIGINT, placeholder_func)

        """
        # This only works on Linux. Windows should work with 'signal', though.
        async_loop = asyncio.get_running_loop()
        async_loop.add_signal_handler(signal.SIGINT, partial(pipeline.sigint_handler, async_loop))
        """

        # TODO: correctly redefine connect() in all interfaces.
        self.task = asyncio.create_task(
            self.connect(
                pipeline_runner,
                loop=loop,
                poll_timeout=poll_timeout,
                worker_timeout=worker_timeout,
                timeout=timeout,
            )
        )

        try:
            await self.task
        except asyncio.CancelledError:
            # Making sure shutdown() has control during cancellation.
            await asyncio.sleep(0)
        finally:
            await self.cleanup()

        self.finished_working = True

    async def shutdown(self):
        """
        Right now, this cancels the main task (if it hasn't finished) and sets a flag self.running to False,
        so that any async tasks in loops can see that and turn off as soon as they are done.
        """
        logger.info(f"messenger_interface.shutdown() called - shutting down interface")
        self.running = False
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            # Awaiting self.task() throws an exception, but if the main task
            # of this interface has finished through any means (like a loop() function running out of loops),
            # the exception would break the program (nothing is there to catch it anymore),
            # so instead the exception will be caught and nothing will happen.
            if not self.finished_working:
                raise asyncio.CancelledError
        logger.info(f"{type(self).__name__} has stopped working - SIGINT received")


class MessengerInterfaceWithAttachments(MessengerInterface, abc.ABC):
    """
    MessengerInterface subclass that has methods for attachment handling.

    :param attachments_directory: Directory where attachments will be stored.
        If not specified, the temporary directory will be used.
    """

    supported_request_attachment_types: set[Type[Attachment]] = set()
    """
    Types of attachment that this messenger interface can receive.
    Attachments not in this list will be neglected.
    """

    supported_response_attachment_types: set[Type[Attachment]] = set()
    """
    Types of attachment that this messenger interface can send.
    Attachments not in this list will be neglected.
    """

    def __init__(self, attachments_directory: Optional[Path] = None) -> None:
        tempdir = gettempdir()
        if attachments_directory is not None and not str(attachments_directory.absolute()).startswith(tempdir):
            self.attachments_directory = attachments_directory
        else:
            warning_start = f"Attachments directory for {type(self).__name__} messenger interface"
            warning_end = "attachment data won't be cached locally!"
            if attachments_directory is None:
                self.attachments_directory = Path(tempdir) / f"chatsky-cache-{type(self).__name__}"
                logger.info(f"{warning_start} is None, so will be set to tempdir and {warning_end}")
            else:
                self.attachments_directory = attachments_directory
                logger.info(f"{warning_start} is in tempdir, so {warning_end}")
        self.attachments_directory.mkdir(parents=True, exist_ok=True)

    @abc.abstractmethod
    async def get_attachment_bytes(self, source: str) -> bytes:
        """
        Get attachment bytes from file source.

        E.g. if a file attachment consists of a URL of the file uploaded to the messenger servers,
        this method is the right place to call the messenger API for the file downloading.

        :param source: Identifying string for the file.
        :return: The attachment bytes.
        """
        raise NotImplementedError


class PollingMessengerInterface(MessengerInterface):
    """
    Polling message interface runs in a loop, constantly asking users for a new input.
    """

    def __init__(self, number_of_workers: int = 2):
        self.request_queue = asyncio.Queue()
        self.number_of_workers = number_of_workers
        self._worker_tasks = []
        super().__init__()

    @abc.abstractmethod
    async def _respond(self, ctx_id, last_response):
        """
        Method used for sending users responses for their last input.

        :param ctx_id: Context id, specifies the user id. Without multiple messenger interfaces it's basically a redundant parameter, because this function is just a more complex `print(last_response)`. (Change before merge)
        :param last_response: Latest response from the pipeline which should be relayed to the specified user.
        """
        raise NotImplementedError

    async def _process_request(self, ctx_id, update: Message, pipeline: Pipeline):
        """
        Process a new update for ctx.
        """
        context = await pipeline._run_pipeline(update, ctx_id)
        await self._respond(ctx_id, context.last_response)

    async def _worker_job(self, worker_timeout: float):
        """
        Obtain Lock over the current context,
        Process the update and send it.
        """
        request = await self.request_queue.get()
        if request is not None:
            (ctx_id, update) = request
            async with self.pipeline.context_lock[ctx_id]:  # get exclusive access to this context among interfaces
                # Trying to see if _process_request works at all. Looks like it does it just fine, actually
                # await self._process_request(ctx_id, update, self.pipeline)
                # Doesn't work in a thread for some reason - it goes into an infinite cycle.
                # """
                await asyncio.wait_for(
                    await asyncio.to_thread(  # [optional] execute in a separate thread to avoid blocking
                        self._process_request, ctx_id, update, self.pipeline
                    ),
                    timeout=worker_timeout,
                )
                # """
            return False
        else:
            return True

    # This worker doesn't save the request and basically deletes it from the queue in case it can't process it.
    # An option to save the request may be fitting? Maybe with an amount of retries.
    async def _worker(self, worker_timeout: float):
        while self.running or not self.request_queue.empty():
            try:
                no_more_jobs = self._worker_job(worker_timeout=worker_timeout)
                if no_more_jobs:
                    logger.info(f"Worker finished working - all remaining requests have been processed.")
                    # Polling_loop should give the required data on whether the stop signal was sent or if
                    # the loop() function gave 'False'.
                    break
            except TimeoutError:
                logger.info("worker couldn't process request in time. A request *may* have been lost.")

    @abc.abstractmethod
    async def _get_updates(self) -> list[tuple[Any, Message]]:
        """
        Obtain updates from another server

        Example:
            self.bot.request_updates()
        """

    async def _polling_job(self, poll_timeout: float):
        try:
            received_updates = await asyncio.wait_for(self._get_updates(), timeout=poll_timeout)
            if received_updates is not None:
                for update in received_updates:
                    await self.request_queue.put(update)
        except TimeoutError:
            logger.debug("polling_job failed - timed out")

    async def _polling_loop(
        self,
        loop: PollingInterfaceLoopFunction = lambda: True,
        poll_timeout: float = None,
        timeout: float = 0,
    ):
        try:
            while loop() and self.running:
                await asyncio.shield(self._polling_job(poll_timeout))  # shield from cancellation
                await asyncio.sleep(timeout)
        finally:
            self.running = False
            # If loop() is somehow True after being False once, this will be wrong.
            # But no user would want to break their own logging, right?
            if loop() is False:
                logger.info(f"polling_loop stopped working - the loop() condition was false")
            else:
                logger.info(f"polling_loop stopped working - the stop signal was received.")
            # If there are no more jobs/stop signal received, a special 'None' request is
            # sent to the queue (one for each worker), they shut down the workers.
            # In case of more workers than two, change the number of 'None' requests to the new number of workers.
            for i in range(self.number_of_workers):
                self.request_queue.put_nowait(None)

    async def connect(
        self,
        pipeline_runner: PipelineRunnerFunction,
        loop: PollingInterfaceLoopFunction = lambda: True,
        poll_timeout: float = None,
        worker_timeout: float = None,
        timeout: float = 0,
    ):
        # Saving strong references to workers, so that they can be cleaned up properly.
        # shield() creates a task just like create_task() according to docs.
        # But for safety we have two task wrappers, I guess.
        for i in range(self.number_of_workers):
            task = asyncio.create_task(asyncio.shield(self._worker(worker_timeout)))
            self._worker_tasks.append(task)
        await self._polling_loop(loop=loop, poll_timeout=poll_timeout, timeout=timeout)

    # Workers for PollingMessengerInterface are awaited here.
    # This probably shouldn't be in cleanup(), it may get overwritten
    # by a user's cleanup if they derive from PollingMessengerInterface.
    # Also, sounds like too critical of a component to call it "cleanup".
    async def cleanup(self):
        await super().cleanup()
        await asyncio.wait(self._worker_tasks)
        # await asyncio.gather(*self._worker_tasks)
        # Blocks until all workers are done

    def _on_exception(self, e: BaseException):
        """
        Method that is called on polling cycle exceptions, in some cases it should show users the exception.
        By default, it logs all exit exceptions to `info` log and all non-exit exceptions to `error`.

        :param e: The exception.
        """
        if isinstance(e, Exception):
            logger.error(f"Exception in {type(self).__name__} loop!", exc_info=e)
        else:
            logger.info(f"{type(self).__name__} has stopped polling.")


class CallbackMessengerInterface(MessengerInterface):
    """
    Callback message interface is waiting for user input and answers once it gets one.
    """

    def __init__(self) -> None:
        self._pipeline_runner: Optional[PipelineRunnerFunction] = None

    async def connect(self, pipeline_runner: PipelineRunnerFunction):
        self._pipeline_runner = pipeline_runner

    async def on_request_async(
        self, request: Message, ctx_id: Optional[Hashable] = None, update_ctx_misc: Optional[dict] = None
    ) -> Context:
        """
        Method that should be invoked on user input.
        This method has the same signature as :py:class:`~chatsky.pipeline.types.PipelineRunnerFunction`.
        """
        return await self._pipeline_runner(request, ctx_id, update_ctx_misc)

    def on_request(
        self, request: Any, ctx_id: Optional[Hashable] = None, update_ctx_misc: Optional[dict] = None
    ) -> Context:
        """
        Method that should be invoked on user input.
        This method has the same signature as :py:class:`~chatsky.pipeline.types.PipelineRunnerFunction`.
        """
        return asyncio.run(self.on_request_async(request, ctx_id, update_ctx_misc))
