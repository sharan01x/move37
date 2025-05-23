![Move37 Logo](images/Move37Logo-BlueGreyBackground.png)

We are at the beginning of a new goal-based paradigm of computing where you can simply describe what you need done without having to think about the steps you need to perform in between to achieve that task. You can describe the "what", because computers are smart enough to figure out the "how" in order to perform the task. This project is an attempt to make that reality come true.

To begin with, this project offers some of the popular features that other commercial products are offering including taking down meeting notes as well as performing some tasks on the computer, but all run locally, with user privacy in mind.

There are numerous reasons for why this application is architected the way it is, ensuring that the data resides only on the user's computer within the user's control. Read more about that [here](https://redd.in/blog/the-age-of-goal-based-computing/)

This project is entirely free for personal use but is covered by a license to ensure fair commercial usage. Please review the license file (license.md) for further details.

## Features

### 1. The most powerful source for answers at the moment. Ask general questions, recall information from old conversations, do tasks that require the web, and more to come!     

![Ask Around](images/01-ThinkerApp.png)


### 2. Get quick answers from a general purpose AI model

![First Reponder](images/01-FirstResponder.png)


### 3. Calculate with accuracy, better than LLMs can

![Number Ninja](images/02-NumberNinja.png)


### 4. Tap into personal knowledge and get answers tailored to you

![Persephone](images/03-Persephone.png)


### 5. Upload your own files and ask questions of them

![Librarian](images/04-Librarian.png)


### 6. Make posting to all your social media accounts a breeze

![Butterfly](images/05-Butterfly.png)


### 7. Record anything, including meeting notes, document information or anything else and recall them when you need

![Submissions](images/06-Submissions.png)


### 8. View all the things recorded about you and delete anything, any time

![User Profile](images/07-UserProfile.png)


### 9. Upload your own files so you can ask any question about them

![Files](images/08-Files.png)


### 10. Dark mode, of course

![Dark Mode](images/10-DarkMode.png)


### 11. Mobile compatible

![Mobile View](images/11-MobileView.png)

---



## Quick Installation

Prerequisites -- you need Python 3.12 and Ollama installed on your local machine with Qwen2.5, mxbai-embed-large and phi4-mini installed. 
You also need to have `uv` installed. Visit https://github.com/astral-sh/uv for installation instructions.

1. Clone the repository and then go into that directory:
```bash
git clone https://github.com/sharan01x/move37.git
cd move37
```

2. Make the setup, upgrade and start shell scripts executable (Mac):
```bash
chmod +x setup.sh # Changed from setup_uv.sh
chmod +x upgrade.sh
chmod +x start.sh
```

3. If it's your first time using this application, run the setup script to install everything required:
```bash
./setup.sh # Changed from setup_uv.sh
```

But if you've been using the application and want to upgrade your app to the latest published version, run the below command:
```bash
./upgrade.sh
```
Don't worry this won't overwrite your data, but it may change your user name to the "default_user", so just change it back to the one you set in the user profile panel and your data will show up again.


4. Now, when you want to launch the application, do:
```bash
./start.sh
```
Point your browser to the address shown in the terminal, or to http://localhost:3737 if you're using it locally, and you're good to go!
---



## Manual Install (If Quick Install Doesn't Work)

1. Make sure you have Python 3.12 installed on your system. If you don't have python, go get it from their [website](https://www.python.org/downloads/)

2. Install `uv` from https://github.com/astral-sh/uv.

3. Install Ollama and Qwen2.5, mxbai-embed-large and phi4-mini AI models. Go to their website to [begin](https://ollama.com).

4. Clone the Move37 repository and then go into that directory:
```bash
git clone https://github.com/sharan01x/move37.git
cd move37
```

5. Create a virtual environment and install dependencies:
```bash
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```
You will need to install some depencies manually post that using the following command in the terminal:

```bash
python3.12 -m spacy download en_core_web_sm
```
If you run into issues, look at the instructions within requirements.txt for alternative ways to fix the install process.

6. Setup the launch script for easy launches in the future:
```bash
chmod +x start.sh
```

7. [OPTIONAL] For social media posting using Butterfly, you need the following two things:

a. A folder with the UI elements that need to be clicked to be able to post using the GUI. This is available for download from https://www.redd.in/resources.html.

b. A file with the social media account details at data/social_media/accounts.json. Use the following structure for the various supported platforms:

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

8. Launch the application in the future simply by using the following command:
```bash
./start.sh
```
Point your browser to the address shown in the terminal, or to http://localhost:3737 if you're using it locally, and you're good to go!
