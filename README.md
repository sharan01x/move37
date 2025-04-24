# Move 37

Move 37 is an AI assistant that helps you record, organize, and recall information and perform actions you want using your own computer. 

This project is covered by a license. Please review the license file (license.md) for further details.

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
git clone https://github.com/sharan01x/move37.git
cd move37
```

2. Check configuration file for the right paths or to change the AI models that you prefer to use. Leave this as is if you want to use the default settings, in which case, ,make sure you already have Ollama installed and running Qwen2.5, mxbai-embed-large and phi4-mini. 

3. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```
You will need to install some depencies manually, and they are detailed in the requirements.txt file.


4. Run the application:
```bash
python main.py --host 0.0.0.0
```

5. Access the frontend:
```bash
cd frontend
python -m http.server 3000
```

6. [OPTIONAL] For social media posting using Butterfly, you need the following two things:
a. A folder with the UI elements that need to be clicked to be able to post using the GUI. This is available for download from https://www.redd.in/move37/uielements
b. A file with the social media account details at data/social_media/accounts.json. You can have one or more accounts use the following structure for the various supported platforms:

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

Then open your browser to http://localhost:3000

## Documentation

More detailed documentation is coming soon.


## Features

- **Multi-agent support**: Users can interact with different specialized agents
- **Real-time communication**: WebSocket ensures instant message delivery and responses
- **Offline resilience**: Reconnection handling with exponential backoff
- **File attachments**: Support for sending files through the chat interface
- **User identity management**: Persistent user ID stored in localStorage
- **Dark mode**: Toggleable theme support
- **Responsive design**: Mobile-friendly with special handling for iOS devices