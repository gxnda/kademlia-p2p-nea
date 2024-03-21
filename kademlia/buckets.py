from datetime import datetime
from os.path import commonprefix

from kademlia.constants import Constants
from kademlia.contact import Contact
from kademlia.errors import BucketDoesNotContainContactToEvictError, OurNodeCannotBeAContactError, OutOfRangeError, \
    RPCError, TooManyContactsError
from kademlia.id import ID


class KBucket:

    def __init__(self,
                 initial_contacts: list[Contact] | None = None,
                 low: int = 0,
                 high: int = 2 ** 160):
        """
        Initialises a k-bucket with a specific ID range,
        initially from 0 to 2**160.
        """
        if initial_contacts is None:  # Fix for instead of setting initial_contacts = []
            initial_contacts = []

        self.contacts: list[Contact] = initial_contacts
        self._low: int = low
        self._high: int = high
        self.time_stamp: datetime = datetime.now()
        # self.lock = WithLock(Lock())

    def low(self) -> int:
        return self._low

    def high(self) -> int:
        return self._high

    def is_full(self) -> bool:
        """
        This INCLUDES K, so if there are 20 inside, no more can be added.
        :return: Boolean saying if it's full.
        """
        return len(self.contacts) >= Constants.K

    def contains(self, id: ID) -> bool:
        """
        Returns boolean determining whether a given contact ID is in the k-bucket.
        """

        # replaceable
        return any(id == contact.id for contact in self.contacts)

    def touch(self) -> None:
        self.time_stamp = datetime.now()

    def is_in_range(self, other_id: ID) -> bool:
        """
        Determines if a given ID is within the range of the k-bucket.
        :param other_id: The ID to be checked.
        :return: Boolean saying if it's in the range of the k-bucket.
        """
        return self._low <= other_id.value <= self._high

    def add_contact(self, contact: Contact) -> None:
        if self.is_full():
            raise TooManyContactsError(
                f"KBucket is full - (length is {len(self.contacts)}).")
        elif not self.is_in_range(contact.id):
            raise OutOfRangeError("Contact ID is out of range.")
        elif contact not in self.contacts:
            self.contacts.append(contact)
        else:
            print("[Client] Contact already in KBucket.")

    def depth(self) -> int:
        """
        "The depth is just the length of the prefix shared by all nodes in
        the k-bucket’s range." Do not confuse that with this statement in the
        spec: “Define the depth, h, of a node to be 160 - i, where i is the
        smallest index of a nonempty bucket.” The former is referring to the
        depth of a k-bucket, the latter the depth of the node.
        """

        return len(self.shared_bits())

    def shared_bits(self) -> str:
        """
        Return the longest shared binary prefix between all
        contacts in the kbucket. This does not "0b" before the binary.
        """
        shared_bits = commonprefix([i.id.bin() for i in self.contacts])
        # print("shared bits", shared_bits)
        return shared_bits

    def split(self) -> tuple:
        """
        Splits KBucket in half, returns tuple of type (KBucket, KBucket).
        """
        # This doesn't work when all contacts are bunched towards one side of the KBucket.
        # It's in the spec so I'm keeping it, it also means it stays nice and neat

        midpoint: int = (self._low + self._high) // 2  # This will always be an integer, but // is faster than /.

        # Gets the median of all contacts inside the KBucket (rounding up in even # of contacts)
        # contact_ids_asc = sorted([c.id.value for c in self.contacts])
        # median_of_contact_id: int = median_high(contact_ids_asc)
        # midpoint = median_of_contact_id

        k1: KBucket = KBucket(low=self._low, high=midpoint)
        k2: KBucket = KBucket(low=midpoint, high=self._high)
        for c in self.contacts:
            if c.id.value < midpoint:
                k1.add_contact(c)
            else:
                k2.add_contact(c)

        return k1, k2

    def replace_contact(self, contact: Contact) -> None:
        """replaces contact, then touches it"""
        contact_ids = [c.id for c in self.contacts]
        index = contact_ids.index(contact.id)
        contact.touch()
        self.contacts[index] = contact

    def evict_contact(self, contact: Contact) -> None:
        if self.contains(contact.id):
            self.contacts.remove(contact)
        else:
            raise BucketDoesNotContainContactToEvictError(
                "Contact not found."
            )


class BucketList:

    def __init__(self, our_contact: Contact):
        """
        :param our_contact: Our contact
        """
        self.dht = None
        self.buckets: list[KBucket] = [KBucket()]
        # first k-bucket has max range
        self.our_id: ID = our_contact.id
        self.our_contact: Contact = our_contact

        # create locking object
        # self.lock = WithLock(Lock())

    def can_split(self, kbucket: KBucket) -> bool:
        # kbucket.HasInRange(ourID) || ((kbucket.Depth() % Constants.B) != 0)
        """
        The depth to which the bucket has split is based on the number of bits
        shared in the prefix of the contacts in the bucket. With random IDs,
        this number will initially be small, but as bucket ranges become more
        narrow from subsequent splits, more contacts will begin the share the
        same prefix and the bucket when split, will result in less “room” for
        new contacts. Eventually, when the bucket range becomes narrow enough,
        the number of bits shared in the prefix of the contacts in the bucket
        reaches the threshold b, which the spec says should be 5.
        """
        # Locking might be useful here?
        return (kbucket.is_in_range(self.our_id)
                or (kbucket.depth() % Constants.B != 0))

    def _get_kbucket_index(self, other_id: ID) -> int:
        """
        Returns the first k-buckets index in the bucket list
        which has a given ID in range. Returns -1 if not found.
        """

        # with self.lock:
        for i in range(len(self.buckets)):
            if self.buckets[i].is_in_range(other_id):
                return i
        return -1

    def get_kbucket(self, other_id: ID) -> KBucket:
        """
        Returns the first k-bucket in the bucket list
        which has a given ID in range. Raises an error if none are found
         - this should never happen!
        :param other_id: ID to used to determine range.
        :return: the first k-bucket which is in range.
        """

        try:
            bucket = self.buckets[self._get_kbucket_index(other_id)]
            return bucket

        except IndexError:
            raise OutOfRangeError(f"ID: {id} is not in range of bucket-list.")

    def add_contact(self, contact: Contact) -> None:
        """
        Adds a contact to a k-bucket in the list, this is determined by the range of k-buckets in the lists.
        This range should span the entire ID space - so there should always be a k-bucket to be added.

        If we can't add it, it will be added to DHT pending contacts.

        This raises an error if we try to add ourselves to the k-bucket.

        :param contact: Contact to be added, this is touched in the process.
        :return: None
        """
        if self.our_id == contact.id:
            raise OurNodeCannotBeAContactError(
                "Cannot add ourselves as a contact.")

        contact.touch()  # Update the time last seen to now

        # print("[Client] Add contact called.")
        # with self.lock:
        kbucket: KBucket = self.get_kbucket(contact.id)
        if kbucket.contains(contact.id):
            print("[Client] Contact already in KBucket.")
            # replace contact, then touch it
            kbucket.replace_contact(contact)
        elif kbucket.is_full():
            print("[Client] Kbucket is full.")
            if self.can_split(kbucket):
                print("[Client] Splitting!")
                # Split then try again
                k1, k2 = kbucket.split()
                # print(f"K1: {len(k1.contacts)}, K2: {len(k2.contacts)}, Buckets: {self.buckets}")
                index: int = self._get_kbucket_index(contact.id)

                # adds the two buckets to 2 separate buckets.
                self.buckets[index] = k1  # Replaces original KBucket
                self.buckets.insert(index + 1, k2)  # Adds a new one after it
                # print(self.buckets)
                self.add_contact(
                    contact
                )  # Unless k <= 0, This should never cause a recursive loop
            else:
                print("[Client] Cannot split")
                last_seen_contact: Contact = sorted(
                    kbucket.contacts, key=lambda c: c.last_seen)[0]
                error: RPCError | None = last_seen_contact.protocol.ping(
                    self.our_contact)
                if error:
                    # Unresponsive
                    print("[Client] Node is unresponsive")
                    if self.dht:  # tests may not initialise a DHT
                        print("[Client] Delaying eviction")
                        self.dht.delay_eviction(last_seen_contact, contact)
                else:
                    # still can't add the contact ,so put it into the pending list
                    print("[Client] Node is responsive.")
                    if self.dht:
                        print("[Client] Adding node to DHT pending...")
                        self.dht.add_to_pending(contact)

        else:
            # Bucket is not full, nothing special happens.
            # print("[Client] Adding contact to bucket")
            kbucket.add_contact(contact)

    def get_close_contacts(self, key: ID, exclude: ID) -> list[Contact]:
        """
        Brute force distance lookup of all known contacts, sorted by distance.
        Then we take K of the closest.
        :param key: The ID for which we want to find close contacts.
        :param exclude: The ID to exclude (the requesters ID).
        :return: List of K contacts sorted by distance.
        """
        # print(key, exclude)
        # with self.lock:
        contacts = []
        # print(self.buckets)
        for bucket in self.buckets:
            # print(bucket.contacts)
            for contact in bucket.contacts:
                # print(contact.id.value)
                # print(f"Exclude: {exclude}")

                if contact.id != exclude:
                    contacts.append(contact)
        # print(contacts)
        contacts = sorted(contacts, key=lambda c: c.id ^ key)[:Constants.K]
        if len(contacts) > Constants.K and Constants.DEBUG:
            raise ValueError(
                f"Contacts should be smaller than or equal to K. Has length {len(contacts)}, "
                f"which is {Constants.K - len(contacts)} too big.")
        return contacts

    def contacts(self) -> list[Contact]:
        """
        Returns a list of all contacts in the bucket list.
        :return: All contacts in the bucket list.
        """
        contacts = []
        for bucket in self.buckets:
            for contact in bucket.contacts:
                contacts.append(contact)
        return contacts

    def contact_exists(self, contact: Contact) -> bool:
        return contact in self.contacts()
