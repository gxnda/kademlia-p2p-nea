from dataclasses import dataclass


@dataclass
class Constants:
    K = 20
    B = 5  # or 160 according to https://xlattice.sourceforge.net/components/protocol/kademlia/specs.html
    REQUEST_TIMEOUT_SEC = 0.5  # 500ms
    ID_LENGTH_BYTES = 20
    ID_LENGTH_BITS = ID_LENGTH_BYTES * 8
    MAX_THREADS = 20
    RESPONSE_WAIT_TIME_MS = 10  # in ms
    BUCKET_REFRESH_INTERVAL_MS = 60 * 60 * 1000  # hourly in ms
    KEY_VALUE_REPUBLISH_INTERVAL_MS = 60 * 60 * 1000  # hourly in ms
    KEY_VALUE_EXPIRE_INTERVAL_MS = 60 * 60 * 1000  # hourly in ms
    ORIGINATOR_REPUBLISH_INTERVAL_MS = 24 * 60 * 60 * 1000  # every 24 hours in ms
    EXPIRATION_TIME_SEC = 24 * 60 * 60  # every 24 hours in seconds
    EVICTION_LIMIT = 5
    MAX_PORT_RETRIES = 100
    DEBUG = False

    DHT_SERIALISED_SUFFIX = "dht"
    PICKLE_ENCODING = "latin1"

    if DEBUG:
        A: int = 3
    else:
        A: int = 20
