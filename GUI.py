import threading
from socket import gethostname

import customtkinter as ctk
from PIL import Image

from kademlia import dht, id, networking, protocols, node, contact, storage, routers

"""
├── User Interface
│   ├── Join
│   │   ├── Settings
│   │   ├── Load an existing network
│   │   └── Bootstrap into a new network
│   ├── Main menu
│   │   ├── Settings
│   │   ├── Download a file
│   │   ├── Add a file for upload
│   │   ├── Remove a file for upload
│   │   ├── Leave network
│   │   └── Search using key


open UserInterface(), then check if the user is in a network already or not
- the k-buckets are stored in a JSON file, which is used to check this, 
and if the user is not in a network, the user is prompted to join a network.
"""


class KademliaFonts:
    pass


class ContactViewer(ctk.CTk):
    def __init__(self, id: int, protocol_type: type, url: str, port: int, appearance_mode="dark"):
        super().__init__()
        self.geometry("300x200")
        ctk.set_appearance_mode(appearance_mode)

        self.settings_title = ctk.CTkLabel(self, text="Our Contact:", font=("Aharoni", 20, "bold"))
        self.settings_title.pack(padx=20, pady=30)

        self.id = ctk.CTkLabel(self, text=str(id), font=("Aharoni", 20, "bold"))
        self.id.pack(padx=20, pady=10)

        self.protocol_type = ctk.CTkLabel(self, text=str(protocol_type), font=("Aharoni", 20, "bold"))
        self.protocol_type.pack(padx=20, pady=10)

        self.url = ctk.CTkLabel(self, text=str(url), font=("Aharoni", 20, "bold"))
        self.url.pack(padx=20, pady=10)

        self.port = ctk.CTkLabel(self, text=str(port), font=("Aharoni", 20, "bold"))
        self.port.pack(padx=20, pady=10)


class Settings(ctk.CTk):
    def __init__(self, hash_table: dht.DHT, appearance_mode="dark"):
        super().__init__()
        ctk.set_appearance_mode(appearance_mode)

        self.dht: dht.DHT = hash_table

        self.geometry("200x300")
        self.title("Kademlia Settings")

        self.settings_title = ctk.CTkLabel(self, text="Settings", font=("Aharoni", 20, "bold"))
        self.settings_title.pack(padx=20, pady=30)

        self.dht_export_file = ctk.CTkTextbox(self, width=200, height=20)
        self.dht_export_file.pack(padx=20, pady=10)

        self.export_dht_button = ctk.CTkButton(self, text="Export", command=self.export_dht)
        self.export_dht_button.pack(padx=20, pady=10)

        self.view_contact_button = ctk.CTkButton(self, text="View our contact", command=self.view_contact)
        self.view_contact_button.pack(padx=20, pady=10)

    def export_dht(self):
        file = self.dht_export_file.get("0.0", "end").strip("\n")
        self.dht.save(file)

    def view_contact(self):
        our_contact: contact.Contact = self.dht.our_contact
        our_id: int = our_contact.id.value
        protocol: protocols.TCPSubnetProtocol = our_contact.protocol
        protocol_type: type = type(protocol)
        our_ip_address: str = protocol.url
        our_port: int = protocol.port

        contact_viewer = ContactViewer(
            id=our_id,
            protocol_type=protocol_type,
            url=our_ip_address,
            port=our_port
        )
        contact_viewer.mainloop()

class MainGUI(ctk.CTk):
    def __init__(self, appearance_mode="dark"):
        ctk.CTk.__init__(self)
        self.appearance_mode = appearance_mode
        self.geometry("600x500")
        self.title("Kademlia")

        self.initialise_kademlia()

        print(self.dht.__dict__)
        ctk.set_appearance_mode(appearance_mode)
        self.make_join_dht_frame()

    def initialise_kademlia(self):
        """
        Initialises Kademlia protocol.
        :return:
        """
        # TODO: This still uses kademlia.networking.TCPSubnetProtocol,
        #     kademlia.networking.TCPProtocol will be ideal in the future.
        #     (Should still work for external references, just a bit iffy)
        print("[Initialisation] Initialising Kademlia.")

        our_id = id.ID.random_id()
        our_ip = gethostname()
        print(f"[Initialisation] Our hostname is {our_ip}.")

        valid_port = None
        for port in range(10000, 30000):
            if networking.port_is_free(port):
                valid_port = port
                break
        if not valid_port:
            raise OSError("No ports free!")

        print(f"[Initialisation] Port free at {valid_port}, creating our node here.")

        protocol = protocols.TCPSubnetProtocol(
            url=our_ip, port=valid_port, subnet=1
        )

        our_node = node.Node(
            contact=contact.Contact(
                id=our_id,
                protocol=protocol
            ),
            storage=storage.SecondaryStorage(f"{our_id.value}/node.json"),
            cache_storage=storage.VirtualStorage()
        )

        self.dht: dht.DHT = dht.DHT(
            id=our_id,
            protocol=protocol,
            originator_storage=storage.SecondaryStorage(f"{our_id.value}/originator_storage.json"),
            republish_storage=storage.SecondaryStorage(f"{our_id.value}/republish_storage.json"),
            cache_storage=storage.VirtualStorage(),
            router=routers.ParallelRouter(our_node)
        )

    def open_settings(self):
        settings_window = Settings(hash_table=self.dht, appearance_mode=self.appearance_mode)
        settings_window.mainloop()

    def thread_open_settings(self):
        settings_thread = threading.Thread(target=self.open_settings, daemon=True)
        settings_thread.daemon = True  # Dies when program ends.
        settings_thread.start()

    def add_settings_icon(self):
        dark_icon = Image.open(r"assets/settings_icon_light.png")
        light_icon = Image.open(r"assets/settings_icon_dark.png")
        settings_icon = ctk.CTkImage(light_image=light_icon, dark_image=dark_icon, size=(30, 30))
        self.settings_button = ctk.CTkButton(self, image=settings_icon, text="",
                                             bg_color="transparent", fg_color="transparent",
                                             width=28, command=self.open_settings)
        self.settings_button.pack(side=ctk.RIGHT, anchor=ctk.SE, padx=10, pady=10)

    def clear_screen(self):
        for child in self.winfo_children():
            child.destroy()
        self.add_settings_icon()

    def make_join_dht_frame(self):
        self.clear_screen()
        join = JoinFrame(parent=self)
        join.pack(padx=20, pady=20)

    def make_load_dht_frame(self):
        self.clear_screen()
        load_dht = LoadDHTFrame(parent=self)
        load_dht.pack(padx=20, pady=20)

    def make_network_page(self):


class LoadDHTFrame(ctk.CTkFrame):
    def __init__(self, parent: MainGUI, fg_color="transparent", **kwargs):
        ctk.CTkFrame.__init__(self, parent, **kwargs)
        self.configure(fg_color=fg_color)
        self.parent = parent

        self.load_title = ctk.CTkLabel(master=self, text="Load DHT from file", font=("Aharoni", 20, "bold"))
        self.load_title.grid(column=0, row=0, columnspan=2, padx=20, pady=20)

        self.enter_file_name_text = ctk.CTkLabel(master=self, text="Load from file: ")
        self.enter_file_name_text.grid(column=0, row=1, padx=20, pady=20)

        self.file_name_textbox = ctk.CTkTextbox(master=self)
        self.file_name_textbox.grid(column=1, row=1, padx=20, pady=20)

        self.back_button = ctk.CTkButton(master=self, text="Back",
                                         command=self.parent.make_join_dht_frame)
        self.back_button.grid(column=0, row=2, padx=20, pady=20)

        self.load_button = ctk.CTkButton(master=self, text="Load DHT",
                                         command=self.load_dht)
        self.load_button.grid(column=1, row=2, padx=20, pady=20)

    def load_dht(self):
        filename = self.file_name_textbox.get("0.0", "end")
        loaded_dht = dht.DHT.load(filename=filename)
        self.parent.dht = loaded_dht

        self.parent.make_network_page()



class JoinFrame(ctk.CTkFrame):
    """
      └── Join
          ├── Settings
          ├── Load an existing network
          └── Bootstrap into a new network
    """
    def __init__(self, parent: MainGUI, fg_color="transparent", **kwargs):
        ctk.CTkFrame.__init__(self, parent, **kwargs)

        self.configure(fg_color=fg_color)
        self.parent = parent

        join_title = ctk.CTkLabel(master=self, text="Join a Network", font=("Aharoni", 20, "bold"))
        join_title.pack(padx=50, pady=20)

        self.load_button = ctk.CTkButton(master=self, text="Load an existing network",
                                         command=self.parent.make_load_dht_frame)
        self.load_button.pack(padx=50, pady=10)

        self.bootstrap_button = ctk.CTkButton(master=self, text="Join a new network",
                                              command=self.handle_bootstrap_click)
        self.bootstrap_button.pack(padx=50, pady=10)

    def clear_screen(self):
        for child in self.winfo_children():
            child.destroy()

    def handle_bootstrap_click(self):
        # TODO: Create
        pass


class BootstrapFrame(ctk.CTkFrame):
    def __init__(self, root, **kwargs):
        
        ctk.CTkFrame.__init__(self, root, **kwargs)
        
        ip_text = ctk.CTkLabel(master=self, text="IP Address: ")
        ip_text.grid(row=0, column=0, padx=5, pady=10, sticky="nsew")
        
        self.IP_entry = ctk.CTkEntry(master=self, width=150)
        self.IP_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        port_text = ctk.CTkLabel(master=self, text="Port: ")
        port_text.grid(row=1, column=0, padx=5, pady=10, sticky="nsew")

        self.port_entry = ctk.CTkEntry(master=self, width=150)
        self.port_entry.grid(row=1, column=1, padx=5, pady=10, sticky="ew")

        self.connect_button = ctk.CTkButton(master=self, text="Connect",
                                            command=self.bootstrap)
        self.connect_button.grid(row=2, column=1, padx=5, pady=10)

    def bootstrap(self):
        """Attempts to bootstrap Kademlia connection from a given IP and port number"""
        print("[GUI] Connecting to bootstrap server...")


if __name__ == "__main__":
    # app = GUI()
    # app.load_bootstrap_window()
    # app.mainloop()

    app = MainGUI("light")
    app.mainloop()
    print("Done!")
