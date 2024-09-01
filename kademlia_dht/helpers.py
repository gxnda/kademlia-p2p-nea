import logging
import os
import random
import socket
import threading
from hashlib import sha1

from kademlia_dht.constants import Constants
from kademlia_dht.contact import Contact
from kademlia_dht.id import ID
from kademlia_dht.node import Node
from kademlia_dht.storage import VirtualStorage

logger = logging.getLogger("__main__")


def empty_node():
    """
    For testing.
    :return:
    """
    return Node(Contact(id=ID(0)), storage=VirtualStorage())


def random_node():
    return Node(Contact(id=ID.random_id()), storage=VirtualStorage())


def select_random(arr: list, freq: int) -> list:
    return random.sample(arr, freq)


def get_closest_number_index(numbers, target):
    closest_index = 0
    closest_difference = abs(numbers[0] - target)

    for i in range(1, len(numbers)):
        difference = abs(numbers[i] - target)
        if difference < closest_difference:
            closest_difference = difference
            closest_index = i

    return closest_index


def convert_file_to_key(filename: str) -> ID:
    sha1_hash = sha1()
    with open(filename, 'rb') as file:
        while True:
            data = file.read(4096)  # Read data from the file in chunks
            if not data:
                break
            sha1_hash.update(data)  # Update the hash object with the read data
    digest = int(sha1_hash.hexdigest(), 16)
    return ID(digest)


def make_sure_filepath_exists(filename: str) -> None:
    if os.path.isabs(filename):
        logger.debug(f"Path {filename} is absolute.")
        path = filename
    else:
        logger.debug(f"Path {filename} is not absolute.")
        path = os.path.join(os.getcwd(), filename)
        logger.debug(f"Absolute version is {path}")
    if not os.path.exists(path):
        logger.debug(f"Path does not exist.")
        dirname = os.path.dirname(path)
        if dirname:
            if not os.path.exists(dirname):
                os.mkdir(dirname)
    else:
        logger.debug("Path already existed.")


def port_is_free(port: int) -> bool:
    """
    Returns if a port is free on localhost.
    :param port: Port to be checked
    :return: if it's free.
    """

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(('localhost', port))
            return True
    except (OSError, PermissionError):
        return False


def get_valid_port(default_tried=False,
                   lower_bound=1024, upper_bound=65535) -> int:
    """
    Gets a valid port on localhost.
    """
    if lower_bound > upper_bound:
        raise ValueError("Port lower bound cannot be greater than port upper bound.")

    if not default_tried:
        port = 7124  # Default port I wish to use.
        default_tried = True
    else:
        port = random.randint(lower_bound, upper_bound)
    if port_is_free(port):
        return port
    else:
        return get_valid_port(default_tried=default_tried)


class Timer:
    def __init__(self, interval_sec: float, function: callable, auto_reset: bool = False, *args, **kwargs):
        self.interval_sec: float = interval_sec
        self.function: callable = function
        self.auto_reset: bool = auto_reset
        self.args: tuple = args
        self.kwargs: dict = kwargs
        self._stop_event = threading.Event()
        self.__thread = None

    def run(self) -> None:
        logger.info("Starting timer.")
        self._stop_event.clear()

        while not self._stop_event.is_set():
            if self._stop_event.wait(self.interval_sec):
                break
            self.function(*self.args, **self.kwargs)
            if not self.auto_reset:
                break

        logger.info("Timer stopped.")

    def reset(self) -> None:
        self.stop()
        self.start()

    def start(self) -> None:
        if self.__thread is None or not self.__thread.is_alive():
            self.__thread = threading.Thread(target=self.run)
            self.__thread.start()
        else:
            logger.info("Resetting timer.")
            self.reset()

    def stop(self) -> None:
        if self._stop_event.is_set():
            logger.warning("Timer already stopped.")
            return

        logger.info("Stopping timer.")
        self._stop_event.set()
        if self.__thread and self.__thread.is_alive():
            self.__thread.join()

    def stopped(self):
        return self._stop_event.is_set()


def get_sha1_hash_from_file(filename) -> int:
    """
    Hash a file using SHA-1 (160-bit hash).
    """
    sha1_hash = sha1()

    with open(filename, 'rb') as file:
        chunk = file.read(4096)
        while chunk:
            sha1_hash.update(chunk)
            chunk = file.read(4096)

    return int.from_bytes(sha1_hash.digest(), byteorder='big')


def get_sha1_hash(input: bytes) -> int:
    sha1_hash = sha1(input)
    return int.from_bytes(sha1_hash.digest(), byteorder='big')


if __name__ == "__main__":
    var = "hello world"
    digest = get_sha1_hash(var.encode("latin-1"))
    print(digest)

