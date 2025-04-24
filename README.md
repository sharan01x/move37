# Move 37

Move 37 is an AI memory assistant that helps you record, organize, and recall information and perform actions you want using your computer. This project is covered by a license. Please review the license file (license.md) for further details.

## Directory Structure

```
root/
├── app/                  # Main application code
│   ├── api/              # API endpoints
│   ├── agents/           # Agent implementations
│   ├── core/             # Core functionality and config
│   ├── database/         # Database interfaces
│   ├── models/           # Data models
│   ├── tools/            # Tools used by agents
│   └── utils/            # Utility functions
├── data/                 # All data storage
│   ├── vector_db/        # Vector database storage
│   │   ├── conversations/# Conversation vectors
│   │   ├── entities/     # Named entity vectors
│   │   └── metadata/     # Vector metadata
│   ├── user_context_db/  # User context database
│   └── user_data/        # User-specific data
├── tests/                # All test files
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── frontend/             # Frontend code
└── docs/                 # Documentation
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/lifescribe.git
cd lifescribe
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Run the application:
```bash
python main.py
```

4. Access the frontend:
```bash
cd frontend
python -m http.server 8080
```

<<<<<<< Updated upstream
=======
5. [OPTIONAL] For social media posting using Butterfly, you need the following two things:

a. A folder with the UI elements that need to be clicked to be able to post using the GUI. This is available for download from https://www.redd.in/move37/uielements
b. A file with the data/social_media/accounts.json file built with the following structure until a utility to manage this has been  built:

```
[
  {
    "id": "twitter_company1",
    "channel_id": "twitter",
    "name": "company1",
    "type": "company",     ///OPTIONS ARE company, personal, anonymous
    "character_limit": 280,
    "max_image_size": 5242880,
    "settings": {
      "api_key": "YOUR_API_KEY",
      "api_key_secret": "YOUR_API_KEY_SECRET",
      "access_token": "YOUR_ACCESS_TOKEN",
      "access_token_secret": "YOUR_ACCESS_TOKEN_SECRET",
      "posting_url": "https://x.com"
    }
  },
  {
    "id": "bluesky_company1",
    "channel_id": "bluesky",
    "name": "company1",
    "type": "company",
    "character_limit": 280,
    "settings": {
      "handle": "company1.bsky.social",
      "password": "YOUR_PASSWORD",
      "max_image_size": 1000000
    }
  },
  {
    "id": "lens_personal1",
    "channel_id": "lens",
    "name": "personal1",
    "type": "personal",
    "character_limit": 300,
    "settings": {
      "posting_url": "https://hey.xyz"
    }
  },
  {
    "id": "mastodon_personal1",
    "channel_id": "mastodon",
    "name": "personal1",
    "type": "personal",
    "character_limit": 300,
    "settings": {
      "access_token": "YOUR_ACCESS_TOKEN",
      "api_base_url": "https://mastodon.social",
      "redirect_uri": "http://localhost:5000/mastodon_callback",
      "max_image_size": 8388608
    }
  },
  {
    "id": "farcaster_personal1",
    "channel_id": "farcaster",
    "name": "personal1",
    "type": "personal",
    "character_limit": 280,
    "settings": {
      "mnemonic": "YOUR_MNEMONIC_PHRASE",
      "posting_url": "https://warpcast.com"
    }
  },
  {
    "id": "linkedin_personal1",
    "channel_id": "linkedin",
    "name": "personal1",
    "type": "personal",
    "character_limit": 3000,
    "settings": {
      "posting_url": "https://www.linkedin.com/feed/"
    }
  },
  {
    "id": "linkedin_company1",
    "channel_id": "linkedin",
    "name": "company1",
    "type": "company",
    "character_limit": 3000,
    "settings": {
      "posting_url": "https://www.linkedin.com/company/YOUR_COMPANY_ID/admin/page-posts/published/?share=true"
    }
  }
]
```



>>>>>>> Stashed changes
Then open your browser to http://localhost:3000

## Features

- Record and transcribe voice notes
- Extract named entities from text
- Search and recall information using natural language
- Specialized agents for different types of queries
- Web-based user interface

## Documentation

More detailed documentation is coming soon.


<<<<<<< Updated upstream
This project is licensed by Sharan Grandige (sharan@redd.in). Please review the license file for further details.

=======
>>>>>>> Stashed changes







# LifeScribe Application Architecture

## Core Components

### App.svelte
The main component that manages the application modes ('recall' or 'record') and renders the sidebar, chat interface, and user profile panel.

### UserProfile.svelte
Handles user ID management, storing it in localStorage, and manages user facts.

### ChatInterface.svelte
The primary chat UI that displays conversations and handles message sending. It includes:
- Message display with proper styling for different message types (user, agent, system)
- Input area with file attachment support
- Connection status indication
- Dark mode toggle

## WebSocket Implementation

The application uses two separate WebSocket connections:
- **Recall WebSocket** (recallWsService): For retrieving information and chat interactions
- **Record WebSocket** (recordWsService): For recording/storing information

The WebSocket implementation uses:
- **WebSocketService class**: A robust implementation handling:
  - Connections and reconnections with exponential backoff
  - Message sending/receiving
  - Error handling
- **Connection status management**: Tracks and displays the connection state to users
- **Message handlers**: Registers event handlers for different message types

## State Management (Svelte Stores)

### chatStore.ts
Manages:
- Message input and loading states
- Message creation and storage
- File attachments
- User ID

### agentsStore.ts
Handles:
- Multiple agent definitions (First Responder, Number Ninja, Persephone, etc.)
- Active agent selection
- Conversation history for each agent
- Message operations (add, clear)

### websocketStore.ts
Provides:
- WebSocket connection status
- Automatic reconnection logic
- Notification handling
- Message sending functions

## Communication Flow

1. User types a message in ChatInterface
2. Message is processed through `sendMessage()` function
3. Message is sent via WebSocket using `sendChatMessage()`
4. The appropriate WebSocket service handles the delivery
5. Response messages from the server are processed by registered handlers
6. Messages are displayed in the chat interface

## Features

- **Multi-agent support**: Users can interact with different specialized agents
- **Real-time communication**: WebSocket ensures instant message delivery and responses
- **Offline resilience**: Reconnection handling with exponential backoff
- **File attachments**: Support for sending files through the chat interface
- **User identity management**: Persistent user ID stored in localStorage
- **Dark mode**: Toggleable theme support
- **Responsive design**: Mobile-friendly with special handling for iOS devices