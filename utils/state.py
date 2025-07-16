import json
import time
from collections import deque
from typing import Dict, Optional, Tuple
import discord

class State:
    """Global state management for the bot"""
    
    def __init__(self):
        # Queue management
        self.waiting_queue = deque()
        self.anon_queue = deque()
        
        # Call management
        self.active_calls: Dict[int, int] = {}
        self.call_started: Dict[int, float] = {}
        self.anon_channels: set[int] = set()
        
        # Queue message tracking for editing
        self.queue_messages: Dict[int, discord.Message] = {}
        
        # Message forwarding
        self.webhooks: Dict[int, discord.Webhook] = {}
        self.relay_map: Dict[Tuple[int, int], int] = {}
        self.last_sent: Dict[int, float] = {}
        self.last_profile: Dict[Tuple[int, int], Tuple[str, str]] = {}
        
        # User settings
        self.user_settings: Dict[str, dict] = {}
        self.settings_path = "user_settings.json"
        self.load_settings()
        
        # Constants
        self.COOLDOWN = 1
        self.AUDIO_AVATAR = "https://i.imgur.com/0h6wYht.png"
    
    def load_settings(self):
        """Load user settings from file"""
        try:
            with open(self.settings_path, "r") as fp:
                self.user_settings = json.load(fp)
        except FileNotFoundError:
            self.user_settings = {}
    
    def flush_settings(self):
        """Save user settings to file"""
        with open(self.settings_path, "w") as fp:
            json.dump(self.user_settings, fp)
    
    def alias_for(self, user: discord.User, anon: bool) -> str:
        """Get alias for user"""
        if anon:
            return f"Stranger {str(user.id)[-4:]}"
        return self.user_settings.get(str(user.id), {}).get("alias", user.display_name)
    
    def avatar_for(self, user: discord.User, anon: bool) -> str:
        """Get avatar URL for user"""
        if anon:
            return self.AUDIO_AVATAR
        return self.user_settings.get(str(user.id), {}).get("avatar_url", user.display_avatar.url)
    
    def start_call(self, ch1_id: int, ch2_id: int, anon: bool = False):
        """Start a call between two channels"""
        self.active_calls[ch1_id] = ch2_id
        self.active_calls[ch2_id] = ch1_id
        self.call_started[ch1_id] = self.call_started[ch2_id] = time.time()
        
        if anon:
            self.anon_channels.update({ch1_id, ch2_id})
        
        # Clean up queue messages for both channels
        self.queue_messages.pop(ch1_id, None)
        self.queue_messages.pop(ch2_id, None)
    
    def end_call(self, ch1_id: int) -> Optional[int]:
        """End a call and return partner channel ID if it existed"""
        partner_id = self.active_calls.pop(ch1_id, None)
        if partner_id:
            self.active_calls.pop(partner_id, None)
            self.anon_channels.discard(ch1_id)
            self.anon_channels.discard(partner_id)
            
            # Clean up relay map entries for both channels
            for k in list(self.relay_map.keys()):
                if k[0] in {ch1_id, partner_id}:
                    self.relay_map.pop(k)
            
            self.call_started.pop(ch1_id, None)
            self.call_started.pop(partner_id, None)
            
            # Clean up queue messages
            self.queue_messages.pop(ch1_id, None)
            self.queue_messages.pop(partner_id, None)
            
            return partner_id
        return None
    
    def get_call_duration(self, ch_id: int) -> Optional[int]:
        """Get call duration in minutes"""
        start = self.call_started.get(ch_id)
        if start:
            return int((time.time() - start) // 60)
        return None
    
    def is_in_call(self, ch_id: int) -> bool:
        """Check if channel is in active call"""
        return ch_id in self.active_calls
    
    def is_anonymous(self, ch_id: int) -> bool:
        """Check if channel is in anonymous mode"""
        return ch_id in self.anon_channels
    
    def remove_from_queues(self, ch_id: int) -> bool:
        """Remove channel from all queues, return True if found"""
        found = False
        for q in (self.waiting_queue, self.anon_queue):
            if ch_id in q:
                q.remove(ch_id)
                found = True
        
        # Clean up queue message if found
        if found:
            self.queue_messages.pop(ch_id, None)
        
        return found
    
    def prune_relay(self, ch1_id: int, ch2_id: int):
        """Clean up relay map entries for disconnected channels"""
        for k in list(self.relay_map.keys()):
            if k[0] in {ch1_id, ch2_id}:
                self.relay_map.pop(k)

# Global state instance
state = State()