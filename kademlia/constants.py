from dataclasses import dataclass

from .main import DEBUG


@dataclass
class Constants:
    """
    TODO: Add docstring here.
    """
    K = 20
    B = 5  # or 160 according to https://xlattice.sourceforge.net/components/protocol/kademlia/specs.html
    REQUEST_TIMEOUT = 0.5  # 500ms
    ID_LENGTH_BYTES = 20
    ID_LENGTH_BITS = 160
    MAX_THREADS = 20
    QUERY_TIME = 500  # in ms
    RESPONSE_WAIT_TIME = 10  # in ms
    BUCKET_REFRESH_INTERVAL = 60 * 60 * 1000  # hourly
    KEY_VALUE_REPUBLISH_INTERVAL = 60 * 60 * 1000  # hourly
    KEY_VALUE_EXPIRE_INTERVAL = 60 * 60 * 1000  # hourly
    ORIGINATOR_REPUBLISH_INTERVAL = 24 * 60 * 60 * 1000  # every 24 hours in ms
    EXPIRATION_TIME_SEC = 24 * 60 * 60  # every 24 hours in seconds
    EVICTION_LIMIT = 5

    DHT_SERIALISED_SUFFIX = "dht"

    if DEBUG:
        A: int = 3
    else:
        A: int = 20
