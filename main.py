"""
Peer to Peer File Sharing System - Hierarchy Chart by ChatGPT
├── User Interface
│   ├── Main Menu
│   ├── Download Menu
│   ├── Upload Menu
│   ├── Search Menu
│   └── Shared Files Menu
├── Network Layer
│   ├── Peer Discovery
│   │   ├── Broadcasting to find peers
│   │   ├── Listening for messages that have been broadcast
│   │   ├── Establishing connections with peers
│   │   ├── Storing a list of connected peers
│   │   └── Removing disconnected peers from the list
│   ├── File Transfer
│   │   ├── Sending files to peers
│   │   ├── Receiving files from peers
│   │   ├── Tracking file transfer progress
│   │   └── Handling file transfer errors
│   └── Network Protocol
│       ├── Determining the message format
│       ├── Defining message types
│       ├── Sending and receiving messages
│       └── Handling message errors
└── File Management Layer
    ├── File Indexing
    │   ├── Scanning shared directories for files
    │   ├── Storing file metadata (e.g., name, size, hash)
    │   ├── Creating an index of shared files
    │   ├── Updating the index when files are added or removed
    │   └── Handling indexing errors
    ├── Search
    │   ├── Allowing users to search for shared files
    │   ├── Filtering search results based on user input
    │   └── Displaying search results to the user
    ├── Downloading
    │   ├── Allowing users to download shared files
    │   ├── Verifying the file hash to ensure integrity
    │   ├── Showing the download progress
    │   └── Handling download errors
    ├── Uploading
    │   ├── Allowing users to share files
    │   ├── Adding files to the shared directory
    │   ├── Updating the file index
    │   └── Sending file information to connected peers
    └── Shared Files
        ├── Displaying a list of shared files to the user
        ├── Showing file information (e.g., name, size, hash)
        ├── Allowing the user to remove shared files
        └── Handling file removal errors
"""
