#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Social Media Posting Tools for CrewAI Agents.

This module provides tools for posting text content to various social media platforms
using GUI automation, adapted from the reference auto_poster_tool.py.
"""

# Placeholder for imports that will be needed
import os
import time
import webbrowser
import pyautogui
import json
from PIL import Image
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from crewai.tools import BaseTool

# --- Placeholder for Settings Management ---
# This needs to be replaced with actual settings management logic
# For now, it returns dummy data.

class DummySettings:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    # Allow dictionary-like access for compatibility if needed
    def get(self, key, default=None):
        return getattr(self, key, default)

def get_user_accounts(user_id: str, account_type: str = None, channel: str = None) -> Dict[str, Dict[str, Any]]:
    """
    Loads social media accounts for a user from their accounts.json file with optional filtering.

    Args:
        user_id: The ID of the user.
        account_type: Optional filter to only return accounts of this type.
        channel: Optional filter to only return accounts for this channel/platform.

    Returns:
        A dictionary of account dictionaries with account names as keys or an empty dictionary
        if no accounts match the criteria or the file is not found/invalid.
    """
    settings_file = os.path.join("data", "social_media", user_id, "accounts.json")

    print(f"[Settings] Attempting to load accounts from: {settings_file}")

    if not os.path.exists(settings_file):
        print(f"[Settings] Error: Settings file not found at {settings_file}")
        return {}

    try:
        with open(settings_file, 'r') as f:
            all_accounts_data = json.load(f)

        # Clean up all account fields for robust matching
        def clean(val):
            return str(val).strip().lower() if isinstance(val, str) else val

        filtered_accounts = []
        for acc in all_accounts_data:
            acc_type = clean(acc.get("type", ""))
            acc_channel = clean(acc.get("channel_id", ""))
            acc_name = acc.get("name", "")
            # Apply filters if present
            if clean(account_type) is not None and clean(account_type) != acc_type:
                continue
            if clean(channel) is not None and clean(channel) != acc_channel:
                continue
            # Always strip spaces from name for keys
            acc["name"] = acc_name.strip() if isinstance(acc_name, str) else acc_name
            filtered_accounts.append(acc)

        # Convert to dictionary with account names as keys
        accounts_dict = {acc["name"]: acc for acc in filtered_accounts if acc.get("name")}

        print(f"[Settings] Successfully loaded {len(accounts_dict)} account(s) matching criteria for user {user_id}")
        return accounts_dict

    except json.JSONDecodeError:
        print(f"[Settings] Error: Invalid JSON format in {settings_file}")
        return {}
    except Exception as e:
        print(f"[Settings] Error loading accounts from {settings_file}: {e}")
        import traceback
        traceback.print_exc()
        return {}

def _get_settings(user_id: str, platform: str, account_name: str) -> Optional[Dict[str, Any]]:
    """Loads settings for a specific account and platform from accounts.json."""
    
    settings_file = os.path.join("data", "social_media", user_id, "accounts.json")
    ui_base_path = os.path.join("data", "social_media", user_id, "ui_elements")

    print(f"[Settings] Attempting to load settings from: {settings_file}")

    if not os.path.exists(settings_file):
        print(f"[Settings] Error: Settings file not found at {settings_file}")
        return None

    try:
        with open(settings_file, 'r') as f:
            all_accounts_data = json.load(f)

        found_account = None
        for acc_data in all_accounts_data:
            # Match based on platform (channel_id) and account name
            if acc_data.get("channel_id") == platform and acc_data.get("name") == account_name:
                found_account = acc_data
                break

        if not found_account:
            print(f"[Settings] Error: No account found for name '{account_name}' on platform '{platform}' in {settings_file}")
            return None

        # Reconstruct the nested structure expected by posters using DummySettings
        # Convert nested dictionaries back into DummySettings objects for attribute access
        account_obj = DummySettings(**found_account)
        for key, value in found_account.items():
            if key.endswith("_settings") and isinstance(value, dict):
                setattr(account_obj, key, DummySettings(**value))

        # Create a basic channel object (can be expanded later if needed)
        # Max image size can be standardized or loaded from a different config if needed
        channel_obj = DummySettings(id=platform, enabled=True, max_image_size=5*1024*1024) # Default 5MB

        # Add the user-specific UI path to the account object
        setattr(account_obj, 'ui_base_path', ui_base_path)

        print(f"[Settings] Successfully loaded settings for {account_name} on {platform}")
        print(f"[Settings] Determined UI base path: {ui_base_path}")
        return {
            "channel": channel_obj,
            "account": account_obj
        }

    except json.JSONDecodeError:
        print(f"[Settings] Error: Invalid JSON format in {settings_file}")
        return None
    except Exception as e:
        print(f"[Settings] Error loading or processing settings from {settings_file}: {e}")
        import traceback
        traceback.print_exc()
        return None



# Simplified PostVariant for text-only posts initially
class PostVariant:
    def __init__(self, platform: str, account_name: str, content: str, image_path: Optional[str] = None):
        self.platform = platform
        self.account_name = account_name
        self.content = content
        self.image_path = image_path

class PlatformPoster:
    """Base class for platform-specific posting strategies (Adapted)"""
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings  # <--- Fix: Store settings as instance attribute
        # Retrieve UI path from settings, with a default fallback
        default_ui_path = "UI" # Default if not found in settings
        if settings and settings.get('account') and hasattr(settings['account'], 'ui_base_path'):
            self.ui_base_path = settings['account'].ui_base_path
            print(f"[PlatformPoster Init] Using UI path from settings: {self.ui_base_path}")
        else:
            self.ui_base_path = default_ui_path
            print(f"[PlatformPoster Init] UI path not found in settings, using default: {self.ui_base_path}")

    def resize_image_for_channel(self, image_path: str, max_size_bytes: int) -> str:
        """
        Resize an image to meet the channel's max size limit. (Copied)
        NOTE: This is kept for completeness but not used in initial text-only tools.
        """
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        directory = os.path.dirname(image_path)
        filename = os.path.basename(image_path)
        name, ext = os.path.splitext(filename)
        resized_path = os.path.join(directory, f"{name}_resized{ext}")

        try:
            with Image.open(image_path) as img:
                quality = 95
                if img.mode == 'RGBA':
                    img = img.convert('RGB')

                img.save(resized_path, quality=quality, optimize=True)
                current_size = os.path.getsize(resized_path)

                if current_size <= max_size_bytes:
                    return resized_path

                scale = (max_size_bytes / current_size) ** 0.5

                while current_size > max_size_bytes and (quality > 30 or scale > 0.1):
                    if quality > 30 and current_size > max_size_bytes * 1.2:
                        quality -= 5
                    else:
                        scale *= 0.9

                    new_width = int(img.width * scale)
                    new_height = int(img.height * scale)

                    if new_width < 100 or new_height < 100:
                        # Stop if dimensions become too small, even if size is still too large
                        print(f"[Resize] Warning: Could not resize below {new_width}x{new_height} while maintaining quality/scale constraints.")
                        break

                    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    resized_img.save(resized_path, quality=quality, optimize=True)
                    current_size = os.path.getsize(resized_path)

                    if current_size <= max_size_bytes:
                        return resized_path

            if current_size > max_size_bytes:
                 # If loop finished and still too large, raise error or return original?
                 # For now, let's raise to signal failure clearly.
                 raise ValueError(f"Could not resize image {filename} below {max_size_bytes} bytes. Final size: {current_size}")

            return resized_path
        except Exception as e:
            print(f"[Resize] Error resizing image {image_path}: {e}")
            # Raise the error to be caught by the calling post method
            raise

    def find_on_screen(self, image_name: str, move: bool = False, click: bool = False, double_click: bool = False, confidence=0.8, search_area=None) -> bool:
        """
        Helper method to find UI elements on screen. (Adapted for path handling)

        Args:
            image_name: Base name of the image file (e.g., 'TwitterPostButton.png')
            click: Whether to click the element if found
            move: Whether to move to the element if found
            double_click: Whether to double click the element if found
            confidence: Confidence level for pyautogui image recognition.

        Returns:
            bool: True if the element was found and actions were performed successfully
        """
        
        # Use the ui_base_path stored during initialization
        if not os.path.isdir(self.ui_base_path):
            print(f"[Find on Screen] Error: Configured UI directory not found at: {os.path.abspath(self.ui_base_path)}")
            return False # Cannot proceed without UI assets

        folders = ["retina", "regular", "retina compact"]
        now = datetime.now()
        # Adjust hours if needed, reference used >= 18 or < 9, let's stick to that
        if now.hour >= 18 or now.hour < 9:
            folders.insert(1, "retina dark")
            folders.insert(3, "regular dark")

        for folder in folders:
            # Construct the full path to the image asset
            image_path = os.path.join(self.ui_base_path, folder, image_name)
            # print(f"[Find on Screen] Trying to find {image_path}") # Verbose

            scale = 0.5 if "retina" in folder else 1.0

            if not os.path.exists(image_path):
                # print(f"[Find on Screen] Image path does not exist: {image_path}") # Verbose
                continue

            try:
                # Using locateCenterOnScreen for coordinates
                search_region = self.get_region(search_area, scale)
                location = pyautogui.locateCenterOnScreen(image_path, confidence=confidence, region=search_region)
                if location:
                    x, y = location
                    x = int(x * scale)
                    y = int(y * scale)
                    print(f"[Find on Screen] Found '{image_name}' in '{folder}' at scaled coordinates: ({x}, {y})")
                    if move or click or double_click: # Move before clicking/double-clicking
                         pyautogui.moveTo(x, y, duration=0.2, tween=pyautogui.easeOutQuad) # Small duration for smoother move
                         time.sleep(0.1) # Pause after moving
                    if click:
                        pyautogui.click(x, y)
                        print(f"[Find on Screen] Clicked at ({x}, {y})")
                    elif double_click: # Use elif because double_click implies click
                        pyautogui.doubleClick(x, y)
                        print(f"[Find on Screen] Double-clicked at ({x}, {y})")
                    return True
            except pyautogui.ImageNotFoundException:
                # print(f"[Find on Screen] Image not found on screen: {image_path}") # Verbose
                continue
            except Exception as e:
                 print(f"[Find on Screen] Error processing {image_path}: {e}")
                 # Potentially permissions errors or other pyautogui issues
                 continue # Try next folder

        print(f"[Find on Screen] Element '{image_name}' not found on screen after checking all folders.")
        return False
    
    def get_region(self, region_name=None, scale=1):
        window_width, window_height = pyautogui.size()
        window_width = int(window_width / scale)
        window_height = int(window_height / scale)
    
        # Map region names to coordinates, including None as the default (full screen)
        region_map = {
            None: (0, 0, window_width, window_height),
            'top-left': (0, 0, window_width // 2, window_height // 2),
            'top-right': (window_width // 2, 0, window_width // 2, window_height // 2),
            'bottom-left': (0, window_height // 2, window_width // 2, window_height // 2),
            'bottom-right': (window_width // 2, window_height // 2, window_width // 2, window_height // 2),
            'left': (0, 0, window_width // 2, window_height),
            'right': (window_width // 2, 0, window_width // 2, window_height),
            'top': (0, 0, window_width, window_height // 2),
            'bottom': (0, window_height // 2, window_width, window_height // 2)
        }
        # Fallback to full area if quadrant is not recognized
        search_region = region_map.get(region_name, region_map[None])
    
        print(f"[Get Region] Searching in '{region_name}' region: {search_region}")
    
        return search_region

    def post(self, content: str, variant: PostVariant, settings: dict) -> Tuple[bool, Optional[str]]:
        """Post content to platform. To be implemented by subclasses."""
        raise NotImplementedError






# --- Platform Specific Posters ---

class LinkedInPoster(PlatformPoster):
    
    # The data structure for LinkedIn accounts is as follows:
    # {
    #     "id": "linkedin_sharanx",
    #     "channel_id": "linkedin",
    #     "name": "sharanx",
    #     "type": "personal",
    #     "character_limit": 300,
    #     "settings": {
    #         "posting_url": "https://www.linkedin.com/feed/"
    #     }
    # }

    # OR, for company types:
    # {
    #     "id": "linkedin_reddxf",
    #     "channel_id": "linkedin",
    #     "name": "reddxf",
    #     "type": "company",
    #     "character_limit": 300,
    #     "settings": {
    #         "posting_url": "https://www.linkedin.com/company/13380986/admin/page-posts/published/?share=true"
    #     }
    # }
    
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        super().__init__(settings=settings)

    def post(self, content: str, variant: PostVariant, settings: dict) -> Tuple[bool, Optional[str]]:
        account = settings.get("account")
        if not account or not hasattr(account, 'type'):
            print("[LinkedIn] Error: No account or no type in account.", account)
            return False, "Invalid or missing LinkedIn account."
        if account.type == "company":
            return self._post_to_company(content, variant, settings)
        else: # If it's "personal" or any other type, we will just use the personal posting method to be safe
            return self._post_to_personal(content, variant, settings)
            
    def _post_to_personal(self, content: str, variant: PostVariant, settings: dict) -> Tuple[bool, Optional[str]]:
        account = settings.get("account")
        try:
            print("[LinkedIn Personal] Starting GUI automation...")
            import webbrowser
            import time
            import pyautogui
            import os

            posting_url = account.settings.get("posting_url")
            if not posting_url:
                print("[LinkedIn Personal] Error: Posting URL not found in account settings:", account.settings)
                return False, "Posting URL not found in settings"

            print(f"[LinkedIn Personal] Opening browser with URL: {posting_url}")
            webbrowser.open(posting_url)
            print("[LinkedIn Personal] Waiting for browser window...")
            time.sleep(3)

            # Locate the posting area and click into it
            if not self.find_on_screen('LinkedInPersonalStartAPost.png', click=True):
                print("[LinkedIn Personal] Error: Posting area not found")
                return False, "Posting area not found on screen"

            time.sleep(2)
            # Type content
            print(f"[LinkedIn Personal] Writing post content: {content[:50]}...")
            pyautogui.write(content, interval=0.025)
            time.sleep(3)

            if variant.image_path:
                print(f"[LinkedIn Personal] Post includes image: {variant.image_path}")
                full_image_path = variant.image_path
                if not os.path.exists(full_image_path):
                    print(f"[LinkedIn Personal] Image not found: {full_image_path}")
                    return False, "[LinkedIn Personal] Image not found."
                if self.find_on_screen('LinkedInMediaButton.png', click=True):
                    time.sleep(3)
                    print("[LinkedIn Personal] Opening file dialog...")
                    pyautogui.hotkey('command', 'shift', 'g')
                    print(f"[LinkedIn Personal] Writing image path: {full_image_path}")
                    pyautogui.write(full_image_path)
                    pyautogui.press('enter')
                    time.sleep(2)
                    print("[LinkedIn Personal] Confirming file selection...")
                    pyautogui.press('enter')
                    time.sleep(3)

                    # Click the Next button
                    if not self.find_on_screen('LinkedInNextButton.png', click=True):
                        print("[LinkedIn Personal] Error: Next button not found")
                        return False, "Next button not found on screen"

                else:
                    print("[LinkedIn Personal] Error: Media button not found")
                    # But it's possible that the media button is not present because the post contains a link and therefore a preview is already shown, so just continue to the next step
                    pass

            # Click the Post button
            if not self.find_on_screen('LinkedInPostButton.png', click=True):
                print("[LinkedIn Personal] Error: Post button not found")
                return False, "Post button not found on screen"

            time.sleep(4)
            print("[LinkedIn Personal] Closing browser window...")
            pyautogui.hotkey('command', 'w')
            print("[LinkedIn Personal] Post completed successfully")
            return True, "[LinkedIn Personal] Post completed successfully"
        except Exception as e:
            print(f"[LinkedIn Personal] Error during GUI automation: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"GUI automation error: {str(e)}"

    def _post_to_company(self, content: str, variant: PostVariant, settings: dict) -> Tuple[bool, Optional[str]]:
        account = settings.get("account")
        try:
            print("[LinkedIn Company] Starting GUI automation...")
            import webbrowser
            import time
            import pyautogui
            import os

            posting_url = account.settings.get("posting_url")
            if not posting_url:
                print("[LinkedIn Company] Error: Posting URL not found in account settings:", account.settings)
                return False, "Posting URL not found in settings"
            print(f"[LinkedIn Company] Opening browser with URL: {posting_url}")
            webbrowser.open(posting_url)
            print("[LinkedIn Company] Waiting for browser window and page load...")
            time.sleep(5)  # Increased wait time for page load

            # Type content
            print(f"[LinkedIn Company] Writing post content: {content[:50]}...")
            pyautogui.write(content, interval=0.025)
            time.sleep(2)
            if variant.image_path:
                print(f"[LinkedIn Company] Post includes image: {variant.image_path}")
                full_image_path = variant.image_path
                if not os.path.exists(full_image_path):
                    print(f"[LinkedIn Company] Image not found: {full_image_path}")
                    return False, "[LinkedIn Company] Image not found."
                if not self.find_on_screen('LinkedInMediaButton.png', click=True):
                    print("[LinkedIn Company] Error: Media button not found")
                    return False, "Media button not found on screen"
                
                time.sleep(2)
                print("[LinkedIn Company] Opening file dialog...")
                pyautogui.hotkey('command', 'shift', 'g')
                print(f"[LinkedIn Company] Writing image path: {full_image_path}")
                pyautogui.write(full_image_path)
                pyautogui.press('enter')
                time.sleep(1)
                print("[LinkedIn Company] Confirming file selection...")
                pyautogui.press('enter')
                time.sleep(2)

                # Click the Next button
                if not self.find_on_screen('LinkedInNextButton.png', click=True):
                    print("[LinkedIn Company] Error: Next button not found")
                    return False, "Next button not found on screen"

            # Click the Post button
            if not self.find_on_screen('LinkedInPostButton.png', click=True):
                print("[LinkedIn Company] Error: Post button not found")
                return False, "Post button not found on screen"

            time.sleep(5)
            print("[LinkedIn Company] Closing browser window...")
            pyautogui.hotkey('command', 'w')
            print("[LinkedIn Company] Post completed successfully")
            return True, "[LinkedIn Company] Post completed successfully"
        except Exception as e:
            print(f"[LinkedIn Company] Error during GUI automation: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"GUI automation error: {str(e)}"

class FarcasterPoster(PlatformPoster):
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        super().__init__(settings=settings)

    def post(self, content: str, variant: PostVariant, settings: dict) -> Tuple[bool, Optional[str]]:
        
        account = settings.get("account")
        if not account.settings.get("mnemonic"):
            print("[Farcaster] Error: Account mnemonic not found in settings:", account.settings)
            return False, "Farcaster mnemonic not found in account settings"

        # If there is an image, use GUI automation (Warpcast web)
        if variant.image_path:
            return self._post_with_gui(content, variant.image_path, account.settings)
        else:
            try:
                from farcaster import Warpcast
                client = Warpcast(account.settings["mnemonic"])
                if not client.get_healthcheck():
                    print("[Farcaster] Error: Failed to connect to Farcaster API")
                    return False, "Failed to connect to Farcaster API"
                client.post_cast(text=content)
                print("[Farcaster] Post completed successfully (API)")
                return True, "[Farcaster] Post completed successfully (API)"
            except Exception as e:
                print(f"[Farcaster] Error posting via API: {e}")
                import traceback
                traceback.print_exc()
                return False, str(e)


    def _post_with_gui(self, content: str, image_path: str, settings: dict) -> Tuple[bool, Optional[str]]:
        try:
            print("[Farcaster] Starting GUI automation...")
            import webbrowser
            import time
            import pyautogui

            posting_url = settings.get("posting_url")
            if not posting_url:
                print("[Farcaster] Error: No posting_url found in settings:", settings)
                return False, "Posting URL not found in settings"

            browser = webbrowser.get()
            browser.open(posting_url)
            time.sleep(10)

            # Click the "Cast" button
            if not self.find_on_screen('WarpcastCastButton.png', click=True):
                print("[Farcaster] Error: Cast button not found")
                return False, "Cast button not found on screen"
            time.sleep(3)

            # Write the post content
            pyautogui.write(content, interval=0.025)

            if image_path:
                # Click the media button
                if not self.find_on_screen('WarpcastMediaButton.png', click=True):
                    print("[Farcaster] Error: Media button not found")
                    return False, "Media button not found on screen"
                time.sleep(3)
                pyautogui.hotkey('command', 'shift', 'g')
                pyautogui.write(image_path)
                pyautogui.press('enter')
                time.sleep(2)
                pyautogui.press('enter')
                time.sleep(4)
                self.find_on_screen('WarpcastPostCastButton.png', click=True)
            else:
                self.find_on_screen('WarpcastPostCastButton.png', click=True)
            time.sleep(3)
            
            pyautogui.hotkey('command', 'w')
            print("[Farcaster] Post completed successfully (GUI)")
            return True, "[Farcaster] Post completed successfully (GUI)"

        except Exception as e:
            print(f"[Farcaster] Error during GUI automation: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"GUI automation error: {str(e)}"


class MastodonPoster(PlatformPoster):

    # The data is stored like this below in accounts.json:
    #   {
    #     "id": "mastodon_sharanx",
    #     "channel_id": "mastodon",
    #     "name": "sharanx",
    #     "type": "personal",
    #     "character_limit": 300,
    #     "settings": {
    #       "access_token": "tWWYpWE",
    #       "api_base_url": "https://mastodon.social",
    #       "redirect_uri": "http://localhost:5000/mastodon_callback",
    #       "max_image_size": 8388608
    #     }
    #   }
    
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        super().__init__(settings=settings)
    
    def post(self, content: str, variant: PostVariant, settings: dict) -> Tuple[bool, Optional[str]]:
        try:
            print("[Mastodon] Starting post process...")
            
            # Get account settings
            account = settings.get("account")
            if not account or not account.settings:
                print("[Mastodon] Error: Account settings not found:", account)
                raise ValueError("No Mastodon account configured")

            from mastodon import Mastodon
            client = Mastodon(
                access_token=account.settings["access_token"],
                api_base_url=account.settings["api_base_url"]
            )

            # Handle image if present
            image_path = None  # Always initialize
            if variant.image_path:
                print(f"[Mastodon] Processing image: {variant.image_path}")
                image_path = self.resize_image_for_channel(variant.image_path, account.settings['max_image_size'])

            # Create post
            print(f"[Mastodon] Creating post: {content[:50]}...")
            if image_path:
                print("[Mastodon] Uploading media...")
                media = client.media_post(image_path)
                print("[Mastodon] Media uploaded successfully, posting with media...")
                response = client.status_post(content, media_ids=[media['id']])
                print("[Mastodon] Successfully posted with image")
            else:
                print("[Mastodon] Posting without media...")
                response = client.status_post(content)
                print("[Mastodon] Successfully posted text")

            # Clean up resized image if it was created
            if image_path and image_path != variant.image_path:
                try:
                    print(f"[Mastodon] Cleaning up resized image: {image_path}")
                    os.remove(image_path)
                    print("[Mastodon] Successfully cleaned up resized image")
                except Exception as e:
                    print(f"[Mastodon] Error cleaning up resized image: {e}")
                    import traceback
                    print("[Mastodon] Full error traceback:")
                    traceback.print_exc()

            print("[Mastodon] Post completed successfully")
            return True, "[Mastodon] Post completed successfully"

        except Exception as e:
            print(f"[Mastodon] Error creating post: {str(e)}")
            import traceback
            print("[Mastodon] Full error traceback:")
            traceback.print_exc()
            return False, str(e)


class BlueSkyPoster(PlatformPoster):

    # The data is stored like this below in accounts.json:
    #   {
    #     "id": "bluesky_reddxf.bsky.social",
    #     "channel_id": "bluesky",
    #     "name": "reddxf",
    #     "type": "company",
    #     "character_limit": 280,
    #     "settings": {
    #       "handle": "reddxf.bsky.social",
    #       "password": "Tacky7",
    #       "max_image_size": 4194304
    #     }
    #   }
    
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        super().__init__(settings=settings)

    def post(self, content: str, variant: PostVariant, settings: dict) -> Tuple[bool, Optional[str]]:
        try:
            print("[BlueSky] Starting post process...")
            
            # Get account settings
            account = settings.get("account")
            if not account or not account.settings:
                print("[BlueSky] Error: Account settings not found:", account)
                raise ValueError("No Bluesky account configured")

            print(f"[BlueSky] Initializing client for handle: {account.settings['handle']}")    
            # Initialize client
            from atproto import Client
            client = Client()
            client.login(account.settings['handle'], account.settings['password'])
            print("[BlueSky] Successfully logged in")

            # Handle image if present
            image_path = None  # Ensure always initialized
            if variant.image_path:
                print(f"[BlueSky] Processing image: {variant.image_path}")
                image_path = self.resize_image_for_channel(variant.image_path, account.settings['max_image_size'])

            # Create post
            if image_path:
                print(f"[BlueSky] Creating post with image: {image_path}")
                print(f"[BlueSky] Post content: {content[:50]}...")
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                response = client.send_image(text=content, image=image_data, image_alt='Uploaded image')
                print("[BlueSky] Successfully posted with image")
            else:
                print("[BlueSky] Creating text-only post")
                print(f"[BlueSky] Post content: {content[:50]}...")
                response = client.send_post(text=content)
                print("[BlueSky] Successfully posted text")

            # Clean up resized image if it was created
            if image_path and image_path != variant.image_path:
                try:
                    print(f"[BlueSky] Cleaning up resized image: {image_path}")
                    os.remove(image_path)
                    print("[BlueSky] Successfully cleaned up resized image")
                except Exception as e:
                    print(f"[BlueSky] Error cleaning up resized image: {str(e)}")
                    import traceback
                    print("[BlueSky] Full error traceback:")
                    traceback.print_exc()

            print("[BlueSky] Post completed successfully")
            return True, "[BlueSky] Post completed successfully"

        except Exception as e:
            print(f"[BlueSky] Error during posting: {str(e)}")
            import traceback
            print("[BlueSky] Full error traceback:")
            traceback.print_exc()
            return False, str(e)


class LensPoster(PlatformPoster):
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        super().__init__(settings=settings)

    def post(self, content: str, variant: PostVariant, settings: dict) -> Tuple[bool, Optional[str]]:
        # Prefer instance settings, fallback to argument
        effective_settings = self.settings if self.settings is not None else settings
        try:
            return self._post_with_gui(content, variant, effective_settings)
        except Exception as e:
            print(f"[Lens] Exception in LensPoster: {str(e)}")
            return False, f"GUI automation error: {str(e)}"

    def _post_with_gui(self, content: str, variant: PostVariant, settings: dict) -> Tuple[bool, Optional[str]]:
        try:
            print("[Lens] Starting GUI automation...")

            # Get account settings
            account = settings.get("account")
            print("[Lens] Found account:", account)
            if not account or not getattr(account, 'settings', None):
                print("[Lens] Error: Account settings not found. Account:", account)
                print("[Lens] Account settings:", getattr(account, 'settings', None) if account else None)
                return False, "No Lens account configured"

            if not account.settings.get('posting_url'):
                print("[Lens] Error: Posting URL not found in settings:", account.settings)
                return False, "Posting URL not found in settings"

            posting_url = account.settings['posting_url']
            print(f"[Lens] Opening browser with URL: {posting_url}")
            webbrowser.open(posting_url)
            print("[Lens] Waiting for browser window...")
            time.sleep(3)

            # Locate the posting area and click into it
            if not self.find_on_screen('HeyPostingArea.png', click=True, search_area='top-left'):
                print("[Lens] Error: Posting area not found")
                return False, "Posting area not found on screen"

            time.sleep(2)
            pyautogui.write(content, interval=0.025)
            time.sleep(2)

            if variant.image_path:

                print(f"[Lens] Post includes image: {variant.image_path}")
                
                # The image should be in the temporary_uploads folder, confirm it exists
                if not os.path.exists(variant.image_path):
                    print(f"[Lens] Image not found: {variant.image_path}")
                    return False, "[Lens] Image not found."

                # Click the media button
                if not self.find_on_screen('HeyMediaButton.png', click=True):
                    print("[Lens] Error: Media button not found")
                    return False, "Media button not found on screen"

                # Click the Upload images button
                if not self.find_on_screen('HeyUploadImageButton.png', click=True):
                    print("[Lens] Error: Upload button not found")
                    return False, "Upload button not found on screen"

                # Wait for the file dialog to open
                time.sleep(2)
                print("[Lens] Opening file dialog...")
                pyautogui.hotkey('command', 'shift', 'g')  # Go to the folder path
                print(f"[Lens] Writing image path: {variant.image_path}")
                pyautogui.write(variant.image_path)  # Write the file path
                pyautogui.press('enter')
                time.sleep(2)
                print("[Lens] Confirming file selection...")
                pyautogui.press('enter')  # This uploads the media
                time.sleep(6)

            # Click the Post button
            if not self.find_on_screen('HeyPostButton.png', click=True):
                print("[Lens] Error: Post button not found")
                return False, "Post button not found on screen"

            time.sleep(4)
            print("[Lens] Closing browser window...")
            pyautogui.hotkey('command', 'w')
            print("[Lens] Post completed successfully")
            return True, "[Lens] Post completed successfully"

        except Exception as e:
            print(f"[Lens] Error during GUI automation: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"GUI automation error: {str(e)}"


class TwitterPoster(PlatformPoster):
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        """Initialize TwitterPoster, calling the base class initializer."""
        super().__init__(settings=settings)

    def post(self, content: str, variant: PostVariant, settings: dict) -> Tuple[bool, str]:
        """
        Posts to Twitter using API for text-only, GUI automation if image is present.
        Returns (success, message) where message is user-facing and context-aware.
        """
        try:
            if variant.image_path:  # Use GUI if image is present
                return self._post_with_gui(content, variant, settings)
            else:  # Use API for text-only
                return self._post_with_api(content, variant, settings)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[Twitter] Exception in TwitterPoster: {str(e)}")
            return False, f"[Twitter] Exception in TwitterPoster: {str(e)}"

    def _post_with_api(self, content: str, variant: PostVariant, settings: dict) -> Tuple[bool, str]:
        try:
            account = settings.get("account")
            twitter_settings = getattr(account, "settings", None) if account else None
            if not twitter_settings:
                return False, "[Twitter] No account configured (API)"

            api_key = twitter_settings.get("api_key") if twitter_settings else None
            api_key_secret = twitter_settings.get("api_key_secret") if twitter_settings else None
            access_token = twitter_settings.get("access_token") if twitter_settings else None
            access_token_secret = twitter_settings.get("access_token_secret") if twitter_settings else None

            if not all([api_key, api_key_secret, access_token, access_token_secret]):
                return False, "[Twitter] Incomplete Twitter API credentials (API)"

            import tweepy
            client = tweepy.Client(
                consumer_key=api_key,
                consumer_secret=api_key_secret,
                access_token=access_token,
                access_token_secret=access_token_secret
            )
            client.create_tweet(text=content)
            return True, f"[Twitter] Successfully posted to account '{variant.account_name}' via API."
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[Twitter] Failed to post to account '{variant.account_name}' via API: {str(e)}")
            return False, f"[Twitter] Failed to post to account '{variant.account_name}' via API: {str(e)}"

    def _post_with_gui(self, content: str, variant: PostVariant, settings: dict) -> Tuple[bool, str]:
        try:
            account_settings = settings.get("account")
            if not account_settings or not getattr(account_settings, 'settings', None):
                return False, "[Twitter] Account settings not configured (GUI)"

            twitter_config = account_settings.settings
            if not twitter_config.get('posting_url'):
                return False, "[Twitter] Posting URL not found in settings (GUI)"

            webbrowser.open(twitter_config['posting_url'])
            time.sleep(6) # Increased wait for page load

            accountImage = 'TwitterAccountsButton-' + variant.account_name + '.png'

            if not self.find_on_screen(accountImage, move=True, search_area='bottom-left'):
                if not self.find_on_screen('TwitterAccountSelector.png', click=True, search_area='bottom-left'):
                    return False, "Unable to find the account selector to switch accounts (GUI)."
                time.sleep(3)
                if not self.find_on_screen(accountImage, click=True, search_area='bottom-left'):
                    return False, f"Unable to switch to the account: {variant.account_name} (GUI)."
                time.sleep(3)

            # Compose Tweet
            # Keyboard shortcut for the compose window is "N"
            pyautogui.press('n')
            time.sleep(2)

            # Write Content
            time.sleep(2) # Wait for focus
            pyautogui.write(content + " ", interval=0.025) # Space needed per reference comment
            time.sleep(1)   

            # If there's an image_path specified, then look for the image and upload it
            if variant.image_path:

                # The image should be in the temporary_uploads folder, confirm it exists
                if not os.path.exists(variant.image_path):
                    return False, "[Twitter] Image not found."
                
                # Resize the image to the max size allowed by the platform
                full_image_path = self.resize_image_for_channel(variant.image_path, settings.get("channel").max_image_size)

                if not self.find_on_screen('TwitterMediaButton.png', double_click=True):
                    return False, "[Twitter] Could not find media button."
                
                # Wait for the file dialog to open
                time.sleep(3)
                
                # Close the file dialog (some Mac issue)
                pyautogui.press('escape')
                time.sleep(2)

                if self.find_on_screen('MacOSFileDialogOpenButtonInactive.png', move=True, search_area='bottom-right'):
                    pyautogui.press('enter')
                    time.sleep(2)
                    pyautogui.press('enter')

                    # Write the image file path
                    pyautogui.hotkey('command', 'shift', 'g')   
                    pyautogui.write(variant.image_path)
                    time.sleep(2)

                    pyautogui.press('enter')
                    time.sleep(2)
                    pyautogui.press('enter')
                    time.sleep(4)
                else:
                    return False, "[Twitter] Unable to find the file dialog"
            
            # # Click Final Post Button
            if not self.find_on_screen('TwitterMessagePostButton.png', click=True):
                # Attempt Esc + close as cleanup
                pyautogui.press('escape')
                time.sleep(1)
                pyautogui.hotkey('command', 'w')
                return False, "[Twitter] Could not find final Post button."

            time.sleep(5) # Wait for post to send and potentially UI changes

            pyautogui.hotkey('command', 'w')
            return True, None
            
                
        except Exception as e:
            print(f"[Twitter] Error during GUI automation: {str(e)}")
            import traceback
            traceback.print_exc()
            # Attempt to close window in case of error
            try:
                pyautogui.hotkey('command', 'w')
            except Exception:
                pass
            return False, f"[Twitter] GUI automation error: {str(e)}"

# --- Tool Definitions ---

class SocialMediaPostTool(BaseTool):
    platform: str
    poster_class: type
    name: str
    description: str
    user_id: Optional[str] = None

    def __init__(self, platform: str, poster_class, name: str, description: str):
        super().__init__(
            platform=platform,
            poster_class=poster_class,
            name=name,
            description=description,
            user_id=None
        )

    def _run(self, account_name: str, content: str, image_path: Optional[str] = None) -> str:
        if not self.user_id:
            return "Error: User context (user_id) not set for the tool."

        print(f"[Tool Run] Attempting to post to {self.platform} account '{account_name}'")
        if image_path:
            print(f"[Tool Run] With image attachment: {image_path}")

        settings = _get_settings(self.user_id, self.platform, account_name)
        if not settings:
            return f"Error: Could not load settings for user '{self.user_id}', {self.platform.title()} account '{account_name}'."

        poster = self.poster_class(settings=settings)
        variant = PostVariant(platform=self.platform, account_name=account_name, content=content, image_path=image_path)

        try:
            _success, message = poster.post(content, variant, settings)
            return message
        except Exception as e:
            print(f"[Tool Run] Unhandled exception in {self.platform.title()}PostTool: {e}")
            import traceback
            traceback.print_exc()
            return f"An unexpected error occurred while trying to post to {self.platform.title()}: {str(e)}"

# Instantiate the tools

# Twitter
twitter_post_tool = SocialMediaPostTool(
    platform="twitter",
    poster_class=TwitterPoster,
    name="Post to Twitter",
    description="Posts the given text content to a specified Twitter account using API or GUI automation. Requires the account name and content and the user has to be logged into the application on the web."
)

# Lens
lens_post_tool = SocialMediaPostTool(
    platform="lens",
    poster_class=LensPoster,
    name="Post to Lens",
    description="Posts the given text content to a specified Lens account using GUI automation. Requires the content and the user has to be logged into the application on the web."
)

# BlueSky
bluesky_post_tool = SocialMediaPostTool(
    platform="bluesky",
    poster_class=BlueSkyPoster,
    name="Post to BlueSky",
    description="Posts the given text content to a specified BlueSky account using the API. Requires the account name and content."
)

# Mastodon
mastodon_post_tool = SocialMediaPostTool(
    platform="mastodon",
    poster_class=MastodonPoster,
    name="Post to Mastodon",
    description="Posts the given text content to a specified Mastodon account using the API. Requires the account name and content."
)

# Farcaster
farcaster_post_tool = SocialMediaPostTool(
    platform="farcaster",
    poster_class=FarcasterPoster,
    name="Post to Farcaster",
    description="Posts the given text content to a specified Farcaster account using the API or GUI automation. Requires the mnemonic and content or the user has to be logged into the application on the web."
)

# LinkedIn
linkedin_post_tool = SocialMediaPostTool(
    platform="linkedin",
    poster_class=LinkedInPoster,
    name="Post to LinkedIn",
    description="Posts the given text content to a specified LinkedIn account using GUI automation. Requires the account name and content and the user has to be logged into the application on the web."
)

available_tools = [twitter_post_tool, bluesky_post_tool, lens_post_tool, mastodon_post_tool, farcaster_post_tool, linkedin_post_tool]