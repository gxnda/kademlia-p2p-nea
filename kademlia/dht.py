import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

import dill

from kademlia import helpers
from kademlia.buckets import KBucket
from kademlia.constants import Constants
from kademlia.contact import Contact
from kademlia.dictionaries import FindResult
from kademlia.errors import BucketDoesNotContainContactToEvictError, RPCError
from kademlia.id import ID
from kademlia.interfaces import IProtocol, IStorage
from kademlia.node import Node
from kademlia.routers import BaseRouter


class DHT:
    """
    This is the main entry point for our peer to interact with other peers.

    This has multiple purposes:
     - One is to propagate key-values to other close peers on the network using a lookup algorithm.
     - Another is to use the same lookup algorithm to search for other close nodes that might have a value that we don’t have.
     - It is also used for bootstrapping our peer into a pre-existing network.

    """

    def __init__(self,
                 id: ID,
                 protocol: IProtocol,
                 router: BaseRouter,
                 storage_factory: Callable[[], IStorage] | None = None,
                 originator_storage: IStorage | None = None,
                 republish_storage: IStorage | None = None,
                 cache_storage: IStorage | None = None):
        """

        We use a wrapper Dht class, which will become the main entry point for our peer,
        for interacting with other peers. The purposes of this class are:

         - When storing a value, use the lookup algorithm to find other closer peers to
         propagate the key-value.
         - When looking up a value, if our peer doesn’t have the value, we again use the
         lookup algorithm to find other closer nodes that might have the value.
         - A bootstrapping method that registers our peer with another peer and
         initializes our bucket list with that peer’s closest contacts.

        Supports different concrete storage types.
        For example, you may want the cache_storage to be an in-memory store,
        the originator_storage to be a SQL database, and the republish store to be a
        key-value database.

        :param id: ID associated with the DHT.

        :param protocol: Protocol implemented by the DHT.

        :param storage_factory: Storage to be used for all storage mechanisms -
        if specific mechanisms are not provided.

        :param originator_storage: Pre-existing storage object to be used for main
        storage.

        :param republish_storage: This contains key-values that have been republished
        by other peers.

        :param cache_storage: Short term storage.

        :param router: Router object associated with the DHT.
        """

        if originator_storage:
            self._originator_storage = originator_storage
        elif storage_factory:
            # if storage_factory == SecondaryJSONStorage:
            #     self._originator_storage = storage_factory(
            #         filename=f"{id.value}/originator_storage.json")
            # else:
            self._originator_storage = storage_factory()
        else:
            raise TypeError(
                "Originator storage must take parameter originator_storage,"
                " or be generated by generated by parameter storage_factory.")

        if republish_storage:
            self._republish_storage = republish_storage
        elif storage_factory:
            # if storage_factory == SecondaryJSONStorage:
            #     self._republish_storage = storage_factory(
            #         filename=f"{id.value}/republish_storage.json")
            # else:
            self._republish_storage = storage_factory()
        else:
            raise TypeError(
                "Republish storage must take parameter republish_storage,"
                " or be generated by generated by parameter storage_factory.")

        if cache_storage:
            self._cache_storage = cache_storage
        elif storage_factory:
            # if storage_factory == SecondaryJSONStorage:
            #     self._cache_storage = storage_factory(
            #         filename=f"{id.value}/cache_storage.json")
            # else:
            self._cache_storage = storage_factory()
        else:
            raise TypeError(
                "Cache storage must take parameter cache_storage,"
                " or be generated by generated by parameter storage_factory.")

        self.pending_contacts: list[Contact] = []
        self.our_id = id
        self.our_contact = Contact(id=id, protocol=protocol)
        # if router.node:
        #     self.node: Node = router.node
        self.node: Node = Node(self.our_contact,
                               storage=self._republish_storage,
                               cache_storage=self._cache_storage)
        self.node.dht = self
        self.node.bucket_list.dht = self
        self._protocol = protocol
        self._router: BaseRouter = router
        self._router.node = self.node
        self._router.dht = self
        self.eviction_count: dict[int, int] = {}

    def router(self) -> BaseRouter:
        return self._router

    def protocol(self) -> IProtocol:
        return self._protocol

    def originator_storage(self) -> IStorage:
        return self._originator_storage

    def store(self, key: ID, val: str) -> None:
        print(f"[Client] Storing value at {key}.")
        self.touch_bucket_with_key(key)
        # We're storing to K closer contacts
        self._originator_storage.set(key, val)
        self.store_on_closer_contacts(key, val)

    def find_value(self, key: ID) -> tuple[bool, list[Contact] | None, str | None]:
        """
        Attempts to find a given value.
        First it checks our originator storage. If the given key does not have a value in our storage,
        it will use Router.lookup() to attempt to find it. If there is no value found from router.lookup(), the value
        returned will be None.
        If there is a value found from router.lookup(), the value will be stored on the closest contact to us, if
        one exists.
        :param key: Key to search for value pair.
        :return: Found: bool (If it is found or not), contacts: list[Contact], val: str | None (value returned)
        """
        print("touch bucket with key")
        self.touch_bucket_with_key(key)
        contacts_queried: list[Contact] = []

        # ret (found: False, contacts: None, val: None)
        contacts: list[Contact] | None = None
        # - Add to docstring when finished
        val: str | None = None

        found, our_val = self._originator_storage.try_get_value(key)
        # There has to be a better way to do this.
        if our_val:
            found = True
            val = our_val
        else:
            found, our_val = self._republish_storage.try_get_value(key)
            if our_val:
                found = True
                val = our_val
            else:
                found, our_val = self._cache_storage.try_get_value(key)
                if our_val:
                    found = True
                    val = our_val
                else:
                    lookup: FindResult = self._router.lookup(
                        key, self._router.rpc_find_value)
                    if lookup["found"]:
                        found = True
                        contacts = None
                        val = lookup["val"]
                        # Find the closest contact (other than the one the value was found by)
                        # in which to "cache" the key-value.

                        store_to: Contact | None = None
                        for c in lookup["contacts"]:
                            if c.id.value != lookup["found_by"].id.value:
                                store_to: Contact | None = c
                                break

                        if store_to:
                            separating_nodes: int = self._get_separating_nodes_count(self.our_contact, store_to)
                            exp_time_sec: int = Constants.EXPIRATION_TIME_SEC // (2 ** separating_nodes)
                            error: RPCError = store_to.protocol.store(self.node.our_contact, key, lookup["val"],
                                                                      exp_time_sec=exp_time_sec)
                            self.handle_error(error, store_to)

        return found, contacts, val

    def touch_bucket_with_key(self, key: ID) -> None:
        """
        Touches a KBucket with a given key from the bucket list.
        :return: Returns nothing.
        """
        self.node.bucket_list.get_kbucket(key).touch()

    def store_on_closer_contacts(self, key: ID, val: str) -> None:
        now: datetime = datetime.now()
        kbucket: KBucket = self.node.bucket_list.get_kbucket(key)
        contacts: list[Contact]
        if (now - kbucket.time_stamp) < timedelta(
                milliseconds=Constants.BUCKET_REFRESH_INTERVAL):
            # Bucket has been refreshed recently, so don't do a lookup as we
            # have the k closest contacts.
            contacts: list[Contact] = self.node.bucket_list.get_close_contacts(
                key=key, exclude=self.node.our_contact.id)
        else:
            contacts: list[Contact] = self._router.lookup(
                key, self._router.rpc_find_nodes)["contacts"]

        for c in contacts:
            error: RPCError | None = c.protocol.store(
                sender=self.node.our_contact, key=key, val=val)
            self.handle_error(error, c)

    def bootstrap(self, known_peer: Contact) -> None:
        """
        This is how we join the network.

        We bootstrap our peer by contacting a known peer in the network, adding its contacts
        to our list, then getting the contacts for other peers not in the
        bucket range of our known peer we're joining.
        :param known_peer: Peer we know / are bootstrapping from.
        :return: None
        """
        print("[Client] Bootstrapping from known peer.")
        # print(f"Adding known peer with ID {known_peer.id}")
        self.node.bucket_list.add_contact(known_peer)

        # UNITTEST NOTES: This should return something in test_bootstrap_outside_bootstrapping_bucket,
        # it isn't at the moment.
        # find_node() should return the bucket list with the contact who knows 10 other contacts
        # it does.

        # finds K close contacts to self.our_id, excluding self.our_contact
        contacts, error = known_peer.protocol.find_node(
            sender=self.our_contact, key=self.our_id)
        self.handle_error(error, known_peer)
        if not error.has_error():
            # print("NO ERROR")

            # add all contacts the known peer DIRECTLY knows
            for contact in contacts:
                self.node.bucket_list.add_contact(contact)

            known_peers_bucket: KBucket = self.node.bucket_list.get_kbucket(
                known_peer.id)

            # Resolve the list now, so we don't include additional contacts
            # as we add to our bucket additional contacts.
            other_buckets: list[KBucket] = [
                i for i in self.node.bucket_list.buckets
                if i != known_peers_bucket
            ]
            for other_bucket in other_buckets:
                self._refresh_bucket(
                    other_bucket
                )  # UNITTEST Notes: one of these should contain the correct contact
        else:
            raise error

    def _refresh_bucket(self, bucket: KBucket) -> None:
        """
        Refreshes the given Kademlia KBucket by updating its last-touch timestamp,
        obtaining a random ID within the bucket's range, and attempting to find
        nodes in the network with that random ID.

        The method touches the bucket to update its last-touch timestamp, generates
        a random ID within the bucket's range, and queries nodes in the network
        using the Kademlia protocol to find nodes with the generated ID. If successful,
        the discovered contacts are added to the Kademlia node's bucket list.

        Note:
        The contacts collection for the given bucket might change during the operation,
        so it is isolated in a separate list before iterating over it.

        :param bucket: The KBucket to be refreshed.
        :returns: Nothing.
        """
        bucket.touch()
        random_id: ID = ID.random_id_within_bucket_range(bucket)

        # put in a separate list as contacts collection for this bucket might change.
        contacts: list[Contact] = bucket.contacts
        for contact in contacts:
            # print(contact.id, contact.protocol.node.bucket_list.contacts())
            new_contacts, timeout_error = contact.protocol.find_node(
                self.our_contact, random_id)
            # print(contacts.index(contact) + 1, "new contacts", new_contacts)
            self.handle_error(timeout_error, contact)
            if new_contacts:
                for other_contact in new_contacts:
                    self.node.bucket_list.add_contact(other_contact)

    def _setup_bucket_refresh_timer(self) -> None:
        """
        Sets up the refresh timer to re-ping KBuckets.

        From the spec:
        “Buckets are generally kept fresh by the traffic of requests traveling through nodes. To handle pathological
        cases in which there are no lookups for a particular ID range, each node refreshes any bucket to which it has
        not performed a node lookup in the past hour. Refreshing means picking a random ID in the bucket’s range and
        performing a node search for that ID.”
        """
        bucket_refresh_timer = threading.Timer(Constants.BUCKET_REFRESH_INTERVAL / 1000, self._refresh_bucket)
        bucket_refresh_timer.auto_reset = True
        bucket_refresh_timer.elapsed += self.bucket_refresh_timer_elapsed
        bucket_refresh_timer.start()

    def _bucket_refresh_timer_elapsed(self):
        now: datetime = datetime.now()
        # Put into a separate list as bucket collections may be modified.
        current_buckets: list[KBucket] = [
            b for b in self.node.bucket_list.buckets
            if (now - b.time_stamp) >= timedelta(milliseconds=Constants.BUCKET_REFRESH_INTERVAL)
        ]

        for b in current_buckets:
            self._refresh_bucket(b)

    def _key_value_republish_elapsed(self) -> None:
        """
        Replicate key values if the key value hasn't been touched within
        the republish interval. Also don't do a FindNode lookup if the
        bucket containing the key has been refresed within the refresh
        interval.
        """
        now: datetime = datetime.now()

        rep_keys = [
            k for k in self._republish_storage.get_keys()
            if now - self._republish_storage.get_timestamp(k) >=
               Constants.KEY_VALUE_REPUBLISH_INTERVAL
        ]

        for k in rep_keys:
            key: ID = ID(k)
            self.store_on_closer_contacts(key,
                                          self._republish_storage.get(key))
            self._republish_storage.touch(k)

    def _expire_keys_elapsed(self) -> None:
        """
        Removes expired key-values from republish and cache storage.
        """
        self._remove_expired_data(self._cache_storage)
        self._remove_expired_data(self._republish_storage)

    @staticmethod
    def _remove_expired_data(store: IStorage) -> None:
        now: datetime = datetime.now()
        # to list so our key list is resolved now as we remove keys
        expired: list[int] = [
            key for key in store.get_keys()
            if (now - store.get_timestamp(key)) >= timedelta(
                seconds=store.get_expiration_time_sec(key))
        ]

        # expired is a list of all expired keys in the given storage.
        for key in expired:
            store.remove(key)

    def _originator_republish_elapsed(self) -> None:
        """
        Redistributes expired key-value pars if we are the publisher.


        Spec: “For Kademlia’s current application (file sharing),
        we also require the original publisher of a (key,value)
        pair to republish it every 24 hours. Otherwise, (key,value)
        pairs expire 24 hours after publication, to limit stale
        index information in the system. For other applications, such
        as digital certificates or cryptographic hash to value mappings,
        longer expiration times may be appropriate.”
        """
        now: datetime = datetime.now()

        keys_pending_republish = [
            key for key in self._originator_storage.get_keys()
            if (now -
                self._originator_storage.get_timestamp(key.value)) >= timedelta(
                milliseconds=Constants.ORIGINATOR_REPUBLISH_INTERVAL)
        ]

        for k in keys_pending_republish:
            key: ID = k
            # Just use close contacts, don't do a lookup
            contacts = self.node.bucket_list.get_close_contacts(
                key, self.node.our_contact.id)

            for c in contacts:
                error: RPCError | None = c.protocol.store(
                    sender=self.our_contact,
                    key=key,
                    val=self._originator_storage.get(key)
                )
                self.handle_error(error, c)

            self._originator_storage.touch(k.value)

    def _get_separating_nodes_count(self, contact_a: Contact, contact_b: Contact) -> int:
        """
        Returns the number of contacts between 2 contacts in our bucket list.
        :param contact_a:
        :param contact_b:
        :return:
        """
        # get all the contacts, ordered by ID
        all_contacts: list[Contact] = sorted(self.node.bucket_list.contacts(), key=lambda c: c.id.value)
        index_a = helpers.get_closest_number_index([i.id.value for i in all_contacts], contact_a.id.value)
        index_b = helpers.get_closest_number_index([i.id.value for i in all_contacts], contact_b.id.value)
        count = abs(index_a - index_b)
        return count

    def handle_error(self, error: RPCError | None, contact: Contact) -> None:
        """
        Put the timed out contact into a collection and increment the number
        of times it has timed out.

        If it has timed out a certain amount, remove it from the bucket
        and replace it with the most recent pending contact that are
        queued for that bucket.
        """
        if error:
            if error.has_error():
                count = self._add_contact_to_evict(contact.id.value)
                if count >= Constants.EVICTION_LIMIT:
                    self._replace_contact(contact)

    def delay_eviction(self,
                       to_evict: Contact,
                       to_replace: Contact) -> None:
        """
        The contact that did not respond (or had an error) gets "n"
        tries before being evicted and replaced with the most recently
        seen contact that wants to got into the non-responding contact's
        K-Bucket

        :param to_evict: The contact that didn't respond.
        :param to_replace: The contact that can replace the
        non-responding contact.
        """
        # Non-concurrent list needs locking
        # lock(pending_contacts)
        # add only if its a new pending contact.
        if to_replace.id not in [c.id for c in self.pending_contacts]:
            self.pending_contacts.append(to_replace)

        key: int = to_evict.id.value
        count = self._add_contact_to_evict(key)
        # if the eviction attempts on key reach the eviction limit
        if count == Constants.EVICTION_LIMIT:
            self._replace_contact(to_evict)

    def _add_contact_to_evict(self, key_to_evict: int) -> int:
        """
        Increments how many times we have tried to evict a given key, returning number of attempts.
        :param key_to_evict: to_evict
        :return: number of attempts
        """
        # self.eviction_count is a dictionary of ID keys ->
        # how many times they have been considered for eviction.
        if key_to_evict not in self.eviction_count:
            self.eviction_count[key_to_evict] = 0
        self.eviction_count[key_to_evict] += 1

        return self.eviction_count[key_to_evict]

    def _replace_contact(self, to_evict: Contact) -> None:
        """
        Replaces an evicted contact with a pending one.
        :param to_evict:
        :return:
        """
        bucket = self.node.bucket_list.get_kbucket(to_evict.id)
        # Prevent other threads from manipulating the bucket list or buckets
        # lock(self.node.bucket_list)
        self._evict_contact(bucket, to_evict)
        self._replace_with_pending_contact(bucket)

    def _evict_contact(self, bucket: KBucket, to_evict: Contact) -> None:
        """
        Removes all attempts to evict to_evict, then removes it from the given bucket,
        raising an error if it is not in the bucket.
        :param bucket:
        :param to_evict:
        :return:
        """

        print("[Client] Evicting contact from bucket.")

        if to_evict.id.value in self.eviction_count:
            self.eviction_count.pop(to_evict.id.value)

        if not bucket.contains(to_evict.id):
            raise BucketDoesNotContainContactToEvictError(
                "Bucket does not contain the contact to be evicted."
            )
        else:
            bucket.evict_contact(to_evict)

    def save(self, filename: str) -> None:
        """
        Saves DHT to file.
        """
        print(f"[Client] Saving DHT to {filename}...")
        helpers.make_sure_filepath_exists(filename)
        with open(filename, "wb") as output_file:
            dill.dump(self, file=output_file)
        print(f"[Client] Saved DHT to {filename}.")

    @classmethod
    def load(cls, filename: str):
        """
        Loads DHT from file.
        """
        print(f"[Client] Loading DHT from file {filename}...")
        with open(filename, "rb") as input_file:
            data = dill.load(file=input_file)
        print(f"[Client] Loaded DHT from file {filename}.")
        return data

    def _replace_with_pending_contact(self, bucket: KBucket) -> None:
        """
        Find a pending contact that goes into the bucket that now has room;
        that pending contact is no longer pending.
        :param bucket:
        :return:
        """
        # lock(self.pending_contacts)
        contact: Optional[Contact] = sorted([c for c in self.pending_contacts if
                                             self.node.bucket_list.get_kbucket(c.id) == bucket],
                                            key=lambda c: c.last_seen)[-1]
        if contact is not None:
            self.pending_contacts.remove(contact)
            bucket.add_contact(contact)
