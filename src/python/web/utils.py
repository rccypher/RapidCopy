
# Input length limits
MAX_FILENAME_LEN = 1024   # bytes, filesystem limit is 255 but paths can be longer
MAX_PATTERN_LEN = 512
MAX_CONFIG_VALUE_LEN = 4096
MAX_PATH_LEN = 4096


def check_length(value: str, max_len: int, label: str):
    """Return a 400 HTTPResponse if value exceeds max_len, else None."""
    if len(value) > max_len:
        from bottle import HTTPResponse
        return HTTPResponse(
            body=f"{label} exceeds maximum length of {max_len} characters",
            status=400
        )
    return None

# Copyright 2017, Inderpreet Singh, All rights reserved.

from queue import Queue, Empty
from typing import TypeVar, Generic, Optional


T = TypeVar('T')


class StreamQueue(Generic[T]):
    """
    A queue that transfers events from one thread to another.
    Useful for web streams that wait for listener events from other threads.
    The producer thread calls put() to insert events. The consumer stream
    calls get_next_event() to receive event in its own thread.
    """
    def __init__(self):
        self.__queue = Queue()

    def put(self, event: T):
        self.__queue.put(event)

    def get_next_event(self) -> T | None:
        """
        Returns the next event if there is one, otherwise returns None
        :return:
        """
        try:
            return self.__queue.get(block=False)
        except Empty:
            return None
