import sys
import io
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding='utf-8')

import discord
from discord import app_commands
from discord.ext import commands
import os
import random
from dotenv import load_dotenv
from itertools import combinations
from typing import Optional
import re
import datetime
import asyncio
import glob
from discord.ui import Button, View
import pytz
from PIL import Image, ImageDraw, ImageFont
# Removed pilmoji import due to dependency issues 
import io
import json
from pathlib import Path
import requests
import requests
import tempfile
import gspread
from google.oauth2.service_account import Credentials
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase Configuration
try:
    if not firebase_admin._apps:
        if os.environ.get("FIREBASE_CREDENTIALS"):
            # Load from raw JSON string Environment Variable instead of a complicated file mount
            cred_dict = json.loads(os.environ.get("FIREBASE_CREDENTIALS"))
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("✅ Connected to Firebase Firestore (via Env Var)")
        elif os.path.exists('firebase_credentials.json'):
            cred = credentials.Certificate('firebase_credentials.json')
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("✅ Connected to Firebase Firestore (via File)")
        else:
            print("⚠️ Firebase credentials not found (JSON file or Env Var missing). Firebase disabled.")
            db = None
    else:
        db = firestore.client()
        print("✅ Connected to Firebase Firestore")
except Exception as e:
    print(f"❌ Firebase initialization error: {e}")
    db = None

# Google Sheets Configuration
GOOGLE_SHEET_ID = "1i8yWJhe-T4cYQtrzfp4HcqH8UmndDi8yydWnMYDfcMI"  # Replace with your actual Sheet ID if different
SERVICE_ACCOUNT_FILE = "service_account.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

class GoogleSheetManager:
    def __init__(self):
        self.client = None
        self.event_sheet = None
        self.attendance_sheet = None
        self.connect()

    def connect(self):
        try:
            if os.path.exists(SERVICE_ACCOUNT_FILE):
                credentials = Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, scopes=SCOPES
                )
                self.client = gspread.authorize(credentials)
                # Open specific worksheets
                sheet = self.client.open_by_key(GOOGLE_SHEET_ID)
                try:
                    self.event_sheet = sheet.worksheet("Event Details")
                except:
                    print("⚠️ 'Event Details' worksheet not found. Using first sheet.")
                    self.event_sheet = sheet.sheet1

                try:
                    self.attendance_sheet = sheet.worksheet("Mark Attendance")
                except:
                    print("⚠️ 'Mark Attendance' worksheet not found.")
                    self.attendance_sheet = None
                    
                print("✅ Connected to Google Sheet")
            else:
                print("⚠️ service_account.json not found. Google Sheet integration disabled.")
        except Exception as e:
            print(f"❌ Error connecting to Google Sheet: {e}")

    def log_event_creation(self, event_data):
        if not self.event_sheet: return
        try:
            # Columns: EventID, Tournament, Mode, Round, Team1, Team2, Date, Time, Judge, Recorder, Winner, Score, Remarks
            row = [
                event_data['event_id'],
                event_data['tournament'],
                event_data.get('mode', 'MW'),
                event_data['round'],
                event_data['team1_captain'].name,
                event_data['team2_captain'].name,
                event_data['date_str'],
                event_data['time_str'],
                "Unassigned", # Judge
                "Unassigned", # Recorder
                "Pending", # Winner
                "Pending",  # Score/Result
                "" # Remarks
            ]
            self.event_sheet.append_row(row)
        except Exception as e:
            print(f"Error logging event to sheet: {e}")

    def update_event_staff(self, event_id, judge_name=None, recorder_name=None):
        if not self.event_sheet: return
        try:
            cell = self.event_sheet.find(event_id)
            if cell:
                if judge_name:
                    self.event_sheet.update_cell(cell.row, 9, judge_name) # Column 9 (I) is Judge
                if recorder_name:
                    self.event_sheet.update_cell(cell.row, 10, recorder_name) # Column 10 (J) is Recorder
        except Exception as e:
            print(f"Error updating staff in sheet: {e}")

    def log_event_result(self, event_id, winner_name, score_text, remarks):
        if not self.event_sheet: return
        try:
            cell = self.event_sheet.find(event_id)
            if cell:
                self.event_sheet.update_cell(cell.row, 11, winner_name) # Column 11 (K) Winner
                self.event_sheet.update_cell(cell.row, 12, score_text)  # Column 12 (L) Score
                # Column 13 (M) Remarks
                if remarks:
                    self.event_sheet.update_cell(cell.row, 13, remarks)
        except Exception as e:
            print(f"Error logging result to sheet: {e}")

    def log_attendance(self, date_str, time_str, event_name, role, staff_name, marked_by):
        if not self.attendance_sheet: return
        try:
            # Columns based on assumption: Date, Time, Event Name, Judge Name, Recorder Name, Marked By
            # We map inputs to these columns.
            judge_val = staff_name if role.lower() == "judge" else ""
            recorder_val = staff_name if role.lower() == "recorder" else ""
            
            row = [
                date_str,
                time_str,
                event_name,
                judge_val,
                recorder_val,
                marked_by
            ]
            self.attendance_sheet.append_row(row)
        except Exception as e:
            print(f"Error logging attendance to sheet: {e}")
            
    def erase_sheets(self):
        """Clears out all rows except the headers to prepare for a new tournament."""
        if self.event_sheet:
            try:
                # Get total rows to ensure we clear enough
                num_rows = self.event_sheet.row_count
                if num_rows > 1:
                    # Clear A2 to Z(num_rows) to avoid touching header
                    self.event_sheet.batch_clear([f"A2:Z{num_rows+10}"])
            except Exception as e:
                print(f"Error erasing event_sheet: {e}")
                
        if self.attendance_sheet:
            try:
                num_rows = self.attendance_sheet.row_count
                if num_rows > 1:
                    self.attendance_sheet.batch_clear([f"A2:Z{num_rows+10}"])
            except Exception as e:
                print(f"Error erasing attendance_sheet: {e}")

sheet_manager = GoogleSheetManager()

# Load environment variables
load_dotenv()

# Channel IDs for event management
CHANNEL_IDS = {
    "take_schedule": 1473774001649090600,
    "results": 1473774002970558486,
    "transcript": 1474159906658713733,
    "staff_attendance": 1473774005235220601
}

# Bot Owner ID for special permissions
BOT_OWNER_ID = 1251442077561131059

# Branding constants
ORGANIZATION_NAME = "Winterfell Arena Esports"
TOURNAMENT_SYSTEM_NAME = "Winterfell Arena Esports Tournament System"

# Role IDs for permissions
# Role IDs for permissions (Supports single ID or list of IDs)
ROLE_IDS = {
    "judge": [1473773795176091674],
    "recorder": [1474281127643451543],
    "head_helper": [1473773791531372664],
    "helper_team": [1184587759487303790],
    "head_organizer": [1474281212398014513],
    "deputy_server_head":[1473773779237863568],
    "Tournament_organizer":[1473773807939485757],
    "Tournament_supervision":[1473773780303347824]
}

# Set Windows event loop policy for asyncio
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.guild_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Store scheduled events for reminders
scheduled_events = {}

# Create command groups
events_group = app_commands.Group(name="events", description="Tournament event management")
tree.add_command(events_group)


# Load scheduled events from file on startup
# Load scheduled events from file on startup
def load_scheduled_events():
    global scheduled_events
    try:
        if db:
            docs = db.collection('scheduled_events').stream()
            data = {doc.id: doc.to_dict() for doc in docs}
            # Convert datetime strings back to datetime objects
            for event_id, event_data in data.items():
                if 'datetime' in event_data:
                    event_data['datetime'] = datetime.datetime.fromisoformat(event_data['datetime'])
            scheduled_events = data
            print(f"Loaded {len(scheduled_events)} scheduled events from Firebase")
        elif os.path.exists('scheduled_events.json'):
            with open('scheduled_events.json', 'r') as f:
                data = json.load(f)
                # Convert datetime strings back to datetime objects
                for event_id, event_data in data.items():
                    if 'datetime' in event_data:
                        event_data['datetime'] = datetime.datetime.fromisoformat(event_data['datetime'])
                scheduled_events = data
                print(f"Loaded {len(scheduled_events)} scheduled events from file")
    except Exception as e:
        print(f"Error loading scheduled events: {e}")
        scheduled_events = {}

# Save scheduled events to file
def save_scheduled_events():
    try:
        # Convert datetime objects to strings for JSON serialization
        data_to_save = {}
        for event_id, event_data in scheduled_events.items():
            event_copy = event_data.copy()
            if 'datetime' in event_copy:
                event_copy['datetime'] = event_copy['datetime'].isoformat()
            
            # Convert Discord objects to IDs
            for key in ['team1_captain', 'team2_captain', 'judge', 'recorder', 'created_by', 'result_judge', 'winner', 'loser']:
                if key in event_copy and hasattr(event_copy[key], 'id'):
                    event_copy[key] = event_copy[key].id
                elif key in event_copy and event_copy[key] is None:
                    event_copy[key] = None
                
            data_to_save[event_id] = event_copy
        
        if db:
            # Batch write events to Firebase
            batch = db.batch()
            for ev_id, ev_data in data_to_save.items():
                doc_ref = db.collection('scheduled_events').document(ev_id)
                batch.set(doc_ref, ev_data)
            batch.commit()
        else:
            with open('scheduled_events.json', 'w') as f:
                json.dump(data_to_save, f, indent=2)
    except Exception as e:
        print(f"Error saving scheduled events: {e}")

# Track per-event reminder tasks (for cancellation/update)
reminder_tasks = {}

# Track per-event cleanup tasks (to remove finished events after result)
cleanup_tasks = {}

# Store staff statistic for leaderboard
staff_stats = {}  # {user_id: {"name": str, "judge_count": int, "recorder_count": int, "last_activity": datetime}}

# ===========================================================================================
# RULE MANAGEMENT SYSTEM
# ===========================================================================================

# Store tournament rules in memory
tournament_rules = {}

def load_rules():
    """Load rules from persistent storage"""
    global tournament_rules
    try:
        if db:
            doc = db.collection('settings').document('tournament_rules').get()
            if doc.exists:
                tournament_rules = doc.to_dict().get('rules', {})
                print(f"Loaded tournament rules from Firebase")
            else:
                tournament_rules = {}
                print("No existing rules found in Firebase, starting with empty rules")
        elif os.path.exists('tournament_rules.json'):
            with open('tournament_rules.json', 'r', encoding='utf-8') as f:
                tournament_rules = json.load(f)
                print(f"Loaded tournament rules from file")
        else:
            tournament_rules = {}
            print("No existing rules file found, starting with empty rules")
    except Exception as e:
        print(f"Error loading tournament rules: {e}")
        tournament_rules = {}

def save_rules():
    """Save rules to persistent storage"""
    try:
        if db:
            db.collection('settings').document('tournament_rules').set({'rules': tournament_rules})
        else:
            with open('tournament_rules.json', 'w', encoding='utf-8') as f:
                json.dump(tournament_rules, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving tournament rules: {e}")
        return False

def load_staff_stats():
    """Load staff statistics from persistent storage"""
    global staff_stats
    try:
        if db:
            docs = db.collection('staff_stats').stream()
            data = {doc.id: doc.to_dict() for doc in docs}
            # Convert datetime strings back to datetime objects
            for user_id, stats in data.items():
                if 'last_activity' in stats and stats['last_activity']:
                    try:
                        stats['last_activity'] = datetime.datetime.fromisoformat(stats['last_activity'])
                    except ValueError:
                         stats['last_activity'] = None
            staff_stats = data
            print(f"Loaded staff statistics from Firebase")
        elif os.path.exists('staff_stats.json'):
            # Check for legacy judge_stats.json first and migrate if needed
            if os.path.exists('judge_stats.json') and not os.path.exists('staff_stats.json'):
                print("Migrating legacy judge stats...")
                try:
                    with open('judge_stats.json', 'r', encoding='utf-8') as f:
                        legacy_data = json.load(f)
                        for uid, data in legacy_data.items():
                            staff_stats[uid] = {
                                "name": data.get("name", "Unknown"),
                                "judge_count": data.get("matches_judged", 0),
                                "recorder_count": 0,
                                "last_activity": datetime.datetime.fromisoformat(data["last_activity"]) if data.get("last_activity") else None
                            }
                    print("Migration complete.")
                except Exception as e:
                    print(f"Migration failed: {e}")

            if os.path.exists('staff_stats.json'):
                with open('staff_stats.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convert datetime strings back to datetime objects
                    for user_id, stats in data.items():
                        if 'last_activity' in stats and stats['last_activity']:
                            try:
                                stats['last_activity'] = datetime.datetime.fromisoformat(stats['last_activity'])
                            except ValueError:
                                 stats['last_activity'] = None
                    staff_stats = data
                    print(f"Loaded staff statistics from file")
        
        if not staff_stats: # Fallback if neither exists or empty
            staff_stats = {}
            print("No existing staff stats found, starting with empty stats")
    except Exception as e:
        print(f"Error loading staff statistics: {e}")
        staff_stats = {}

def save_staff_stats():
    """Save staff statistics to persistent storage"""
    try:
        # Convert datetime objects to strings for JSON serialization
        data_to_save = {}
        for user_id, stats in staff_stats.items():
            stats_copy = stats.copy()
            if 'last_activity' in stats_copy and stats_copy['last_activity']:
                stats_copy['last_activity'] = stats_copy['last_activity'].isoformat()
            data_to_save[str(user_id)] = stats_copy
        
        if db:
            batch = db.batch()
            for uid, stats in data_to_save.items():
                doc_ref = db.collection('staff_stats').document(uid)
                batch.set(doc_ref, stats)
            batch.commit()
        else:
            with open('staff_stats.json', 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving staff statistics: {e}")
        return False

def update_staff_stats(user_id: int, user_name: str, role: str):
    """Update staff statistics when they complete a match"""
    global staff_stats
    uid = str(user_id)
    
    if uid not in staff_stats:
        staff_stats[uid] = {
            "name": user_name,
            "judge_count": 0,
            "recorder_count": 0,
            "last_activity": None
        }
    
    if role.lower() == "judge":
        staff_stats[uid]["judge_count"] += 1
    elif role.lower() == "recorder":
        staff_stats[uid]["recorder_count"] += 1
        
    staff_stats[uid]["last_activity"] = datetime.datetime.utcnow()
    staff_stats[uid]["name"] = user_name  # Update name in case it changed
    
    save_staff_stats()

def reset_staff_stats():
    """Reset all staff statistics (Head Organizer only)"""
    global staff_stats
    staff_stats = {}
    save_staff_stats()
    return True

def get_staff_leaderboard(limit: int = 20) -> list:
    """Get top staff sorted by total activity"""
    try:
        # Sort by total count (judge + recorder)
        sorted_staff = sorted(
            staff_stats.items(),
            key=lambda x: x[1].get("judge_count", 0) + x[1].get("recorder_count", 0),
            reverse=True
        )
        return sorted_staff[:limit]
    except Exception as e:
        print(f"Error getting staff leaderboard: {e}")
        return []

def get_current_rules():
    """Get current rules content"""
    return tournament_rules.get('rules', {}).get('content', '')

def set_rules_content(content, user_id, username):
    """Set new rules content with metadata"""
    global tournament_rules
    
    # Sanitize content (basic cleanup)
    if content:
        content = content.strip()
    
    # Update rules with metadata
    tournament_rules['rules'] = {
        'content': content,
        'last_updated': datetime.datetime.utcnow().isoformat(),
        'updated_by': {
            'user_id': user_id,
            'username': username
        },
        'version': tournament_rules.get('rules', {}).get('version', 0) + 1
    }
    
    return save_rules()

# Enhanced command data structure for help system
COMMAND_DATA = {
    "system": {
        "title": "⚙️ System Commands",
        "description": "Basic bot functionality available to all users",
        "commands": [
            {
                "name": "/help",
                "description": "Display this comprehensive command guide with role-based filtering",
                "usage": "/help",
                "permissions": "everyone",
                "example": "Simply type `/help` to see available commands",
                "parameters": [],
                "usage_examples": [
                    {
                        "scenario": "Getting general help",
                        "command": "/help",
                        "explanation": "Shows all commands available to your role"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "tip",
                        "content": "Help is filtered based on your Discord roles - you'll only see commands you can actually use"
                    }
                ],
                "related_commands": [],
                "common_errors": []
            },
            {
                "name": "/rules",
                "description": "View tournament rules (or manage them if you're an organizer)",
                "usage": "/rules",
                "permissions": "everyone (view) / organizer (manage)",
                "example": "Use `/rules` to view current tournament rules",
                "parameters": [],
                "usage_examples": [
                    {
                        "scenario": "Viewing current rules",
                        "command": "/rules",
                        "explanation": "Displays the current tournament rules for all players"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "note",
                        "content": "Only Head Organizers can edit rules - everyone else can view them"
                    }
                ],
                "related_commands": ["/help"],
                "common_errors": []
            },
            {
                "name": "/staff-leaderboard",
                "description": "Display staff leaderboard showing active judges and recorders",
                "usage": "/staff-leaderboard",
                "permissions": "everyone",
                "example": "Use `/staff-leaderboard` to see the most active staff members",
                "parameters": [],
                "usage_examples": [
                    {
                        "scenario": "Viewing staff statistics",
                        "command": "/staff-leaderboard",
                        "explanation": "Shows top staff, ranked by total matches handled"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "note",
                        "content": "Statistics are updated automatically when results are posted"
                    },
                    {
                        "type": "tip",
                        "content": "Head Organizers can reset the leaderboard"
                    },
                    {
                        "type": "warning",
                        "content": "Leaderboard is public"
                    }
                ],
                "related_commands": ["/event-result"],
                "common_errors": []
            },
            {
                "name": "/info",
                "description": "Display bot information, latency, and server statistics",
                "usage": "/info",
                "permissions": "everyone",
                "example": "Use `/info` to check bot status and statistics",
                "parameters": [],
                "usage_examples": [
                    {
                        "scenario": "Checking bot status",
                        "command": "/info",
                        "explanation": "Shows latency, server count, and version info"
                    }
                ],
                "tips_and_warnings": [],
                "related_commands": ["/help"],
                "common_errors": []
            }
        ]
    },
    "utility": {
        "title": "🛠️ Utility Commands",
        "description": "Helpful tools for tournament management",
        "commands": [
            {
                "name": "/team_balance",
                "description": "Balance two teams based on player skill levels",
                "usage": "/team_balance levels:<comma-separated levels>",
                "permissions": "everyone",
                "example": "Example: `/team_balance levels:48,50,51,35,51,50,50,37,51,52`",
                "parameters": [
                    {
                        "name": "levels",
                        "type": "string",
                        "required": True,
                        "description": "Comma-separated list of player skill levels (numbers)",
                        "constraints": "Must be numeric values separated by commas, minimum 2 players",
                        "examples": ["48,50,51,35", "45,47,49,52,53,48,46,51"]
                    }
                ],
                "usage_examples": [
                    {
                        "scenario": "Balancing 4 players",
                        "command": "/team_balance levels:48,50,51,35",
                        "explanation": "Creates two balanced teams from 4 players with given skill levels"
                    },
                    {
                        "scenario": "Balancing 8 players",
                        "command": "/team_balance levels:45,47,49,52,53,48,46,51",
                        "explanation": "Creates two balanced teams from 8 players, optimizing for fair skill distribution"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "tip",
                        "content": "The algorithm tries to minimize skill difference between teams"
                    },
                    {
                        "type": "note",
                        "content": "Works best with even numbers of players, but can handle odd numbers too"
                    }
                ],
                "related_commands": ["/choose"],
                "common_errors": [
                    {
                        "error": "Invalid levels format",
                        "solution": "Make sure to separate skill levels with commas and use only numbers"
                    }
                ]
            },
            {
                "name": "/time",
                "description": "Generate a random match time between 12:00-17:59 UTC",
                "usage": "/time",
                "permissions": "everyone",
                "example": "Use `/time` to get a random tournament match time",
                "parameters": [],
                "usage_examples": [
                    {
                        "scenario": "Getting a random match time",
                        "command": "/time",
                        "explanation": "Generates a random time in the tournament window (12:00-17:59 UTC)"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "note",
                        "content": "Times are always in UTC timezone for consistency across regions"
                    },
                    {
                        "type": "tip",
                        "content": "Use this for scheduling matches when captains can't agree on a time"
                    }
                ],
                "related_commands": ["/event-create"],
                "common_errors": []
            },
            {
                "name": "/choose",
                "description": "Make a random choice from comma-separated options",
                "usage": "/choose options:<option1,option2,option3>",
                "permissions": "everyone",
                "tutorial_url": "https://youtu.be/xSLbccfaKzE",
                "example": "Example: `/choose options:Map1,Map2,Map3` to randomly select a map",
                "parameters": [
                    {
                        "name": "options",
                        "type": "string",
                        "required": True,
                        "description": "Comma-separated list of options to choose from",
                        "constraints": "Minimum 2 options, maximum 20 options",
                        "examples": ["Map1,Map2,Map3", "Red,Blue,Green,Yellow", "Option A,Option B"]
                    }
                ],
                "usage_examples": [
                    {
                        "scenario": "Choosing a map",
                        "command": "/choose options:Archipelago,Beacon,Cold Waters",
                        "explanation": "Randomly selects one map from the three options"
                    },
                    {
                        "scenario": "Picking team colors",
                        "command": "/choose options:Red,Blue,Green,Yellow",
                        "explanation": "Randomly selects a team color from the available options"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "tip",
                        "content": "Great for making fair decisions when teams can't agree"
                    }
                ],
                "related_commands": ["/team_balance"],
                "common_errors": [
                    {
                        "error": "Only one option provided",
                        "solution": "Provide at least 2 options separated by commas"
                    }
                ]
            },
            {
                "name": "/maps",
                "description": "Randomly select 3, 5, or 7 maps from the tournament pool",
                "usage": "/maps count:<3|5|7>",
                "permissions": "everyone",
                "example": "Example: `/maps count:5` to select 5 random maps",
                "parameters": [
                    {
                        "name": "count",
                        "type": "integer",
                        "required": True,
                        "description": "Number of maps to pick (must be 3, 5, or 7)",
                        "constraints": "3, 5, or 7",
                        "examples": ["3", "5", "7"]
                    }
                ],
                "usage_examples": [
                    {
                        "scenario": "Selecting maps for a Bo5",
                        "command": "/maps count:5",
                        "explanation": "Picks 5 unique maps from the pool"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "tip",
                        "content": "Useful for veto processes or random selections"
                    }
                ],
                "related_commands": ["/choose"],
                "common_errors": []
            },
            {
                "name": "?sh / ?dq / ?dd / ?ho",
                "description": "Quickly update ticket channel status with status icons (🟢, 🔴, ✅, 🟡)",
                "usage": "?[code]",
                "permissions": "everyone",
                "example": "Type `?sh` to mark a match as started",
                "parameters": [],
                "usage_examples": [
                    {
                        "scenario": "Marking a match as finished",
                        "command": "?dd",
                        "explanation": "Adds ✅ to the channel name"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "tip",
                        "content": "Use these in match tickets to keep the sidebar organized"
                    }
                ],
                "related_commands": [],
                "common_errors": []
            },
            {
                "name": "?b",
                "description": "Get the official tournament bracket link",
                "usage": "?b",
                "permissions": "everyone",
                "example": "Type `?b` to see current standings",
                "parameters": [],
                "usage_examples": [],
                "tips_and_warnings": [],
                "related_commands": [],
                "common_errors": []
            }
        ]
    },
    "rules": {
        "title": "📜 Command Rules",
        "description": "General rules and etiquette for using bot commands",
        "commands": [
            {
                "name": "📍 Channel Etiquette",
                "description": "Use commands only in designated channels or active tournament tickets.",
                "usage": "General Rule",
                "permissions": "everyone",
                "example": "Match-specific commands should stay in match tickets.",
                "parameters": [],
                "usage_examples": [],
                "tips_and_warnings": [],
                "related_commands": [],
                "common_errors": []
            },
            {
                "name": "🛡️ No Spamming",
                "description": "Avoid triggering commands repeatedly. Wait for the bot to process your request.",
                "usage": "General Rule",
                "permissions": "everyone",
                "example": "Only click 'Take Schedule' once.",
                "parameters": [],
                "usage_examples": [],
                "tips_and_warnings": [],
                "related_commands": [],
                "common_errors": []
            },
            {
                "name": "🎯 Accuracy",
                "description": "Ensure all inputs (scores, dates, names) are correct before submitting results.",
                "usage": "Data Integrity",
                "permissions": "everyone",
                "example": "Verify the winner mention in /event-result.",
                "parameters": [],
                "usage_examples": [],
                "tips_and_warnings": [],
                "related_commands": [],
                "common_errors": []
            }
        ]
    },
    "event_management": {
        "title": "🏆 Event Management",
        "description": "Tournament event creation and management (requires special permissions)",
        "commands": [
            {
                "name": "/event-create",
                "description": "Create new tournament events with Group support and Winner/Loser options",
                "usage": "/event-create team_1_captain:<@user> team_2_captain:<@user> hour:<0-23> minute:<0-59> date:<1-31> month:<1-12> round:<round> tournament:<name> [group:<A-J/Winner/Loser>]",
                "permissions": "head_organizer / head_helper / helper_team",
                "tutorial_url": "https://youtu.be/Xo0CipufKaM",
                "example": "Example: `/event-create team_1_captain:@Captain1 team_2_captain:@Captain2 hour:15 minute:30 date:25 month:12 round:R1 tournament:Summer Cup group:Group A`",
                "round_options": "R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, Qualifier, Semi Final, Final",
                "group_options": "Group A, Group B, Group C, Group D, Group E, Group F, Group G, Group H, Group I, Group J, Winner, Loser",
                "parameters": [
                    {
                        "name": "team_1_captain",
                        "type": "user",
                        "required": True,
                        "description": "Discord user mention for team 1 captain",
                        "constraints": "Must be a valid Discord user in the server",
                        "examples": ["@Captain1", "@JohnDoe"]
                    },
                    {
                        "name": "team_2_captain",
                        "type": "user",
                        "required": True,
                        "description": "Discord user mention for team 2 captain",
                        "constraints": "Must be a valid Discord user in the server, different from team_1_captain",
                        "examples": ["@Captain2", "@JaneSmith"]
                    },
                    {
                        "name": "hour",
                        "type": "integer",
                        "required": True,
                        "description": "Hour of the match in 24-hour format (UTC)",
                        "constraints": "0-23",
                        "examples": ["15", "20", "12"]
                    },
                    {
                        "name": "minute",
                        "type": "integer",
                        "required": True,
                        "description": "Minute of the match",
                        "constraints": "0-59",
                        "examples": ["30", "0", "45"]
                    },
                    {
                        "name": "date",
                        "type": "integer",
                        "required": True,
                        "description": "Day of the month for the match",
                        "constraints": "1-31 (must be valid for the specified month)",
                        "examples": ["25", "15", "1"]
                    },
                    {
                        "name": "month",
                        "type": "integer",
                        "required": True,
                        "description": "Month number for the match",
                        "constraints": "1-12",
                        "examples": ["12", "6", "3"]
                    },
                    {
                        "name": "round",
                        "type": "choice",
                        "required": True,
                        "description": "Tournament round designation",
                        "constraints": "Must be one of: R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, Qualifier, Semi Final, Final",
                        "examples": ["R1", "Semi Final", "Final"]
                    },
                    {
                        "name": "tournament",
                        "type": "string",
                        "required": True,
                        "description": "Name of the tournament",
                        "constraints": "Any descriptive tournament name",
                        "examples": ["Summer Cup", "Winter Championship", "Weekly Tournament"]
                    },
                    {
                        "name": "group",
                        "type": "choice",
                        "required": False,
                        "description": "Group designation for group stage tournaments",
                        "constraints": "Must be one of: Group A-J, Winner, Loser",
                        "default": "None",
                        "examples": ["Group A", "Winner", "Loser"]
                    }
                ],
                "usage_examples": [
                    {
                        "scenario": "Creating a group stage match",
                        "command": "/event-create team_1_captain:@Alice team_2_captain:@Bob hour:15 minute:30 date:25 month:12 round:R1 tournament:Winter Cup group:Group A",
                        "explanation": "Creates a Round 1 match in Group A between Alice and Bob's teams"
                    },
                    {
                        "scenario": "Creating a final match",
                        "command": "/event-create team_1_captain:@Winner1 team_2_captain:@Winner2 hour:18 minute:0 date:30 month:12 round:Final tournament:Winter Cup",
                        "explanation": "Creates the final match between two winners"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "warning",
                        "content": "Double-check the date and time - incorrect scheduling can disrupt the tournament"
                    },
                    {
                        "type": "tip",
                        "content": "Use groups for organized tournaments with multiple stages"
                    },
                    {
                        "type": "note",
                        "content": "All times are in UTC - make sure captains know the timezone"
                    }
                ],
                "related_commands": ["/event-edit", "/event-delete", "/time"],
                "common_errors": [
                    {
                        "error": "Invalid date (e.g., February 30th)",
                        "solution": "Check that the date exists in the specified month"
                    },
                    {
                        "error": "Same captain for both teams",
                        "solution": "Make sure team_1_captain and team_2_captain are different users"
                    }
                ]
            },
            {
                "name": "/event-edit",
                "description": "Edit existing events to correct mistakes with Group support and Winner/Loser options",
                "usage": "/event-edit",
                "permissions": "head_organizer / head_helper / helper_team",
                "example": "Use `/event-edit` to select and modify any scheduled event with pre-filled current values including group assignments (Group A-J, Winner, Loser)",
                "parameters": [],
                "usage_examples": [
                    {
                        "scenario": "Correcting event details",
                        "command": "/event-edit",
                        "explanation": "Opens an interactive menu to select and edit any scheduled event"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "tip",
                        "content": "Current values are pre-filled - only change what needs to be corrected"
                    },
                    {
                        "type": "warning",
                        "content": "Notify affected players when you change event details"
                    }
                ],
                "related_commands": ["/event-create", "/event-delete"],
                "common_errors": []
            },
            {
                "name": "/event-result",
                "description": "Record match results with Group support and comprehensive tournament tracking",
                "usage": "/event-result winner:<@user> winner_score:<score> loser:<@user> loser_score:<score> tournament:<name> round:<round> [group:<A-J/Winner/Loser>] [remarks:<text>] [screenshots:<1-11>]",
                "permissions": "head_organizer / judge",
                "tutorial_url": "https://youtu.be/fQupdX9aCHI",
                "example": "Use `/event-result` to record match outcomes with group information and screenshot evidence",
                "round_options": "R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, Qualifier, Semi Final, Final",
                "group_options": "Group A, Group B, Group C, Group D, Group E, Group F, Group G, Group H, Group I, Group J, Winner, Loser",
                "parameters": [
                    {
                        "name": "winner",
                        "type": "user",
                        "required": True,
                        "description": "Discord user mention for the winning captain",
                        "constraints": "Must be a valid Discord user who was in the match",
                        "examples": ["@WinnerCaptain", "@Alice"]
                    },
                    {
                        "name": "winner_score",
                        "type": "integer",
                        "required": True,
                        "description": "Score achieved by the winning team",
                        "constraints": "Must be a positive integer, typically higher than loser_score",
                        "examples": ["3", "5", "10"]
                    },
                    {
                        "name": "loser",
                        "type": "user",
                        "required": True,
                        "description": "Discord user mention for the losing captain",
                        "constraints": "Must be a valid Discord user who was in the match, different from winner",
                        "examples": ["@LoserCaptain", "@Bob"]
                    },
                    {
                        "name": "loser_score",
                        "type": "integer",
                        "required": True,
                        "description": "Score achieved by the losing team",
                        "constraints": "Must be a positive integer or 0",
                        "examples": ["1", "2", "0"]
                    },
                    {
                        "name": "tournament",
                        "type": "string",
                        "required": True,
                        "description": "Name of the tournament (must match event creation)",
                        "constraints": "Must match the tournament name from the original event",
                        "examples": ["Summer Cup", "Winter Championship"]
                    },
                    {
                        "name": "round",
                        "type": "choice",
                        "required": True,
                        "description": "Tournament round (must match event creation)",
                        "constraints": "Must be one of: R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, Qualifier, Semi Final, Final",
                        "examples": ["R1", "Semi Final", "Final"]
                    },
                    {
                        "name": "group",
                        "type": "choice",
                        "required": False,
                        "description": "Group designation (if applicable)",
                        "constraints": "Must be one of: Group A-J, Winner, Loser",
                        "examples": ["Group A", "Winner"]
                    },
                    {
                        "name": "remarks",
                        "type": "string",
                        "required": False,
                        "description": "Additional notes about the match",
                        "constraints": "Any relevant information about the match",
                        "examples": ["Close match", "Technical issues resolved", "Overtime victory"]
                    },
                    {
                        "name": "screenshots",
                        "type": "integer",
                        "required": False,
                        "description": "Number of screenshot attachments",
                        "constraints": "1-11 screenshots can be attached",
                        "examples": ["3", "5", "1"]
                    }
                ],
                "usage_examples": [
                    {
                        "scenario": "Recording a group stage result",
                        "command": "/event-result winner:@Alice winner_score:3 loser:@Bob loser_score:1 tournament:Winter Cup round:R1 group:Group A remarks:Great match",
                        "explanation": "Records Alice's team victory over Bob's team in Group A"
                    },
                    {
                        "scenario": "Recording a final result with screenshots",
                        "command": "/event-result winner:@Champion winner_score:5 loser:@Runner loser_score:2 tournament:Winter Cup round:Final screenshots:3",
                        "explanation": "Records the final match result with 3 screenshot attachments"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "warning",
                        "content": "This permanently records the result - double-check all details before submitting"
                    },
                    {
                        "type": "tip",
                        "content": "Include screenshots as evidence, especially for important matches"
                    },
                    {
                        "type": "note",
                        "content": "Tournament and round must exactly match the original event creation"
                    }
                ],
                "related_commands": ["/event-create", "/unassigned_events"],
                "common_errors": [
                    {
                        "error": "Tournament name mismatch",
                        "solution": "Use the exact tournament name from when the event was created"
                    },
                    {
                        "error": "Winner score lower than loser score",
                        "solution": "Make sure the winner actually has the higher score"
                    }
                ]
            },
            {
                "name": "/event-delete",
                "description": "Delete scheduled events (use with caution)",
                "usage": "/event-delete",
                "permissions": "head_organizer / head_helper / helper_team",
                "tutorial_url": "https://youtu.be/xSLbccfaKzE",
                "example": "Use `/event-delete` and select from scheduled events to remove",
                "parameters": [],
                "usage_examples": [
                    {
                        "scenario": "Removing a cancelled event",
                        "command": "/event-delete",
                        "explanation": "Opens a selection menu to choose which scheduled event to delete"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "warning",
                        "content": "This permanently deletes the event - make sure you really want to remove it"
                    },
                    {
                        "type": "tip",
                        "content": "Notify affected players before deleting their scheduled match"
                    }
                ],
                "related_commands": ["/event-create", "/event-edit"],
                "common_errors": []
            },
            {
                "name": "/unassigned_events",
                "description": "List all events without a judge assigned for easy management",
                "usage": "/unassigned_events",
                "permissions": "head_organizer / head_helper / helper_team / judge",
                "example": "Use `/unassigned_events` to see which matches still need judges",
                "parameters": [],
                "usage_examples": [
                    {
                        "scenario": "Finding matches that need judges",
                        "command": "/unassigned_events",
                        "explanation": "Shows all scheduled events that don't have a judge assigned yet"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "tip",
                        "content": "Judges can use this to find matches they can volunteer for"
                    },
                    {
                        "type": "note",
                        "content": "Events are automatically removed from this list when a judge is assigned"
                    }
                ],
                "related_commands": ["/exchange"],
                "common_errors": []
            },
            {
                "name": "/exchange",
                "description": "Exchange a Judge or Recorder for an event",
                "usage": "/exchange role:[Judge/Recorder] new_user:@User",
                "permissions": "head_organizer / head_helper / helper_team / judge",
                "tutorial_url": "https://youtu.be/vBYZSkdiyFI",
                "example": "Use `/exchange` to swap staff for an event",
                "parameters": [
                    {
                        "name": "role",
                        "type": "choice",
                        "required": True,
                        "description": "Role to exchange (Judge or Recorder)",
                        "constraints": "Must be Judge or Recorder",
                        "examples": ["Judge", "Recorder"]
                    },
                    {
                        "name": "new_user",
                        "type": "user",
                        "required": True,
                        "description": "The new staff member taking over",
                        "constraints": "Valid Discord user",
                        "examples": ["@NewStaff"]
                    }
                ],
                "usage_examples": [],
                "tips_and_warnings": [],
                "related_commands": ["/event-create"],
                "common_errors": []
            },
            {
                "name": "/general_tie_breaker",
                "description": "Break a tie between two teams by calculating total player scores",
                "usage": "/general_tie_breaker tm1_pl1_score:<val> ... tm2_pl5_score:<val>",
                "permissions": "organizer / helper",
                "example": "Input all player scores to see which team wins by total score",
                "parameters": [
                    {
                        "name": "tm1_pl1-5_score",
                        "type": "integer",
                        "required": True,
                        "description": "Scores for all 5 players of Team 1"
                    },
                    {
                        "name": "tm2_pl1-5_score",
                        "type": "integer",
                        "required": True,
                        "description": "Scores for all 5 players of Team 2"
                    }
                ],
                "usage_examples": [],
                "tips_and_warnings": [
                    {
                        "type": "tip",
                        "content": "Calculates the sum for both teams and declares a winner based on highest total"
                    }
                ],
                "related_commands": ["/event-result"],
                "common_errors": []
            },
            {
                "name": "/add_captain",
                "description": "Add team names and captains to a match channel and rename it automatically",
                "usage": "/add_captain round:<R1-Fin> team1:<name> captain1:<@user> team2:<name> captain2:<@user>",
                "permissions": "organizer / helper",
                "tutorial_url": "https://youtu.be/4zAQ7pMcsFM",
                "example": "Use in a ticket to quickly setup the match environment",
                "parameters": [
                    {
                        "name": "round",
                        "type": "choice",
                        "required": True,
                        "description": "The current tournament round"
                    },
                    {
                        "name": "team1 / team2",
                        "type": "string",
                        "required": True,
                        "description": "The names of the two teams"
                    },
                    {
                        "name": "captain1 / captain2",
                        "type": "user",
                        "required": True,
                        "description": "The mentions for team captains"
                    }
                ],
                "usage_examples": [],
                "tips_and_warnings": [
                    {
                        "type": "note",
                        "content": "Renames the channel to round-team1-vs-team2 format and pings rules"
                    }
                ],
                "related_commands": ["/event-create"],
                "common_errors": []
            },
            {
                "name": "/test_channels",
                "description": "Verify bot permissions in all configured channels",
                "usage": "/test_channels",
                "permissions": "owner / head_organizer",
                "example": "Run this to debug if the bot can't post in certain channels",
                "parameters": [],
                "usage_examples": [],
                "tips_and_warnings": [],
                "related_commands": [],
                "common_errors": []
            }
        ]
    },
    "judge": {
        "title": "👨‍⚖️ Judge Commands",
        "description": "Special commands for tournament judges",
        "commands": [
            {
                "name": "Take Schedule Button",
                "description": "Click the 'Take Schedule' button on event posts to assign yourself as judge",
                "usage": "Click button on event announcements",
                "permissions": "judge / head_organizer",
                "example": "Look for green 'Take Schedule' buttons in the schedule channel",
                "parameters": [],
                "usage_examples": [
                    {
                        "scenario": "Volunteering to judge a match",
                        "command": "Click 'Take Schedule' button",
                        "explanation": "Assigns you as the judge for that specific match and adds you to the event channel"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "tip",
                        "content": "You'll be automatically added to the event channel when you take a schedule"
                    },
                    {
                        "type": "note",
                        "content": "Make sure you're available at the scheduled time before taking a schedule"
                    },
                    {
                        "type": "warning",
                        "content": "Once taken, the schedule is assigned to you - be responsible and show up"
                    }
                ],
                "related_commands": ["/unassigned_events", "/event-result"],
                "common_errors": [
                    {
                        "error": "Button already taken by another judge",
                        "solution": "Look for other unassigned events or check /unassigned_events"
                    }
                ]
            },
            {
                "name": "/event-result",
                "description": "Record official match results with Group support and comprehensive tracking",
                "usage": "/event-result winner:<@user> winner_score:<score> loser:<@user> loser_score:<score> tournament:<name> round:<round> [group:<A-J>] [remarks:<text>] [screenshots:<1-11>]",
                "permissions": "judge / head_organizer",
                "example": "Use after completing a match you judged to record the official result with group information and evidence",
                "round_options": "R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, Qualifier, Semi Final, Final",
                "group_options": "Group A, Group B, Group C, Group D, Group E, Group F, Group G, Group H, Group I, Group J",
                "parameters": [
                    {
                        "name": "winner",
                        "type": "user",
                        "required": True,
                        "description": "Discord user mention for the winning captain",
                        "constraints": "Must be one of the captains from the match you judged",
                        "examples": ["@WinningCaptain"]
                    },
                    {
                        "name": "winner_score",
                        "type": "integer",
                        "required": True,
                        "description": "Final score of the winning team",
                        "constraints": "Must be a positive integer, higher than loser_score",
                        "examples": ["3", "5", "7"]
                    },
                    {
                        "name": "loser",
                        "type": "user",
                        "required": True,
                        "description": "Discord user mention for the losing captain",
                        "constraints": "Must be the other captain from the match you judged",
                        "examples": ["@LosingCaptain"]
                    },
                    {
                        "name": "loser_score",
                        "type": "integer",
                        "required": True,
                        "description": "Final score of the losing team",
                        "constraints": "Must be a non-negative integer, lower than winner_score",
                        "examples": ["1", "2", "0"]
                    },
                    {
                        "name": "tournament",
                        "type": "string",
                        "required": True,
                        "description": "Tournament name (must match the event)",
                        "constraints": "Must exactly match the tournament name from the scheduled event",
                        "examples": ["Winter Cup", "Summer Championship"]
                    },
                    {
                        "name": "round",
                        "type": "choice",
                        "required": True,
                        "description": "Tournament round (must match the event)",
                        "constraints": "Must match the round from the scheduled event",
                        "examples": ["R1", "Semi Final", "Final"]
                    },
                    {
                        "name": "group",
                        "type": "choice",
                        "required": False,
                        "description": "Group designation if applicable",
                        "constraints": "Must match the group from the scheduled event if it had one",
                        "examples": ["Group A", "Group B"]
                    },
                    {
                        "name": "remarks",
                        "type": "string",
                        "required": False,
                        "description": "Judge's notes about the match",
                        "constraints": "Any relevant observations or notes",
                        "examples": ["Fair play from both teams", "Technical issue resolved quickly"]
                    },
                    {
                        "name": "screenshots",
                        "type": "integer",
                        "required": False,
                        "description": "Number of result screenshots to attach",
                        "constraints": "1-11 screenshots showing match results",
                        "examples": ["2", "3", "5"]
                    }
                ],
                "usage_examples": [
                    {
                        "scenario": "Recording a judged match result",
                        "command": "/event-result winner:@TeamA winner_score:3 loser:@TeamB loser_score:1 tournament:Winter Cup round:R1 group:Group A screenshots:2",
                        "explanation": "Records the result of a Group A match you just judged, with 2 screenshot attachments"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "warning",
                        "content": "Only record results for matches you actually judged - accuracy is crucial"
                    },
                    {
                        "type": "tip",
                        "content": "Take screenshots during the match to have evidence ready"
                    },
                    {
                        "type": "note",
                        "content": "Double-check all details before submitting - results are permanent"
                    }
                ],
                "related_commands": ["Take Schedule Button", "/unassigned_events"],
                "common_errors": [
                    {
                        "error": "Tournament/round mismatch with scheduled event",
                        "solution": "Use the exact tournament name and round from the original event creation"
                    },
                    {
                        "error": "Recording result for match you didn't judge",
                        "solution": "Only record results for matches you were officially assigned to judge"
                    }
                ]
            },
            {
                "name": "/unassigned_events",
                "description": "View events without assigned judges to help with scheduling",
                "usage": "/unassigned_events",
                "permissions": "judge / head_organizer",
                "example": "Use `/unassigned_events` to see which matches need judges",
                "parameters": [],
                "usage_examples": [
                    {
                        "scenario": "Finding matches to judge",
                        "command": "/unassigned_events",
                        "explanation": "Shows all scheduled matches that still need a judge assigned"
                    }
                ],
                "tips_and_warnings": [
                    {
                        "type": "tip",
                        "content": "Use this to find matches you can volunteer to judge"
                    },
                    {
                        "type": "note",
                        "content": "Check the times carefully to make sure you're available"
                    }
                ],
                "related_commands": ["Take Schedule Button", "/event-result"],
                "common_errors": []
            }
        ]
    }
}

def get_user_permission_level(user: discord.Member) -> str:
    """Determine user's permission level based on their Discord roles and ID"""
    try:
        # Check for bot owner (always owner level)
        if user.id == BOT_OWNER_ID:
            return "owner"
            
        role_ids = [role.id for role in user.roles]
        
        # Check for organizer roles
        org_role_ids = (
            ROLE_IDS.get("head_organizer", []) + 
            ROLE_IDS.get("deputy_server_head", []) + 
            ROLE_IDS.get("Tournament_organizer", []) + 
            ROLE_IDS.get("Tournament_supervision", [])
        )
        if any(rid in role_ids for rid in org_role_ids):
            return "organizer"
            
        # Check for helper roles
        helper_role_ids = ROLE_IDS["head_helper"] + ROLE_IDS["helper_team"]
        if any(rid in role_ids for rid in helper_role_ids):
            return "helper"
            
        # Check for judge roles
        judge_role_ids = ROLE_IDS["judge"]
        if any(rid in role_ids for rid in judge_role_ids):
            return "judge"
            
        return "user"
    except Exception as e:
        print(f"Error determining user permission level: {e}")
        return "user"

def filter_commands_by_permission(permission_level: str) -> dict:
    """Filter and group command data into role-based buckets for the help menu"""
    try:
        grouped_data = {
            "general": {
                "title": "📖 General Commands",
                "description": "Basic tools available to everyone",
                "commands": COMMAND_DATA["system"]["commands"] + COMMAND_DATA["utility"]["commands"]
            },
            "rules": COMMAND_DATA["rules"]
        }
        
        # Helper Category (create, edit, captains, delete, etc.)
        if permission_level in ["owner", "organizer", "helper"]:
            helper_cmds = [cmd for cmd in COMMAND_DATA["event_management"]["commands"] 
                          if cmd["name"] in ["/event-create", "/event-edit", "/event-delete", "/unassigned_events", "/add_captain", "/exchange", "/general_tie_breaker"]]
            grouped_data["helper"] = {
                "title": "🛡️ Helper Commands",
                "description": "Tournament management & match setup",
                "commands": helper_cmds
            }
            
        # Judge Category (results, unassigned)
        if permission_level in ["owner", "organizer", "helper", "judge"]:
            grouped_data["judge"] = {
                "title": "👨‍⚖️ Judge Commands",
                "description": "Match result recording and scheduling",
                "commands": COMMAND_DATA["judge"]["commands"]
            }
            
        # Organizer Category (Deletions, system tests)
        if permission_level in ["owner", "organizer"]:
            org_cmds = [cmd for cmd in COMMAND_DATA["event_management"]["commands"] 
                       if cmd["name"] in ["/event-delete", "/test_channels", "/event-edit"]]
            grouped_data["organizer"] = {
                "title": "⚙️ Organizer Commands",
                "description": "Administrative tournament control",
                "commands": org_cmds
            }
        
        return grouped_data
    except Exception as e:
        print(f"Error filtering commands by permission: {e}")
        return {
            "general": {
                "title": "📖 General Commands",
                "description": "Basic tools",
                "commands": COMMAND_DATA["system"]["commands"]
            }
        }

def build_help_embed(permission_level: str, user_name: str) -> discord.Embed:
    """Build a concise help overview with role-based navigation"""
    try:
        embed = discord.Embed(
            title=f"🎯 {ORGANIZATION_NAME} Help Center",
            description=f"Hello **{user_name}**! 👋\nPlease select your role below to view only the commands you need.\n\n*Current Access Level: {permission_level.title()}*",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Add Tutorial Videos section (Keep this as requested)
        tutorial_text = (
            "🎥 [Create Events](https://youtu.be/Xo0CipufKaM) | [Add Captains](https://youtu.be/4zAQ7pMcsFM)\n"
            "🎥 [Post Results](https://youtu.be/fQupdX9aCHI) | [Staff Exchange](https://youtu.be/vBYZSkdiyFI)\n"
            "🎥 [Delete & Choose](https://youtu.be/xSLbccfaKzE)"
        )
        embed.add_field(name="📼 Training Center", value=tutorial_text, inline=False)

        # Quick summary of what's inside
        guide_summary = (
            "📖 **General**: Rules, Time, Maps, etc.\n"
            "🛡️ **Helper**: Match setup & event management\n"
            "👨‍⚖️ **Judge**: Scheduling & result recording\n"
            "⚙️ **Organizer**: System control & Administration"
        )
        embed.add_field(name="📋 Navigation Guide", value=guide_summary, inline=False)
        
        embed.set_footer(text=f"{ORGANIZATION_NAME} • Select a category below")
        return embed
        
    except Exception as e:
        print(f"Error building help embed: {e}")
        # Fallback embed
        embed = discord.Embed(
            title="🎯 Command Guide",
            description="Error loading command information. Please try again.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"{ORGANIZATION_NAME}")
        return embed

def has_organizer_permission(interaction):
    """Check if user has organizer permissions (Bot Owner or any Head Organizer role)"""
    if interaction.user.id == BOT_OWNER_ID:
        return True
    user_role_ids = [role.id for role in interaction.user.roles]
    org_role_ids = (
        ROLE_IDS.get("head_organizer", []) + 
        ROLE_IDS.get("deputy_server_head", []) + 
        ROLE_IDS.get("Tournament_organizer", []) + 
        ROLE_IDS.get("Tournament_supervision", [])
    )
    return any(rid in user_role_ids for rid in org_role_ids)

# Embed field utility functions for safe Discord.py embed manipulation
def find_field_index(embed: discord.Embed, field_name: str) -> int:
    """Find the index of a field by name. Returns -1 if not found."""
    try:
        for i, field in enumerate(embed.fields):
            if field.name == field_name:
                return i
        return -1
    except Exception as e:
        print(f"Error finding field index: {e}")
        return -1

def remove_field_by_name(embed: discord.Embed, field_name: str) -> bool:
    """Safely remove a field by name using Discord.py methods. Returns True if removed, False if not found."""
    try:
        field_index = find_field_index(embed, field_name)
        if field_index != -1:
            embed.remove_field(field_index)
            return True
        return False
    except Exception as e:
        print(f"Error removing field by name '{field_name}': {e}")
        return False

def update_judge_field(embed: discord.Embed, judge_member: discord.Member) -> bool:
    """Update or add judge field safely. Returns True if successful."""
    try:
        # Remove existing judge field if it exists
        remove_field_by_name(embed, "👨‍⚖️ Judge")
        
        # Add new judge field
        embed.add_field(
            name="👨‍⚖️ Judge", 
            value=f"{judge_member.mention}", 
            inline=True
        )
        return True
    except Exception as e:
        print(f"Error updating judge field: {e}")
        return False

def remove_judge_field(embed: discord.Embed) -> bool:
    """Remove judge field safely. Returns True if removed, False if not found."""
    try:
        return remove_field_by_name(embed, "👨‍⚖️ Judge")
    except Exception as e:
        print(f"Error removing judge field: {e}")
        return False

def add_green_circle_to_title(title: str) -> str:
    """Add green circle emoji to the beginning of title if not already present"""
    green_circle = "🟢"
    
    # Check if already has green circle
    if title and title.startswith(green_circle):
        return title
    
    # Add green circle to beginning
    return green_circle + (title or "")

def update_embed_title_with_green_circle(embed: discord.Embed) -> bool:
    """Update embed title with green circle, returns success status"""
    try:
        if embed.title:
            new_title = add_green_circle_to_title(embed.title)
            embed.title = new_title
            return True
        return False
    except Exception as e:
        print(f"Error updating embed title with green circle: {e}")
        return False

def replace_green_circle_with_checkmark(title: str) -> str:
    """Replace green circle emoji with checkmark emoji in title"""
    green_circle = "🟢"
    checkmark = "✅"
    
    if title and title.startswith(green_circle):
        return checkmark + title[len(green_circle):]
    
    # If no green circle, just add checkmark at the beginning
    return checkmark + (title or "")

def update_embed_title_with_checkmark(embed: discord.Embed) -> bool:
    """Update embed title with checkmark, returns success status"""
    try:
        if embed.title:
            new_title = replace_green_circle_with_checkmark(embed.title)
            embed.title = new_title
            return True
        return False
    except Exception as e:
        print(f"Error updating embed title with checkmark: {e}")
        return False


class JudgeLeaderboardView(View):
    """View for staff leaderboard with reset functionality"""
    
    def __init__(self, show_reset: bool = False):
        super().__init__(timeout=300)  # 5 minute timeout
        self.show_reset = show_reset
        
        if not show_reset:
            # Remove the reset button if user doesn't have permission
            self.clear_items()
    
    @discord.ui.button(label="🔄 Reset Leaderboard", style=discord.ButtonStyle.danger, emoji="🔄")
    async def reset_leaderboard(self, interaction: discord.Interaction, button: Button):
        """Reset staff leaderboard (Head Organizer only)"""
        # Double-check permissions (Bot Owner or Head Organizer)
        if not has_organizer_permission(interaction):
            await interaction.response.send_message("❌ You need **Head Organizer** role to reset the leaderboard.", ephemeral=True)
            return
        
        # Create confirmation view
        confirm_view = ConfirmResetView()
        await interaction.response.send_message(
            "⚠️ **WARNING**: This will permanently delete all staff statistics!\n\n"
            "Are you sure you want to reset the staff leaderboard?",
            view=confirm_view,
            ephemeral=True
        )

class ConfirmResetView(View):
    """Confirmation view for resetting staff leaderboard"""
    
    def __init__(self):
        super().__init__(timeout=60)  # 1 minute timeout for confirmation
    
    @discord.ui.button(label="✅ Yes, Reset", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_reset(self, interaction: discord.Interaction, button: Button):
        """Confirm reset of staff leaderboard"""
        try:
            # Reset the statistics
            reset_staff_stats()
            
            await interaction.response.edit_message(
                content="✅ **Staff leaderboard has been reset successfully!**\n\n"
                        "All statistics have been cleared.",
                view=None
            )
            
            print(f"Staff leaderboard reset by {interaction.user.display_name} (ID: {interaction.user.id})")
            
        except Exception as e:
            print(f"Error resetting staff leaderboard: {e}")
            await interaction.response.edit_message(
                content="❌ **Error resetting leaderboard.** Please try again.",
                view=None
            )
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_reset(self, interaction: discord.Interaction, button: Button):
        """Cancel reset operation"""
        await interaction.response.edit_message(
            content="✅ **Reset cancelled.** Judge leaderboard remains unchanged.",
            view=None
        )

class HelpNavigationView(View):
    """Interactive help navigation with category buttons"""
    
    def __init__(self, permission_level: str, user_name: str):
        super().__init__(timeout=300)  # 5 minute timeout
        self.permission_level = permission_level
        self.user_name = user_name
        
    @discord.ui.button(label="📖 General", style=discord.ButtonStyle.primary, emoji="📖")
    async def general_commands(self, interaction: discord.Interaction, button: Button):
        """Show general commands"""
        await self.show_category(interaction, "general")

    @discord.ui.button(label="📜 Rules", style=discord.ButtonStyle.primary, emoji="📜")
    async def rules_section(self, interaction: discord.Interaction, button: Button):
        """Show command rules section"""
        await self.show_category(interaction, "rules")
    
    @discord.ui.button(label="🛡️ Helper", style=discord.ButtonStyle.success, emoji="🛡️")
    async def helper_commands(self, interaction: discord.Interaction, button: Button):
        """Show helper commands"""
        if self.permission_level in ["owner", "organizer", "helper"]:
            await self.show_category(interaction, "helper")
        else:
            await interaction.response.send_message("❌ Limited to **Helpers** and above.", ephemeral=True)
    
    @discord.ui.button(label="👨‍⚖️ Judge", style=discord.ButtonStyle.success, emoji="👨‍⚖️")
    async def judge_commands(self, interaction: discord.Interaction, button: Button):
        """Show judge commands"""
        if self.permission_level in ["owner", "organizer", "helper", "judge"]:
            await self.show_category(interaction, "judge")
        else:
            await interaction.response.send_message("❌ Limited to **Judges** and above.", ephemeral=True)

    @discord.ui.button(label="⚙️ Organizer", style=discord.ButtonStyle.danger, emoji="⚙️")
    async def org_commands(self, interaction: discord.Interaction, button: Button):
        """Show organizer commands"""
        if self.permission_level in ["owner", "organizer"]:
            await self.show_category(interaction, "organizer")
        else:
            await interaction.response.send_message("❌ Limited to **Organizers**.", ephemeral=True)
    
    @discord.ui.button(label="🔄 Back to Overview", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def back_to_overview(self, interaction: discord.Interaction, button: Button):
        """Return to main help overview"""
        embed = build_help_embed(self.permission_level, self.user_name)
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def show_category(self, interaction: discord.Interaction, category: str):
        """Show detailed information for a specific category"""
        try:
            filtered_commands = filter_commands_by_permission(self.permission_level)
            
            if category not in filtered_commands:
                await interaction.response.send_message("❌ Category not found or not accessible.", ephemeral=True)
                return
            
            category_data = filtered_commands[category]
            
            # Create detailed category embed
            embed = discord.Embed(
                title=f"{category_data['title']} - Detailed View",
                description=category_data['description'],
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            # Add each command with full details
            for cmd in category_data["commands"]:
                command_text = f"**Usage:** `{cmd['usage']}`\n"
                command_text += f"**Permissions:** {cmd['permissions']}\n"
                
                # Add parameters if available
                if cmd.get('parameters') and len(cmd['parameters']) > 0:
                    command_text += f"**Parameters:**\n"
                    for param in cmd['parameters']:
                        required_text = "Required" if param['required'] else f"Optional (default: {param.get('default', 'None')})"
                        command_text += f"• `{param['name']}` ({param['type']}) - {required_text}\n"
                        command_text += f"  └ {param['description']}\n"
                        if param.get('constraints'):
                            command_text += f"  └ Constraints: {param['constraints']}\n"
                
                # Add usage examples
                if cmd.get('usage_examples') and len(cmd['usage_examples']) > 0:
                    command_text += f"**Examples:**\n"
                    for example in cmd['usage_examples'][:2]:  # Limit to 2 examples to save space
                        command_text += f"• {example['scenario']}: `{example['command']}`\n"
                
                # Add tips and warnings
                if cmd.get('tips_and_warnings') and len(cmd['tips_and_warnings']) > 0:
                    for tip in cmd['tips_and_warnings'][:2]:  # Limit to 2 tips
                        if tip['type'] == 'warning':
                            command_text += f"⚠️ **Warning:** {tip['content']}\n"
                        elif tip['type'] == 'tip':
                            command_text += f"💡 **Tip:** {tip['content']}\n"
                        elif tip['type'] == 'note':
                            command_text += f"📝 **Note:** {tip['content']}\n"
                
                # Truncate if too long for Discord embed field limit
                if len(command_text) > 1024:
                    command_text = command_text[:1020] + "..."
                
                embed.add_field(
                    name=f"{cmd['name']}",
                    value=command_text,
                    inline=False
                )
            
            embed.set_footer(text=f"{ORGANIZATION_NAME} • Detailed Help")
            
            # Create view with command detail buttons
            view = CommandDetailView(self.permission_level, self.user_name, category_data["commands"])
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            print(f"Error showing category {category}: {e}")
            await interaction.response.send_message("❌ Error loading category details.", ephemeral=True)

class CommandDetailView(View):
    """View for showing individual command details"""
    
    def __init__(self, permission_level: str, user_name: str, commands: list):
        super().__init__(timeout=300)
        self.permission_level = permission_level
        self.user_name = user_name
        self.commands = commands
        
        # Add buttons for each command (limit to 5 to fit Discord limits)
        for i, cmd in enumerate(commands[:5]):
            button = Button(
                label=cmd['name'].replace('/', ''),
                style=discord.ButtonStyle.secondary,
                custom_id=f"cmd_{i}"
            )
            button.callback = self.create_command_callback(i)
            self.add_item(button)
    
    def create_command_callback(self, cmd_index: int):
        """Create callback for command detail button"""
        async def callback(interaction: discord.Interaction):
            await self.show_command_detail(interaction, cmd_index)
        return callback
    
    @discord.ui.button(label="🔄 Back to Categories", style=discord.ButtonStyle.primary, emoji="🔄", row=2)
    async def back_to_categories(self, interaction: discord.Interaction, button: Button):
        """Return to category navigation"""
        embed = build_help_embed(self.permission_level, self.user_name)
        view = HelpNavigationView(self.permission_level, self.user_name)
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def show_command_detail(self, interaction: discord.Interaction, cmd_index: int):
        """Show detailed information for a specific command"""
        try:
            if cmd_index >= len(self.commands):
                await interaction.response.send_message("❌ Command not found.", ephemeral=True)
                return
            
            cmd = self.commands[cmd_index]
            
            # Create detailed command embed
            embed = discord.Embed(
                title=f"📖 {cmd['name']} - Complete Guide",
                description=cmd['description'],
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Basic information
            embed.add_field(
                name="ℹ️ Basic Information",
                value=f"**Usage:** `{cmd['usage']}`\n**Permissions:** {cmd['permissions']}",
                inline=True
            )
            
            # Video tutorial if available
            if cmd.get('tutorial_url'):
                embed.add_field(
                    name="🎥 Video Tutorial",
                    value=f"[Watch Guide]({cmd['tutorial_url']})",
                    inline=True
                )
            
            # Parameters section
            if cmd.get('parameters') and len(cmd['parameters']) > 0:
                param_text = ""
                for param in cmd['parameters']:
                    required_text = "✅ Required" if param['required'] else f"⚪ Optional (default: {param.get('default', 'None')})"
                    param_text += f"**`{param['name']}`** ({param['type']}) - {required_text}\n"
                    param_text += f"└ {param['description']}\n"
                    if param.get('constraints'):
                        param_text += f"└ **Constraints:** {param['constraints']}\n"
                    if param.get('examples'):
                        param_text += f"└ **Examples:** {', '.join(param['examples'][:3])}\n"
                    param_text += "\n"
                
                if len(param_text) > 1024:
                    param_text = param_text[:1020] + "..."
                
                embed.add_field(
                    name="⚙️ Parameters",
                    value=param_text,
                    inline=False
                )
            
            # Usage examples
            if cmd.get('usage_examples') and len(cmd['usage_examples']) > 0:
                example_text = ""
                for i, example in enumerate(cmd['usage_examples'][:3], 1):
                    example_text += f"**{i}. {example['scenario']}**\n"
                    example_text += f"`{example['command']}`\n"
                    example_text += f"└ {example['explanation']}\n\n"
                
                if len(example_text) > 1024:
                    example_text = example_text[:1020] + "..."
                
                embed.add_field(
                    name="💡 Usage Examples",
                    value=example_text,
                    inline=False
                )
            
            # Tips and warnings
            if cmd.get('tips_and_warnings') and len(cmd['tips_and_warnings']) > 0:
                tips_text = ""
                for tip in cmd['tips_and_warnings']:
                    if tip['type'] == 'warning':
                        tips_text += f"⚠️ **Warning:** {tip['content']}\n\n"
                    elif tip['type'] == 'tip':
                        tips_text += f"💡 **Tip:** {tip['content']}\n\n"
                    elif tip['type'] == 'note':
                        tips_text += f"📝 **Note:** {tip['content']}\n\n"
                
                if len(tips_text) > 1024:
                    tips_text = tips_text[:1020] + "..."
                
                embed.add_field(
                    name="📋 Tips & Warnings",
                    value=tips_text,
                    inline=False
                )
            
            # Related commands and common errors
            footer_text = ""
            if cmd.get('related_commands') and len(cmd['related_commands']) > 0:
                footer_text += f"Related: {', '.join(cmd['related_commands'][:5])}"
            
            if cmd.get('common_errors') and len(cmd['common_errors']) > 0:
                error_text = "\n\n**Common Issues:**\n"
                for error in cmd['common_errors'][:2]:
                    error_text += f"• {error['error']}: {error['solution']}\n"
                footer_text += error_text
            
            if footer_text and len(footer_text) < 1024:
                embed.add_field(
                    name="🔗 Additional Information",
                    value=footer_text,
                    inline=False
                )
            
            embed.set_footer(text=f"{ORGANIZATION_NAME} • Command Details")
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            print(f"Error showing command detail: {e}")
            await interaction.response.send_message("❌ Error loading command details.", ephemeral=True)

class TakeScheduleButton(View):
    def __init__(self, event_id: str, team1_captain: any, team2_captain: any, event_channel: discord.TextChannel = None):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.team1_captain = team1_captain
        self.team2_captain = team2_captain
        self.event_channel = event_channel
        self.judge = None
        self.recorder = None
        self._taking_schedule = False  # Flag to prevent race conditions
        
    @discord.ui.button(label="Take Judge", style=discord.ButtonStyle.green, emoji="👨‍⚖️")
    async def take_judge(self, interaction: discord.Interaction, button: Button):
        await self.handle_take_role(interaction, button, "judge")

    @discord.ui.button(label="Take Recorder", style=discord.ButtonStyle.blurple, emoji="📹")
    async def take_recorder(self, interaction: discord.Interaction, button: Button):
        await self.handle_take_role(interaction, button, "recorder")

    async def handle_take_role(self, interaction: discord.Interaction, button: Button, role_type: str):
        # Prevent race conditions
        if self._taking_schedule:
            await interaction.response.send_message("⏳ Request processing. Please wait.", ephemeral=True)
            return

        # Check if match has already started
        if self.event_id in scheduled_events:
            event_data = scheduled_events[self.event_id]
            match_time = event_data.get('datetime')
            if match_time:
                # Ensure timezone awareness
                if match_time.tzinfo is None:
                    match_time = match_time.replace(tzinfo=pytz.UTC)
                
                now = datetime.datetime.now(pytz.UTC)
                if now > match_time:
                    # Disable buttons on the current view
                    for item in self.children:
                        if isinstance(item, discord.ui.Button):
                            item.disabled = True
                    await interaction.message.edit(view=self)
                    await interaction.response.send_message("❌ This match has already started. You can no longer take this schedule.", ephemeral=True)
                    return
            
        # Check permissions
        user_role_ids = [r.id for r in interaction.user.roles]
        
        allowed = False
        org_role_ids = (
            ROLE_IDS.get("head_organizer", []) + 
            ROLE_IDS.get("deputy_server_head", []) + 
            ROLE_IDS.get("Tournament_organizer", []) + 
            ROLE_IDS.get("Tournament_supervision", [])
        )
        if role_type == "judge":
            is_judge = any(rid in user_role_ids for rid in ROLE_IDS["judge"])
            is_org = any(rid in user_role_ids for rid in org_role_ids)
            if is_judge or is_org:
                allowed = True
            if self.judge:
                await interaction.response.send_message(f"❌ Judge already assigned: {self.judge.display_name}", ephemeral=True)
                return
        elif role_type == "recorder":
            is_recorder = any(rid in user_role_ids for rid in ROLE_IDS["recorder"])
            is_org = any(rid in user_role_ids for rid in org_role_ids)
            if is_recorder or is_org:
                allowed = True
            if self.recorder:
                await interaction.response.send_message(f"❌ Recorder already assigned: {self.recorder.display_name}", ephemeral=True)
                return

        if not allowed:
            await interaction.response.send_message(f"❌ You need the **{role_type.title()}** role to take this spot.", ephemeral=True)
            return
        
        self._taking_schedule = True
        try:
            await interaction.response.defer(ephemeral=True)
            
            # double check availability
            if role_type == "judge" and self.judge:
                 await interaction.followup.send("❌ Already taken.", ephemeral=True)
                 return
            if role_type == "recorder" and self.recorder:
                 await interaction.followup.send("❌ Already taken.", ephemeral=True)
                 return

            # Assign
            if role_type == "judge":
                self.judge = interaction.user
                button.label = f"Judge: {interaction.user.display_name}"
                button.disabled = True
                button.style = discord.ButtonStyle.gray
                
                # Update sheet
                sheet_manager.update_event_staff(self.event_id, judge_name=self.judge.name)
                
            else:
                self.recorder = interaction.user
                button.label = f"Recorder: {interaction.user.display_name}"
                button.disabled = True
                button.style = discord.ButtonStyle.gray

                # Update sheet
                sheet_manager.update_event_staff(self.event_id, recorder_name=self.recorder.name)

            # Update embed
            embed = interaction.message.embeds[0]
            self.update_embed_fields(embed)
            
            await interaction.message.edit(embed=embed, view=self)
            await interaction.followup.send(f"✅ You have taken the **{role_type.title()}** slot!", ephemeral=True)
            
            # Update internal state
            if self.event_id in scheduled_events:
                if role_type == "judge":
                    scheduled_events[self.event_id]['judge'] = self.judge
                else:
                    scheduled_events[self.event_id]['recorder'] = self.recorder
                save_scheduled_events()

            # Notify and Add to channel
            await self.send_assignment_notification(interaction.user, role_type)

        except Exception as e:
            print(f"Error taking {role_type}: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        finally:
            self._taking_schedule = False

    def update_embed_fields(self, embed):
        # Update Judge Field
        remove_field_by_name(embed, "👨‍⚖️ Judge")
        remove_field_by_name(embed, "📹 Recorder")
        
        if self.judge:
            embed.add_field(name="👨‍⚖️ Judge", value=self.judge.mention, inline=True)
        if self.recorder:
            embed.add_field(name="📹 Recorder", value=self.recorder.mention, inline=True)
            
    async def send_assignment_notification(self, member: discord.Member, role_type: str):
        if not self.event_channel: return
        try:
            await self.event_channel.set_permissions(
                member, read_messages=True, send_messages=True, embed_links=True, attach_files=True
            )
            await self.event_channel.send(
                f"🔔 {member.mention} has been assigned as the **{role_type.title()}** for this match!"
            )
        except Exception as e:
            print(f"Error adding to channel: {e}")
    
    





# ===========================================================================================
# RULE MANAGEMENT UI COMPONENTS
# ===========================================================================================

class RuleInputModal(discord.ui.Modal):
    """Modal for entering/editing rule content"""
    
    def __init__(self, title: str, current_content: str = ""):
        super().__init__(title=title)
        
        # Text input field for rule content
        self.rule_input = discord.ui.TextInput(
            label="Tournament Rules",
            placeholder="Enter the tournament rules here...",
            default=current_content,
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=False
        )
        self.add_item(self.rule_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Get the content from the input
            content = self.rule_input.value.strip()
            
            # Save the rules
            success = set_rules_content(content, interaction.user.id, interaction.user.name)
            
            if success:
                # Create confirmation embed
                embed = discord.Embed(
                    title="✅ Rules Updated Successfully",
                    description="Tournament rules have been saved.",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                if content:
                    # Show preview of rules (truncated if too long)
                    preview = content[:500] + "..." if len(content) > 500 else content
                    embed.add_field(name="Rules Preview", value=f"```\n{preview}\n```", inline=False)
                else:
                    embed.add_field(name="Status", value="Rules have been cleared (empty)", inline=False)
                
                embed.set_footer(text=f"Updated by {interaction.user.name}")
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ Failed to save rules. Please try again.", ephemeral=True)
                
        except Exception as e:
            print(f"Error in rule modal submission: {e}")
            await interaction.response.send_message("❌ An error occurred while saving rules.", ephemeral=True)

class RulesManagementView(discord.ui.View):
    """Interactive view for organizers with rule management buttons"""
    
    def __init__(self):
        super().__init__(timeout=300)  # 5 minute timeout
    
    @discord.ui.button(label="Enter Rules", style=discord.ButtonStyle.green, emoji="📝")
    async def enter_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to enter new rules"""
        modal = RuleInputModal("Enter Tournament Rules")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Reedit Rules", style=discord.ButtonStyle.primary, emoji="✏️")
    async def reedit_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to edit existing rules"""
        current_rules = get_current_rules()
        
        if not current_rules:
            await interaction.response.send_message("❌ No rules are currently set. Use 'Enter Rules' to create new rules.", ephemeral=True)
            return
        
        modal = RuleInputModal("Edit Tournament Rules", current_rules)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Show Rules", style=discord.ButtonStyle.secondary, emoji="👁️")
    async def show_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to display current rules"""
        await display_rules(interaction)

async def display_rules(interaction: discord.Interaction):
    """Display current tournament rules in an embed"""
    try:
        global tournament_rules
        current_rules = get_current_rules()
        
        if not current_rules:
            embed = discord.Embed(
                title="📋 Tournament Rules",
                description="No tournament rules have been set yet.",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text="Winterfell Arena Esports Tournament System")
        else:
            embed = discord.Embed(
                title="📋 Tournament Rules",
                description=current_rules,
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Add metadata if available
            if 'rules' in tournament_rules and 'last_updated' in tournament_rules['rules']:
                updated_by = tournament_rules['rules'].get('updated_by', {}).get('username', 'Unknown')
                embed.set_footer(text=f"Winterfell Arena Esports • Last updated by {updated_by}")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
    except Exception as e:
        print(f"Error displaying rules: {e}")
        await interaction.response.send_message("❌ An error occurred while displaying rules.", ephemeral=False)

# ===========================================================================================
# NOTIFICATION AND REMINDER SYSTEM (Ten-minute reminder for captains and judge)
# ===========================================================================================

async def send_ten_minute_reminder(event_id: str, team1_captain: discord.Member, team2_captain: discord.Member, judge: Optional[discord.Member], event_channel: discord.TextChannel, match_time: datetime.datetime):
    """Send 10-minute reminder notification to judge, recorder and captains"""
    try:
        if not event_channel:
            return

        # Get the latest data from scheduled_events if available
        team1_name = "Team 1"
        team2_name = "Team 2"
        tournament_name = "Tournament"
        round_name = "Match"
        resolved_judge = judge
        resolved_recorder = None
        
        if event_id in scheduled_events:
            event_data = scheduled_events[event_id]
            resolved_judge = event_data.get('judge', resolved_judge)
            resolved_recorder = event_data.get('recorder', resolved_recorder)
            team1_captain = event_data.get('team1_captain', team1_captain)
            team2_captain = event_data.get('team2_captain', team2_captain)
            team1_name = event_data.get('team1_name', "Team 1")
            team2_name = event_data.get('team2_name', "Team 2")
            tournament_name = event_data.get('tournament', "Tournament")
            round_name = event_data.get('round', "Match")

        # Create embed
        embed = discord.Embed(
            title="⏰ 10-MINUTE MATCH REMINDER",
            description=f"**Your tournament match is starting in 10 minutes!**",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="⚔️ Match-up", value=f"**{team1_name}** vs **{team2_name}**", inline=False)
        embed.add_field(name="🏆 Tournament", value=tournament_name, inline=True)
        embed.add_field(name="📍 Round", value=round_name, inline=True)
        embed.add_field(name="🕔 Start Time", value=f"<t:{int(match_time.timestamp())}:F>", inline=False)
        
        embed.set_footer(text=f"{ORGANIZATION_NAME} • Match Reminder")
        
        def get_mention(obj):
            if obj is None: return ""
            if hasattr(obj, 'mention'): return obj.mention
            if isinstance(obj, (int, str)):
                s_obj = str(obj)
                if s_obj.startswith('<@'): return s_obj
                if s_obj.isdigit(): return f"<@{s_obj}>"
            return str(obj)

        # Pings
        ping_list = []
        for person in [team1_captain, team2_captain, resolved_judge, resolved_recorder]:
            mention = get_mention(person)
            if mention:
                ping_list.append(mention)
        
        pings = " ".join(ping_list)
        
        notification_text = f"🔔 **MATCH REMINDER**\n\n{pings}\n\nYour match starts in **10 minutes**!"
        await event_channel.send(content=notification_text, embed=embed)

    except Exception as e:
        print(f"Error sending 10-minute reminder for event {event_id}: {e}")


async def schedule_ten_minute_reminder(event_id: str, team1_captain: discord.Member, team2_captain: discord.Member, judge: Optional[discord.Member], event_channel: discord.TextChannel, match_time: datetime.datetime):
    """Schedule a 10-minute reminder for the match"""
    try:
        # Calculate when to send the 10-minute reminder
        reminder_time = match_time - datetime.timedelta(minutes=10)
        now = datetime.datetime.now(pytz.UTC)

        # Ensure match_time and reminder_time are timezone-aware UTC
        if match_time.tzinfo is None:
            match_time = match_time.replace(tzinfo=pytz.UTC)
            reminder_time = match_time - datetime.timedelta(minutes=10)

        # Check if reminder time is in the future
        if reminder_time <= now:
            print(f"Reminder time for event {event_id} is in the past, skipping")
            return

        # Calculate delay in seconds
        delay_seconds = (reminder_time - now).total_seconds()

        async def reminder_task():
            try:
                await asyncio.sleep(delay_seconds)
                await send_ten_minute_reminder(event_id, team1_captain, team2_captain, judge, event_channel, match_time)
            except asyncio.CancelledError:
                print(f"Reminder task for event {event_id} was cancelled")
            except Exception as e:
                print(f"Error in reminder task for event {event_id}: {e}")

        # Cancel existing reminder if any
        if event_id in reminder_tasks:
            reminder_tasks[event_id].cancel()

        # Schedule new reminder
        reminder_tasks[event_id] = asyncio.create_task(reminder_task())
        print(f"10-minute reminder scheduled for event {event_id} at {reminder_time}")
    except Exception as e:
        print(f"Error scheduling 10-minute reminder for event {event_id}: {e}")


async def schedule_event_reminder_v2(event_id: str, team1_captain: discord.Member, team2_captain: discord.Member, judge: Optional[discord.Member], event_channel: discord.TextChannel):
    """Schedule event reminder with 10-minute notification using stored event datetime"""
    try:
        if event_id not in scheduled_events:
            print(f"Event {event_id} not found in scheduled_events")
            return
        event_data = scheduled_events[event_id]
        match_time = event_data.get('datetime')
        if not match_time:
            print(f"No datetime found for event {event_id}")
            return
        # Ensure timezone-aware UTC
        if match_time.tzinfo is None:
            match_time = match_time.replace(tzinfo=pytz.UTC)
        await schedule_ten_minute_reminder(event_id, team1_captain, team2_captain, judge, event_channel, match_time)
    except Exception as e:
        print(f"Error in schedule_event_reminder_v2 for event {event_id}: {e}")



async def schedule_event_cleanup(event_id: str, delay_hours: int = 2):
    """Schedule cleanup to remove an event after delay_hours (default 2h)."""
    try:
        if event_id not in scheduled_events:
            return
        delay_seconds = delay_hours * 3600

        async def cleanup_task():
            try:
                await asyncio.sleep(delay_seconds)
                data = scheduled_events.get(event_id)
                if not data:
                    return
                # Delete original schedule message if known
                try:
                    guilds = bot.guilds
                    for guild in guilds:
                        ch_id = data.get('schedule_channel_id')
                        msg_id = data.get('schedule_message_id')
                        if ch_id and msg_id:
                            channel = guild.get_channel(ch_id)
                            if channel:
                                try:
                                    msg = await channel.fetch_message(msg_id)
                                    await msg.delete()
                                except discord.NotFound:
                                    pass
                                except Exception as e:
                                    print(f"Error deleting schedule message for {event_id}: {e}")
                except Exception as e:
                    print(f"Guild/channel fetch error during cleanup for {event_id}: {e}")

                # Clean up poster file if any
                try:
                    poster_path = data.get('poster_path')
                    if poster_path and os.path.exists(poster_path):
                        os.remove(poster_path)
                except Exception as e:
                    print(f"Poster cleanup error for {event_id}: {e}")

                # Remove any reminder task
                try:
                    if event_id in reminder_tasks:
                        reminder_tasks[event_id].cancel()
                        del reminder_tasks[event_id]
                except Exception:
                    pass

                # Finally remove from scheduled events and persist
                try:
                    if event_id in scheduled_events:
                        del scheduled_events[event_id]
                        save_scheduled_events()
                        print(f"Event {event_id} cleaned up from memory and file")
                except Exception as e:
                    print(f"Error removing event {event_id} in cleanup: {e}")
            except asyncio.CancelledError:
                print(f"Cleanup task for event {event_id} was cancelled")
            except Exception as e:
                print(f"Error in cleanup task for event {event_id}: {e}")

        # Cancel existing cleanup if any and schedule new
        if event_id in cleanup_tasks:
            try:
                cleanup_tasks[event_id].cancel()
            except Exception:
                pass

        cleanup_tasks[event_id] = asyncio.create_task(cleanup_task())
        print(f"Cleanup scheduled for event {event_id} in {delay_hours} hours")
    except Exception as e:
        print(f"Error scheduling cleanup for event {event_id}: {e}")


# Google Fonts API Integration
def download_google_font(font_family: str, font_style: str = "regular", font_weight: str = "400") -> str:
    """Download a font from Google Fonts API and return the local file path"""
    try:
        # Google Fonts API URL
        api_url = f"https://fonts.googleapis.com/css2?family={font_family.replace(' ', '+')}:wght@{font_weight}"
        
        # Add style parameter if not regular
        if font_style != "regular":
            api_url += f"&style={font_style}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse CSS to get font URL
        css_content = response.text
        font_urls = re.findall(r'url\((https://[^)]+\.woff2?)\)', css_content)
        
        if not font_urls:
            print(f"No font URLs found in CSS for {font_family}")
            return None
        
        # Download the first font file (usually woff2)
        font_url = font_urls[0]
        font_response = requests.get(font_url, timeout=15)
        font_response.raise_for_status()
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.woff2')
        temp_file.write(font_response.content)
        temp_file.close()
        
        print(f"Downloaded Google Font: {font_family} -> {temp_file.name}")
        return temp_file.name
        
    except Exception as e:
        print(f"Error downloading Google Font {font_family}: {e}")
        return None

def get_font_with_fallbacks(font_name: str, size: int, font_style: str = "regular") -> ImageFont.FreeTypeFont:
    """Get a font using your local fonts first, then Google Fonts as fallback"""
    font_candidates = []
    
    # 1. Try your local fonts FIRST (from Fonts/ folder)
    if font_name == "DS-Digital":
        # Prioritize DS-Digital fonts when specifically requested
        local_fonts = [
            str(Path("Fonts") / "ds_digital" / "DS-DIGIB.TTF"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGII.TTF"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGI.TTF"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGIT.TTF"),
        ]
    else:
        # Default local fonts for other font requests
        local_fonts = [
            str(Path("Fonts") / "capture_it" / "Capture it.ttf"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGIB.TTF"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGII.TTF"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGI.TTF"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGIT.TTF"),
        ]
    font_candidates.extend(local_fonts)
    
    # 2. Try Google Fonts as fallback (only if local fonts fail)
    try:
        google_font_path = download_google_font(font_name, font_style)
        if google_font_path:
            font_candidates.append(google_font_path)
    except Exception as e:
        print(f"Google Fonts failed for {font_name}: {e}")
    
    # 3. Try system fonts
    system_fonts = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf", 
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/trebucbd.ttf",
    ]
    font_candidates.extend(system_fonts)
    
    # Try each font candidate
    for font_path in font_candidates:
        try:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, size)
                print(f"Successfully loaded font: {font_path}")
                return font
        except Exception as e:
            print(f"Failed to load font {font_path}: {e}")
            continue
    
    # Final fallback to default font
    print(f"All fonts failed, using default font for size {size}")
    try:
        return ImageFont.load_default().font_variant(size=size)
    except:
        return ImageFont.load_default()

def sanitize_username_for_poster(username: str) -> str:
    """Convert Discord display names to poster-friendly ASCII by stripping emojis and fancy Unicode.

    - Normalizes to NFKD and drops non-ASCII codepoints
    - Collapses repeated whitespace and trims ends
    - Falls back to 'Player' if empty after sanitization
    """
    try:
        import unicodedata
        # Normalize and strip accents/fancy letters
        normalized = unicodedata.normalize('NFKD', str(username))
        ascii_only = normalized.encode('ascii', 'ignore').decode('ascii')
        # Remove remaining characters that might be control or non-printable
        ascii_only = re.sub(r"[^\x20-\x7E]", "", ascii_only)
        # Collapse whitespace
        ascii_only = re.sub(r"\s+", " ", ascii_only).strip()
        return ascii_only if ascii_only else "Player"
    except Exception:
        return str(username) if username else "Player"

def get_random_template(mode="MW"):
    """Get a random template image based on mode (MW or MWT)"""
    # Define folder paths
    mw_path = Path("MW Templates")
    mwt_path = Path("MWT Templates")
    
    # Select folder based on mode
    target_path = mwt_path if mode == "MWT" else mw_path
    
    if target_path.exists():
        # Get all image files
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif']
        image_files = []
        for ext in image_extensions:
            # Using glob directly on the path object's glob method if strict path object, 
            # but current code uses glob module with string path
            image_files.extend(glob.glob(str(target_path / ext)))
            image_files.extend(glob.glob(str(target_path / ext.upper())))
        
        if image_files:
            return random.choice(image_files)
            
    print(f"⚠️ Template folder not found or empty: {target_path}")
    return None

def create_event_poster(template_path: str, round_label: str, team1_captain: str, team2_captain: str, utc_time: str, date_str: str = None, server_name: str = "Winterfell Arena Esports") -> str:
    """Create event poster with text overlays using Google Fonts and improved error handling"""
    print(f"Creating poster with template: {template_path}")
    
    try:
        # Validate template path
        if not os.path.exists(template_path):
            print(f"Template file not found: {template_path}")
            return None
            
        # Open the template image
        with Image.open(template_path) as img:
            print(f"Opened template image: {img.size}, mode: {img.mode}")
            
            # Convert to RGBA if needed
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Resize image to be smaller (max 800x600 to avoid Discord size limits)
            max_width, max_height = 800, 600
            width, height = img.size
            
            # Calculate new dimensions while maintaining aspect ratio
            if width > max_width or height > max_height:
                ratio = min(max_width / width, max_height / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"Resized image to: {new_width}x{new_height}")
            
            # Create a copy to work with
            poster = img.copy()
            draw = ImageDraw.Draw(poster)
            
            # Get final image dimensions
            width, height = poster.size
            
            # Load fonts using the new system with Google Fonts integration
            print("Loading fonts...")
            
            # Define font sizes based on image height (reduced for better fit)
            title_size = int(height * 0.10)
            round_size = int(height * 0.14)
            vs_size = int(height * 0.09)
            time_size = int(height * 0.07)
            tiny_size = int(height * 0.05)
            
            # Load fonts with Google Fonts fallback
            try:
                # Use Square One font for server name, DS-Digital for round, date, and time
                font_title = get_font_with_fallbacks("Square One", title_size, "bold")  # Server name
                font_round = get_font_with_fallbacks("DS-Digital", round_size, "bold")  # Round text
                # Use a unique bundled font for player names so styling is consistent regardless of Discord nickname styling
                font_vs = get_font_with_fallbacks("Capture it", vs_size, "bold")       # Unique display font from Fonts/capture_it
                font_time = get_font_with_fallbacks("DS-Digital", time_size, "bold")  # Date and time
                font_tiny = get_font_with_fallbacks("Roboto", tiny_size)              # Small text
                
                print("Fonts loaded successfully")
                
            except Exception as font_error:
                print(f"Font loading error: {font_error}")
                # Ultimate fallback to default fonts
                font_title = ImageFont.load_default()
                font_round = ImageFont.load_default()
                font_vs = ImageFont.load_default()
                font_time = ImageFont.load_default()
                font_tiny = ImageFont.load_default()
            
            # Define colors for clean visibility
            text_color = (255, 255, 255)  # Bright white
            outline_color = (0, 0, 0)     # Pure black
            yellow_color = (255, 255, 0)  # Bright yellow for important text
            
            # Helper function to draw text with outline
            def draw_text_with_outline(text, x, y, font, text_color=text_color, use_yellow=False):
                x, y = int(x), int(y)
                final_text_color = yellow_color if use_yellow else text_color
                
                # Draw thick black outline for visibility
                outline_width = 4
                for dx in range(-outline_width, outline_width + 1):
                    for dy in range(-outline_width, outline_width + 1):
                        if dx != 0 or dy != 0:
                            try:
                                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
                            except Exception as e:
                                print(f"Error drawing outline: {e}")
                
                # Draw main text on top
                try:
                    draw.text((x, y), text, font=font, fill=final_text_color)
                except Exception as e:
                    print(f"Error drawing main text: {e}")
            
            # Add server name text (top center)
            try:
                server_text = server_name
                server_bbox = draw.textbbox((0, 0), server_text, font=font_title)
                server_width = server_bbox[2] - server_bbox[0]
                server_x = (width - server_width) // 2
                server_y = int(height * 0.08)
                draw_text_with_outline(server_text, server_x, server_y, font_title)
                print(f"Added server name: {server_text}")
            except Exception as e:
                print(f"Error adding server name: {e}")
            
            # Add Round text (center) - use yellow for emphasis
            try:
                round_text = f"ROUND {round_label}"
                round_bbox = draw.textbbox((0, 0), round_text, font=font_round)
                round_width = round_bbox[2] - round_bbox[0]
                round_x = (width - round_width) // 2
                round_y = int(height * 0.35)
                draw_text_with_outline(round_text, round_x, round_y, font_round, use_yellow=True)
                print(f"Added round text: {round_text}")
            except Exception as e:
                print(f"Error adding round text: {e}")
            
            # Add Captain vs Captain text (center)
            try:
                left_name_text = sanitize_username_for_poster(team1_captain)
                vs_core = " VS "
                right_name_text = sanitize_username_for_poster(team2_captain)

                # Measure text components to center the whole line
                left_box = draw.textbbox((0, 0), left_name_text, font=font_vs)
                vs_box = draw.textbbox((0, 0), vs_core, font=font_vs)
                right_box = draw.textbbox((0, 0), right_name_text, font=font_vs)
                
                total_width = (left_box[2] - left_box[0]) + (vs_box[2] - vs_box[0]) + (right_box[2] - right_box[0])
                current_x = (width - total_width) // 2
                vs_y = int(height * 0.55)

                # Draw left name
                draw_text_with_outline(left_name_text, current_x, vs_y, font_vs)
                current_x += (left_box[2] - left_box[0])
                
                # Draw VS
                draw_text_with_outline(vs_core, current_x, vs_y, font_vs, use_yellow=False)
                current_x += (vs_box[2] - vs_box[0])
                
                # Draw right name
                draw_text_with_outline(right_name_text, current_x, vs_y, font_vs)
                
                print(f"Added VS text: {left_name_text} VS {right_name_text}")
            except Exception as e:
                print(f"Error adding VS text: {e}")
            
            # Add date (if provided)
            if date_str:
                try:
                    date_text = f"DATE:  {date_str}"
                    date_bbox = draw.textbbox((0, 0), date_text, font=font_time)
                    date_width = date_bbox[2] - date_bbox[0]
                    date_x = (width - date_width) // 2
                    date_y = int(height * 0.72)
                    draw_text_with_outline(date_text, date_x, date_y, font_time)
                    print(f"Added date: {date_text}")
                except Exception as e:
                    print(f"Error adding date: {e}")
            
            # Add UTC time
            try:
                time_text = f"TIME:  {utc_time}"
                time_bbox = draw.textbbox((0, 0), time_text, font=font_time)
                time_width = time_bbox[2] - time_bbox[0]
                time_x = (width - time_width) // 2
                time_y = int(height * 0.82) if date_str else int(height * 0.75)
                draw_text_with_outline(time_text, time_x, time_y, font_time)
                print(f"Added time: {time_text}")
            except Exception as e:
                print(f"Error adding time: {e}")
            
            # Save the modified image
            output_path = f"temp_poster_{int(datetime.datetime.now().timestamp())}.png"
            poster.save(output_path, "PNG")
            print(f"Poster saved successfully: {output_path}")
            return output_path
            
    except Exception as e:
        print(f"Critical error creating poster: {e}")
        import traceback
        traceback.print_exc()
        return None

def calculate_time_difference(event_datetime: datetime.datetime, user_timezone: str = None) -> dict:
    """Calculate time difference and format for different timezones"""
    current_time = datetime.datetime.now(pytz.UTC).replace(tzinfo=None)
    time_diff = event_datetime - current_time
    minutes_remaining = int(time_diff.total_seconds() / 60)
    
    # Format UTC time exactly as requested
    utc_time_str = event_datetime.strftime("%H:%M utc, %d/%m")
    
    # Try to detect user's local timezone
    local_timezone = None
    if user_timezone:
        try:
            local_timezone = pytz.timezone(user_timezone)
        except:
            pass
    
    # If no user timezone provided, try to detect from system
    if not local_timezone:
        try:
            # Try to get system timezone
            import time
            local_timezone = pytz.timezone(time.tzname[time.daylight])
        except:
            # Fallback to IST if detection fails
            local_timezone = pytz.timezone('Asia/Kolkata')
    
    # Calculate user's local time
    local_time = event_datetime.replace(tzinfo=pytz.UTC).astimezone(local_timezone)
    local_time_formatted = local_time.strftime("%A, %d %B, %Y %H:%M")
    
    # Calculate other common timezones
    ist_tz = pytz.timezone('Asia/Kolkata')
    ist_time = event_datetime.replace(tzinfo=pytz.UTC).astimezone(ist_tz)
    ist_formatted = ist_time.strftime("%A, %d %B, %Y %H:%M")
    
    est_tz = pytz.timezone('America/New_York')
    est_time = event_datetime.replace(tzinfo=pytz.UTC).astimezone(est_tz)
    est_formatted = est_time.strftime("%A, %d %B, %Y %H:%M")
    
    gmt_tz = pytz.timezone('Europe/London')
    gmt_time = event_datetime.replace(tzinfo=pytz.UTC).astimezone(gmt_tz)
    gmt_formatted = gmt_time.strftime("%A, %d %B, %Y %H:%M")
    
    return {
        'minutes_remaining': minutes_remaining,
        'utc_time': utc_time_str,
        'utc_time_simple': event_datetime.strftime("%H:%M UTC"),
        'local_time': local_time_formatted,
        'ist_time': ist_formatted,
        'est_time': est_formatted,
        'gmt_time': gmt_formatted
    }

def has_event_create_permission(interaction):
    """Check if user has permission to create events (Bot Owner, Organizer, or Helper)"""
    if interaction.user.id == BOT_OWNER_ID:
        return True
    user_role_ids = [role.id for role in interaction.user.roles]
    staff_roles = (
        ROLE_IDS.get("head_organizer", []) + 
        ROLE_IDS.get("deputy_server_head", []) + 
        ROLE_IDS.get("Tournament_organizer", []) + 
        ROLE_IDS.get("Tournament_supervision", []) +
        ROLE_IDS.get("head_helper", []) + 
        ROLE_IDS.get("helper_team", [])
    )
    return any(rid in user_role_ids for rid in staff_roles)

def has_event_result_permission(interaction):
    """Check if user has permission to post event results (Bot Owner, Organizer, or Judge)"""
    if interaction.user.id == BOT_OWNER_ID:
        return True
    user_role_ids = [role.id for role in interaction.user.roles]
    staff_roles = (
        ROLE_IDS.get("head_organizer", []) + 
        ROLE_IDS.get("deputy_server_head", []) + 
        ROLE_IDS.get("Tournament_organizer", []) + 
        ROLE_IDS.get("Tournament_supervision", []) +
        ROLE_IDS.get("judge", [])
    )
    return any(rid in user_role_ids for rid in staff_roles)

@bot.event
async def on_message(message):
    """Handle auto-response commands for ticket management"""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # Only process messages that start with ? and are in specific channels
    if not message.content.startswith('?'):
        return
    
    # Check if the command should be restricted to specific channels
    # For now, allow in all channels, but you can add restrictions here
    # Example: if message.channel.id not in [CHANNEL_IDS["take_schedule"], ...]:
    #     return
    
    # Extract command from message
    command = message.content.lower().strip()
    
    # Handle ticket status commands (?sh, ?dq, ?dd, ?ho) - modify channel name prefix
    if command in ['?sh', '?dq', '?dd', '?ho']:
        try:
            # Get the current channel
            channel = message.channel
            
            # Determine the new prefix based on command
            if command == '?sh':
                new_prefix = "🟢"
            elif command == '?dq':
                new_prefix = "🔴"
            elif command == '?dd':
                new_prefix = "✅"
            elif command == '?ho':
                new_prefix = "🟡"
            
            # Get current channel name
            current_name = channel.name
            
            # Remove existing status prefixes if they exist
            clean_name = current_name
            status_prefixes = ["🟢", "🔴", "✅", "🟡"]
            for prefix in status_prefixes:
                if clean_name.startswith(prefix):
                    clean_name = clean_name[len(prefix):].lstrip("-").lstrip()
                    break
            
            # Create new channel name with the status prefix
            new_name = f"{new_prefix}-{clean_name}"
            
            # Update channel name
            await channel.edit(name=new_name)
            
            # Delete the original command message after successful execution
            try:
                await message.delete()
            except discord.Forbidden:
                pass  # Ignore if we can't delete the message
            except Exception:
                pass  # Ignore any other deletion errors
            
        except discord.Forbidden:
            response = await message.channel.send("❌ I don't have permission to edit this channel's name.")
            try:
                await message.delete()
            except:
                pass
        except discord.HTTPException as e:
            response = await message.channel.send(f"❌ Error updating channel name: {e}")
            try:
                await message.delete()
            except:
                pass
        except Exception as e:
            response = await message.channel.send(f"❌ Unexpected error: {e}")
            try:
                await message.delete()
            except:
                pass
        
    elif command == '?b':
        # Challonge URL response
        response = await message.channel.send("https://challonge.com/The_Devil_Brigade")
        # Delete the original command message
        try:
            await message.delete()
        except discord.Forbidden:
            pass  # Ignore if we can't delete the message
        except Exception:
            pass  # Ignore any other deletion errors
    
    # Process other bot commands (important for command processing)
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    print(f"🆔 Bot ID: {bot.user.id}")
    print(f"📊 Connected to {len(bot.guilds)} guild(s)")
    
    # Load scheduled events from file
    load_scheduled_events()
    
    # Load tournament rules from file
    load_rules()
    
    # Reschedule cleanups for any events already marked finished_on if needed (optional)
    try:
        for ev_id, data in list(scheduled_events.items()):
            # If previously scheduled cleanup exists, skip (it won't persist); we don't know result time here
            # Optionally: clean up events older than 7 days to avoid clutter
            try:
                dt = data.get('datetime')
                if isinstance(dt, datetime.datetime):
                    age_days = (datetime.datetime.now() - dt).days
                    if age_days >= 7:
                        # Hard cleanup very old events
                        if ev_id in reminder_tasks:
                            try:
                                reminder_tasks[ev_id].cancel()
                                del reminder_tasks[ev_id]
                            except Exception:
                                pass
                        del scheduled_events[ev_id]
                    elif data.get('status') == 'scheduled' or not data.get('status'):
                        try:
                            ch_id = data.get('channel_id')
                            if ch_id:
                                ch = bot.get_channel(int(ch_id))
                                if ch:
                                    bot.loop.create_task(schedule_event_reminder_v2(
                                        ev_id, 
                                        data.get('team1_captain'), 
                                        data.get('team2_captain'), 
                                        data.get('judge'), 
                                        ch
                                    ))
                        except Exception as e:
                            print(f"Failed to reschedule reminder {ev_id}: {e}")
            except Exception:
                pass
        save_scheduled_events()
    except Exception as e:
        print(f"Startup cleanup sweep error: {e}")
    
    # Sync commands with timeout handling
    try:
        print("🔄 Syncing slash commands...")
        import asyncio
        synced = await asyncio.wait_for(tree.sync(), timeout=30.0)
        print(f"✅ Synced {len(synced)} command(s)")
    except asyncio.TimeoutError:
        print("⚠️ Command sync timed out, but bot will continue running")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")
        print("⚠️ Bot will continue running without command sync")
    
    print("🎯 Bot is ready to receive commands!")

@tree.command(name="help", description="Show available commands based on your permissions")
async def help_command(interaction: discord.Interaction):
    """Enhanced help command with role-based filtering and interactive navigation"""
    try:
        # Determine user's permission level
        permission_level = get_user_permission_level(interaction.user)
        
        # Build appropriate help embed
        embed = build_help_embed(permission_level, interaction.user.display_name)
        
        # Create interactive navigation view
        view = HelpNavigationView(permission_level, interaction.user.display_name)
        
        # Send response with interactive buttons (public message)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
        
    except Exception as e:
        print(f"Error in help command: {e}")
        # Fallback response
        embed = discord.Embed(
            title="🎯 Command Guide",
            description="Error loading command information. Please try again.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"{ORGANIZATION_NAME}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="staff-leaderboard", description="Display staff leaderboard showing most active judges and recorders")
async def staff_leaderboard(interaction: discord.Interaction):
    """Display staff leaderboard with match counts in table format"""
    try:
        # Get top staff
        top_staff = get_staff_leaderboard(limit=15)

        # Determine totals for footer
        total_judges = 0
        total_recorders = 0
        total_matches = 0

        # Calculate distinct counts if possible, or just sums
        # For simplicity, we count active roles
        try:
            total_judges = sum(1 for _, s in staff_stats.items() if s.get('judge_count', 0) > 0)
            total_recorders = sum(1 for _, s in staff_stats.items() if s.get('recorder_count', 0) > 0)
            total_matches = sum(s.get('judge_count', 0) for _, s in staff_stats.items())
        except:
            pass

        header = "📊 STAFF LEADERBOARD"
        separator = "=" * 70
        sub_sep = "-" * 70

        # Format table header
        # Rank | Judge Name (Matches) | Recorder Name (Matches) | Last Active
        # Note: The user requested "Judge Name   Recorder Name".
        # Since a user can be both, we will list users and show their counts for both roles.

        table_header = f"{'Rank':<6}{'Name':<20}{'Judge':<8}{'Recorder':<10}{'Total':<8}{'Last Active':<15}"

        message = f"```\n{header}\n{separator}\n{table_header}\n{sub_sep}\n"

        if not top_staff:
             message += "No staff statistics available yet.\n"
        else:
            medals = ["🥇", "🥈", "🥉"]
            for i, (uid, stats) in enumerate(top_staff):
                position = i + 1
                medal = medals[i] if i < 3 else f"{position}."

                name = stats.get("name", "Unknown")[:18]
                j_count = stats.get("judge_count", 0)
                r_count = stats.get("recorder_count", 0)
                t_count = j_count + r_count

                last_activity = stats.get("last_activity")
                activity_text = "Unknown"
                if last_activity:
                    try:
                        if isinstance(last_activity, str):
                            last_activity = datetime.datetime.fromisoformat(last_activity)
                        days_ago = (datetime.datetime.utcnow() - last_activity).days
                        if days_ago == 0: activity_text = "Today"
                        elif days_ago == 1: activity_text = "Yesterday"
                        else: activity_text = f"{days_ago}d ago"
                    except: pass

                # Rank | Name | Judge | Recorder | Total | Last Active
                message += f"{medal:<6}{name:<20}{j_count:<8}{r_count:<10}{t_count:<8}{activity_text:<15}\n"

        message += f"{sub_sep}\n"
        message += f"Total Judges involved: {total_judges} | Total Recorders involved: {total_recorders}\n"
        message += f"Total Interactions: {sum(s.get('judge_count', 0) + s.get('recorder_count', 0) for _, s in staff_stats.items())}\n"
        message += "```"

        # Check if user is head organizer for reset button
        user_role_ids = [role.id for role in interaction.user.roles]
        org_role_ids = (
            ROLE_IDS.get("head_organizer", []) + 
            ROLE_IDS.get("deputy_server_head", []) + 
            ROLE_IDS.get("Tournament_organizer", []) + 
            ROLE_IDS.get("Tournament_supervision", [])
        )
        has_org_role = any(rid in user_role_ids for rid in org_role_ids)
        
        if has_org_role:
            view = JudgeLeaderboardView(show_reset=True)
            await interaction.response.send_message(message, view=view)
        else:
            await interaction.response.send_message(message)

    except Exception as e:
        print(f"Error in staff leaderboard command: {e}")
        message = "```\n❌ Error loading staff statistics. Please try again.\n```"
        await interaction.response.send_message(message)

@tree.command(name="staff-update", description="Update a staff member's match count in the leaderboard")
@app_commands.describe(
    staff_member="The staff member to update",
    role="Role to update (judge or recorder)",
    action="Add, Subtract, or Set the count",
    amount="The number of matches to add, subtract, or set to"
)
@app_commands.choices(
    role=[
        app_commands.Choice(name="Judge", value="judge"),
        app_commands.Choice(name="Recorder", value="recorder")
    ],
    action=[
        app_commands.Choice(name="Add (+)", value="add"),
        app_commands.Choice(name="Subtract (-)", value="subtract"),
        app_commands.Choice(name="Set (=)", value="set")
    ]
)
async def staff_update(
    interaction: discord.Interaction, 
    staff_member: discord.Member, 
    role: app_commands.Choice[str], 
    action: app_commands.Choice[str], 
    amount: int
):
    """Update staff statistics for a specific user"""
    # Check if user has head organizer role
    org_role_ids = (
        ROLE_IDS.get("head_organizer", []) + 
        ROLE_IDS.get("deputy_server_head", []) + 
        ROLE_IDS.get("Tournament_organizer", []) + 
        ROLE_IDS.get("Tournament_supervision", [])
    )
    has_permission = any(r.id in org_role_ids for r in interaction.user.roles)
            
    if not has_permission:
        await interaction.response.send_message("❌ You need **Head Organizer** role to update staff statistics.", ephemeral=True)
        return
        
    if amount < 0 and action.value != "subtract":
        await interaction.response.send_message("❌ Amount cannot be negative.", ephemeral=True)
        return
        
    global staff_stats
    uid = str(staff_member.id)
    
    # Initialize if not exists
    if uid not in staff_stats:
        staff_stats[uid] = {
            "name": staff_member.display_name,
            "judge_count": 0,
            "recorder_count": 0,
            "last_activity": None
        }
    else:
        # Update name in case it changed
        staff_stats[uid]["name"] = staff_member.display_name
        
    role_key = f"{role.value}_count"
    current_count = staff_stats[uid].get(role_key, 0)
    
    if action.value == "add":
        new_count = current_count + amount
    elif action.value == "subtract":
        new_count = max(0, current_count - amount)
    else: # set
        new_count = max(0, amount)
        
    staff_stats[uid][role_key] = new_count
    staff_stats[uid]["last_activity"] = datetime.datetime.utcnow()
    
    save_staff_stats()
    
    await interaction.response.send_message(f"✅ Successfully updated **{staff_member.display_name}**'s {role.name} count from {current_count} to **{new_count}**.", ephemeral=False)

@tree.command(name="info", description="Display bot information and statistics")
async def info_command(interaction: discord.Interaction):
    """Display bot information and server statistics"""
    try:
        # Calculate statistics
        total_members = sum(g.member_count for g in bot.guilds)
        total_channels = sum(len(g.channels) for g in bot.guilds)
        
        # Create embed
        embed = discord.Embed(
            title=f"ℹ️ {ORGANIZATION_NAME} Bot Information",
            description="Tournament management bot for Modern Warships",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Bot Information
        embed.add_field(
            name="🤖 Bot Details",
            value=f"**Name:** {bot.user.name}\n"
                  f"**ID:** {bot.user.id}\n"
                  f"**Latency:** {round(bot.latency * 1000)}ms",
            inline=True
        )
        
        # Bot Statistics
        embed.add_field(
            name="📊 Bot Statistics",
            value=f"**Servers:** {len(bot.guilds)}\n"
                  f"**Users:** {total_members:,}\n"
                  f"**Channels:** {total_channels:,}",
            inline=True
        )
        
        # Server Information (if in a guild)
        if interaction.guild:
            embed.add_field(
                name="🏠 Current Server",
                value=f"**Name:** {interaction.guild.name}\n"
                      f"**Members:** {interaction.guild.member_count:,}\n"
                      f"**Created:** {interaction.guild.created_at.strftime('%d/%m/%Y')}",
                inline=True
            )
        
        # Commands Information
        total_commands = len(bot.tree.get_commands())
        embed.add_field(
            name="⚙️ Commands",
            value=f"**Total Commands:** {total_commands}\n"
                  f"**Categories:** Tournament, Event Management, Utility, System",
            inline=False
        )
        
        # Organization Info
        embed.add_field(
            name="🏆 Organization",
            value=f"{ORGANIZATION_NAME}\n"
                  f"Modern Warships Tournament System",
            inline=False
        )
        
        # Set thumbnail to bot avatar
        if bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in info command: {e}")

@tree.command(name="rules", description="Manage or view tournament rules")
async def rules_command(interaction: discord.Interaction):
    """Main rules command with role-based functionality"""
    try:
        # Check if user has organizer permissions
        if has_organizer_permission(interaction):
            # Organizer gets management interface
            embed = discord.Embed(
                title="📋 Tournament Rules Management",
                description="Choose an action to manage tournament rules:",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            current_rules = get_current_rules()
            if current_rules:
                embed.add_field(
                    name="Current Status", 
                    value="✅ Rules are set", 
                    inline=True
                )
                # Show preview of current rules
                preview = current_rules[:200] + "..." if len(current_rules) > 200 else current_rules
                embed.add_field(
                    name="Preview", 
                    value=f"```\n{preview}\n```", 
                    inline=False
                )
            else:
                embed.add_field(
                    name="Current Status", 
                    value="❌ No rules set", 
                    inline=True
                )
            
            embed.set_footer(text="Winterfell Arena Esports • Organizer Panel")
            
            # Send with management buttons
            view = RulesManagementView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            # Non-organizer gets direct rule display
            await display_rules(interaction)
            
    except Exception as e:
        print(f"Error in rules command: {e}")
        await interaction.response.send_message("❌ An error occurred while processing the rules command.", ephemeral=True)
    
@tree.command(name="team_balance", description="Balance two teams based on player levels")
@app_commands.describe(levels="Comma-separated player levels (e.g. 48,50,51,35,51,50,50,37,51,52)")
async def team_balance(interaction: discord.Interaction, levels: str):
    try:
        level_list = [int(x.strip()) for x in levels.split(",") if x.strip()]
        n = len(level_list)
        if n % 2 != 0:
            await interaction.response.send_message("❌ Number of players must be even (e.g., 8 or 10).", ephemeral=True)
            return

        team_size = n // 2
        min_diff = float('inf')
        best_team_a = []
        for combo in combinations(level_list, team_size):
            team_a = list(combo)
            team_b = list(level_list)
            for lvl in team_a:
                team_b.remove(lvl)
            diff = abs(sum(team_a) - sum(team_b))
            if diff < min_diff:
                min_diff = diff
                best_team_a = team_a
        team_b = list(level_list)
        for lvl in best_team_a:
            team_b.remove(lvl)
        sum_a = sum(best_team_a)
        sum_b = sum(team_b)
        diff = abs(sum_a - sum_b)
        await interaction.response.send_message(
            f"**Team A:** {best_team_a} | Total Level: {sum_a}\n"
            f"**Team B:** {team_b} | Total Level: {sum_b}\n"
            f"**Level Difference:** {diff}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@events_group.command(name="create", description="Create an event.")
@app_commands.describe(
    team1="Name of Team 1",
    team2="Name of Team 2",
    captain1="Mention Captain of Team 1",
    captain2="Mention Captain of Team 2",
    hour="Hour of the event (0-23)",
    minute="Minute of the event (0-59)",
    date="Date of the event",
    month="Month of the event",
    round="Round label",
    tournament="Tournament name (e.g. King of the Seas, Summer Cup, etc.)",
    mode="Game Mode (MW or MWT)",
    group="Group assignment (A-J) or Winner/Loser"
)
@app_commands.choices(
    round=[
        app_commands.Choice(name="R1", value="R1"),
        app_commands.Choice(name="R2", value="R2"),
        app_commands.Choice(name="R3", value="R3"),
        app_commands.Choice(name="R4", value="R4"),
        app_commands.Choice(name="R5", value="R5"),
        app_commands.Choice(name="R6", value="R6"),
        app_commands.Choice(name="R7", value="R7"),
        app_commands.Choice(name="R8", value="R8"),
        app_commands.Choice(name="R9", value="R9"),
        app_commands.Choice(name="R10", value="R10"),
        app_commands.Choice(name="Qualifier", value="Qualifier"),
        app_commands.Choice(name="Semi Final", value="Semi Final"),
        app_commands.Choice(name="Final", value="Final"),
    ],
    group=[
        app_commands.Choice(name="Group A", value="Group A"),
        app_commands.Choice(name="Group B", value="Group B"),
        app_commands.Choice(name="Group C", value="Group C"),
        app_commands.Choice(name="Group D", value="Group D"),
        app_commands.Choice(name="Group E", value="Group E"),
        app_commands.Choice(name="Group F", value="Group F"),
        app_commands.Choice(name="Group G", value="Group G"),
        app_commands.Choice(name="Group H", value="Group H"),
        app_commands.Choice(name="Group I", value="Group I"),
        app_commands.Choice(name="Group J", value="Group J"),
        app_commands.Choice(name="Winner", value="Winner"),
        app_commands.Choice(name="Loser", value="Loser"),
    ],
    mode=[
        app_commands.Choice(name="Modern Warships (MW)", value="MW"),
        app_commands.Choice(name="Modern Warships Tanks (MWT)", value="MWT"),
    ]
)
async def create(
    interaction: discord.Interaction,
    team1: str,
    team2: str,
    hour: int,
    minute: int,
    date: int,
    month: int,
    round: app_commands.Choice[str],
    tournament: str,
    mode: app_commands.Choice[str],
    captain1: discord.Member = None,
    captain2: discord.Member = None,
    group: app_commands.Choice[str] = None
):
    """Creates an event with the specified parameters"""
    
    # Defer the response to give us more time for image processing
    await interaction.response.defer(ephemeral=True)
    
    # Check permissions
    if not has_event_create_permission(interaction):
        await interaction.followup.send("❌ You need **Head Organizer**, **Head Helper** or **Helper Team** role to create events.", ephemeral=True)
        return
    
    # Helper to resolve names from mentions in strings
    def resolve_name(val):
        if not val: return val
        match = re.search(r'<@!?(\d+)>', str(val))
        if match:
            member_id = int(match.group(1))
            member = interaction.guild.get_member(member_id)
            if member: return member.display_name
        return val

    # Determine final names and mentions
    t1_display = resolve_name(team1)
    t2_display = resolve_name(team2)
    
    t1_full = team1
    if captain1:
        if team1.lower() == captain1.display_name.lower() or team1.strip() == f"<@{captain1.id}>" or team1.strip() == f"<@!{captain1.id}>":
             t1_full = captain1.mention
        else:
             t1_full = f"{team1} ({captain1.mention})"
    
    t2_full = team2
    if captain2:
        if team2.lower() == captain2.display_name.lower() or team2.strip() == f"<@{captain2.id}>" or team2.strip() == f"<@!{captain2.id}>":
             t2_full = captain2.mention
        else:
             t2_full = f"{team2} ({captain2.mention})"
    
    # Validate input parameters
    if not (0 <= hour <= 23):
        await interaction.followup.send("❌ Hour must be between 0 and 23", ephemeral=True)
        return
    
    if not (1 <= date <= 31):
        await interaction.followup.send("❌ Date must be between 1 and 31", ephemeral=True)
        return

    if not (1 <= month <= 12):
        await interaction.followup.send("❌ Month must be between 1 and 12", ephemeral=True)
        return
            
    if not (0 <= minute <= 59):
        await interaction.followup.send("❌ Minute must be between 0 and 59", ephemeral=True)
        return

    # Create datetime object for the event
    try:
        current_year = datetime.datetime.now().year
        event_datetime = datetime.datetime(current_year, month, date, hour, minute)
        
        # Calculate time difference and UTC formatting
        time_info = calculate_time_difference(event_datetime)
        
        # Team formatting matching request: team strings + captain mentions
        # Generate event poster
        poster_image = None
        template = get_random_template(mode.value)
        if template:
            poster_image = create_event_poster(
                template, 
                round.value, 
                t1_display, 
                t2_display, 
                time_info['utc_time_simple'],
                f"{date:02d}/{month:02d}"
            )
        
        # Create event data
        event_id = f"EVT-{int(datetime.datetime.now().timestamp())}"
        round_label = round.value
        group_label = group.value if group else None
        
        event_data = {
            'id': event_id,
            'team1_captain': t1_full,
            'team2_captain': t2_full,
            'team1_name': team1,
            'team2_name': team2,
            'datetime': event_datetime,
            'time_str': time_info['utc_time'],
            'date_str': f"{date:02d}/{month:02d}",
            'round': round_label,
            'tournament': tournament,
            'mode': mode.value,
            'group': group_label,
            'channel_id': interaction.channel.id,
            'created_at': datetime.datetime.now().isoformat(),
            'created_by': interaction.user.id,
            'status': 'scheduled',
            'poster_path': poster_image,
            'captain1_id': captain1.id if captain1 else None,
            'captain2_id': captain2.id if captain2 else None
        }
        
        sheet_manager.log_event_creation(event_data)
        
        print(f"📝 Event {event_id} created internally for {team1} vs {team2}")
        
        # Store event data for reminders
        scheduled_events[event_id] = event_data
        
        # Save events to file
        save_scheduled_events()
        print(f"💾 Event {event_id} saved to file")
        
        # Create event embed with new format
        embed = discord.Embed(
            title="Schedule",
            description=f"🗓️ {team1} VS {team2}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Tournament and Time Information
        timestamp = int(event_datetime.timestamp())
        event_details = f"**Tournament:** {tournament}\n"
        event_details += f"**Mode:** {mode.value}\n"
        event_details += f"**UTC Time:** {time_info['utc_time']}\n"
        event_details += f"**Local Time:** <t:{timestamp}:F> (<t:{timestamp}:R>)\n"
        event_details += f"**Round:** {round_label}\n"
        
        if group_label:
            event_details += f"**Group:** {group_label}\n"
        
        event_details += f"**Channel:** {interaction.channel.mention}"
        
        embed.add_field(
            name="📋 Event Details", 
            value=event_details,
            inline=False
        )
        
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        
        # Captains Section
        captains_text = f"**Captains/Teams**\n"
        captains_text += f"▪ Team 1: {t1_full}\n"
        captains_text += f"▪ Team 2: {t2_full}"
        embed.add_field(name="👑 Match-up", value=captains_text, inline=False)
        
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        embed.add_field(name="👤 Created By", value=interaction.user.mention, inline=False)
        
        if poster_image:
            try:
                with open(poster_image, 'rb') as f:
                    file = discord.File(f, filename="event_poster.png")
                    embed.set_image(url="attachment://event_poster.png")
            except Exception as e:
                print(f"Error loading poster image: {e}")
        
        embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
        
        # Create Take Schedule button
        take_schedule_view = TakeScheduleButton(event_id, t1_full, t2_full, interaction.channel)
        
        await interaction.followup.send("✅ Event created and posted to both channels!", ephemeral=True)
        
        # Post in Take-Schedule channel
        schedule_channel = interaction.guild.get_channel(CHANNEL_IDS["take_schedule"])
        if schedule_channel:
            judge_ping = " ".join([f"<@&{rid}>" for rid in ROLE_IDS['judge']])
            if poster_image:
                with open(poster_image, 'rb') as f:
                    file = discord.File(f, filename="event_poster.png")
                    schedule_message = await schedule_channel.send(content=judge_ping, embed=embed, file=file, view=take_schedule_view)
            else:
                schedule_message = await schedule_channel.send(content=judge_ping, embed=embed, view=take_schedule_view)
            
            event_data['schedule_message_id'] = schedule_message.id
            event_data['schedule_channel_id'] = schedule_channel.id
            save_scheduled_events()
            
        # Post in the current channel
        if poster_image:
            with open(poster_image, 'rb') as f:
                file = discord.File(f, filename="event_poster.png")
                await interaction.channel.send(embed=embed, file=file)
        else:
            await interaction.channel.send(embed=embed)
 
        await schedule_ten_minute_reminder(event_id, t1_full, t2_full, None, interaction.channel, event_datetime)

    except Exception as e:
        print(f"Error in event_create: {e}")
        await interaction.followup.send(f"⚠️ Error creating event: {e}", ephemeral=True)

@tree.command(name="event-result", description="Add event results.")
@app_commands.describe(
    team_1="Name of Team 1",
    team_1_captain="Captain of Team 1",
    team_1_score="Score for Team 1",
    team_2="Name of Team 2",
    team_2_captain="Captain of Team 2",
    team_2_score="Score for Team 2",
    number_of_matches="Total number of matches played",
    remarks="Remarks about the match",
    ss_1="Screenshot 1",
    ss_2="Screenshot 2",
    ss_3="Screenshot 3",
    ss_4="Screenshot 4",
    ss_5="Screenshot 5",
    ss_6="Screenshot 6",
    ss_7="Screenshot 7",
    ss_8="Screenshot 8",
    ss_9="Screenshot 9",
    ss_10="Screenshot 10",
    ss_11="Screenshot 11"
)
async def event_result(
    interaction: discord.Interaction,
    team_1: str,
    team_1_captain: discord.Member,
    team_1_score: int,
    team_2: str,
    team_2_captain: discord.Member,
    team_2_score: int,
    number_of_matches: int = 1,
    remarks: str = "ggwp",
    ss_1: discord.Attachment = None,
    ss_2: discord.Attachment = None,
    ss_3: discord.Attachment = None,
    ss_4: discord.Attachment = None,
    ss_5: discord.Attachment = None,
    ss_6: discord.Attachment = None,
    ss_7: discord.Attachment = None,
    ss_8: discord.Attachment = None,
    ss_9: discord.Attachment = None,
    ss_10: discord.Attachment = None,
    ss_11: discord.Attachment = None
):
    """Adds results for an event"""
    
    # Defer the response immediately to avoid timeout issues
    await interaction.response.defer(ephemeral=True)
    
    # Check permissions
    if not has_event_result_permission(interaction):
        await interaction.followup.send("❌ You need **Head Organizer** or **Judge** role to post event results.", ephemeral=True)
        return

    # Find event logic
    current_channel_id = interaction.channel.id
    event_id_found = None
    event_data = {}
    
    # Fallback to current channel
    for ev_id, data in scheduled_events.items():
        if data.get('channel_id') == current_channel_id:
            event_id_found = ev_id
            event_data = data
            break
            
    # Extract info from event data where possible
    tournament = event_data.get('tournament', 'N/A')
    round_label = event_data.get('round', 'N/A')
    group_label = event_data.get('group')

    # Format full names for display
    t1_full = f"{team_1} ({team_1_captain.mention})"
    t2_full = f"{team_2} ({team_2_captain.mention})"

    # Determine winner and loser
    if team_1_score > team_2_score:
        winner, winner_score = t1_full, team_1_score
        winner_name = team_1
        loser, loser_score = t2_full, team_2_score
        loser_name = team_2
    else:
        winner, winner_score = t2_full, team_2_score
        winner_name = team_2
        loser, loser_score = t1_full, team_1_score
        loser_name = team_1
    
    # Validate scores
    if team_1_score < 0 or team_2_score < 0:
        await interaction.followup.send("❌ Scores cannot be negative", ephemeral=True)
        return
            
    # Create results embed
    # Create results embed
    embed_description = f"🗓️ {t1_full} Vs {t2_full}\n"
    embed_description += f"**Tournament:** {tournament}\n"
    embed_description += f"**Round:** {round_label}"
    
    if group_label:
        embed_description += f"\n**Group:** {group_label}"
    
    embed = discord.Embed(
        title="Results",
        description=embed_description,
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="👑 Match-up", value=f"▪ Team 1: {t1_full}\n▪ Team 2: {t2_full}", inline=False)
    embed.add_field(name="\u200b", value="\u200b", inline=False) 
    
    results_text = f"🏆 {winner} ({winner_score}) Vs ({loser_score}) {loser} 💀"
    embed.add_field(name="Results", value=results_text, inline=False)
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    
    staff_text = f"👨‍⚖️ **Staffs**\n▪ Judge: {interaction.user.mention}\n"
    current_recorder = event_data.get('recorder')
    if current_recorder:
        if isinstance(current_recorder, int):
            staff_text += f"▪ Recorder: <@{current_recorder}>"
        elif hasattr(current_recorder, 'mention'):
            staff_text += f"▪ Recorder: {current_recorder.mention}"
        else:
            staff_text += f"▪ Recorder: {current_recorder}"
    else:
        staff_text += "▪ Recorder: None"
        
    embed.add_field(name="Staffs", value=staff_text, inline=False)
    embed.add_field(name="📝 Remarks", value=remarks, inline=False)

    # Log Result to Sheet
    if event_id_found:
        score_combined = f"{team_1} ({team_1_score}) - {team_2} ({team_2_score})"
        sheet_manager.log_event_result(event_id_found, winner_name, score_combined, remarks)

    # Handle screenshots safely by caching the bytes
    screenshots = [ss_1, ss_2, ss_3, ss_4, ss_5, ss_6, ss_7, ss_8, ss_9, ss_10, ss_11]
    screenshot_data = []
    screenshot_names = []
    
    for i, screenshot in enumerate(screenshots, 1):
        if screenshot:
            try:
                # Capture the bytes once so we can safely reuse them globally without seek()
                file_data = await screenshot.read()
                screenshot_data.append((file_data, f"SS-{i}_{screenshot.filename}"))
                screenshot_names.append(f"SS-{i}")
            except Exception as e:
                print(f"Error processing screenshot {i}: {e}")
    
    if screenshot_names:
        embed.add_field(name="📷 Proof", value=f"Proof of Result ({len(screenshot_names)} images): {' • '.join(screenshot_names)}", inline=False)
    
    embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
    
    # Post to Results Channel
    try:
        results_channel = interaction.guild.get_channel(CHANNEL_IDS["results"]) or bot.get_channel(CHANNEL_IDS["results"])
        if results_channel:
            # We recreate files for each send since fp is consumed upon sending
            fs = []
            for data, name in screenshot_data:
                fs.append(discord.File(fp=io.BytesIO(data), filename=name))
            await results_channel.send(embed=embed, files=fs)
    except Exception as e:
        print(f"Error posting to results channel: {e}")

    # Post to Current Channel
    try:
        fs = []
        for data, name in screenshot_data:
            fs.append(discord.File(fp=io.BytesIO(data), filename=name))
        await interaction.channel.send(embed=embed, files=fs)
    except Exception as e:
        print(f"Error posting to current channel: {e}")

    # Staff Attendance Channel
    try:
        staff_attendance_channel = interaction.guild.get_channel(CHANNEL_IDS["staff_attendance"]) or bot.get_channel(CHANNEL_IDS["staff_attendance"])
        if staff_attendance_channel:
            att_text = f"🏅 {team_1} Vs {team_2}\n**Round:** {round_label}\n"
            if group_label: att_text += f"**Group:** {group_label}\n"
            att_text += f"\n🏆 {winner} ({winner_score}) Vs ({loser_score}) {loser} 💀\n\n"
            att_text += f"**Staffs**\n• Judge: {interaction.user.mention}\n"
            rec_id = event_data.get('recorder')
            att_text += f"• Recorder: <@{rec_id}>" if rec_id else "• Recorder: None"
            await staff_attendance_channel.send(att_text)
            
            # Log to sheet
            dt_now = datetime.datetime.now()
            date_s = dt_now.strftime("%Y-%m-%d")
            time_s = dt_now.strftime("%H:%M:%S")
            
            sheet_manager.log_attendance(
                date_str=date_s, 
                time_str=time_s, 
                event_name=f"{team_1} vs {team_2} ({round_label})", 
                role="Judge", 
                staff_name=interaction.user.name, 
                marked_by=interaction.user.name
            )
            
            if rec_id:
                rec_name = "Unknown"
                if isinstance(rec_id, int):
                    m = interaction.guild.get_member(rec_id)
                    if m: rec_name = m.name
                elif hasattr(rec_id, 'name'):
                    rec_name = rec_id.name
                
                sheet_manager.log_attendance(
                    date_str=date_s, 
                    time_str=time_s, 
                    event_name=f"{team_1} vs {team_2} ({round_label})", 
                    role="Recorder", 
                    staff_name=rec_name, 
                    marked_by=interaction.user.name
                )
    except Exception as e:
        print(f"Error with staff attendance: {e}")

    # Update event status
    if event_data:
        event_data['result_added'] = True
        event_data['team1_score'] = team_1_score
        event_data['team2_score'] = team_2_score
        event_data['number_of_matches'] = number_of_matches
        event_data['winner'] = winner
        event_data['status'] = 'completed'
        save_scheduled_events()
    
    # Auto cleanup
    if event_id_found:
        await schedule_event_cleanup(event_id_found, delay_hours=2)
    
    # Update stats
    update_staff_stats(interaction.user.id, interaction.user.display_name, "Judge")
    rec_val = event_data.get('recorder')
    if rec_val:
        if isinstance(rec_val, int):
            m = interaction.guild.get_member(rec_val)
            if m: update_staff_stats(m.id, m.display_name, "Recorder")
        elif hasattr(rec_val, 'id'):
            update_staff_stats(rec_val.id, rec_val.display_name, "Recorder")

    await interaction.followup.send("✅ Results processed and cleanup scheduled (2h).", ephemeral=True)
        
@tree.command(name="time", description="Get a random match time from fixed 30-min slots (12:00-17:00 UTC)")
async def time(interaction: discord.Interaction):
    """Pick a random time from 30-minute slots between 12:00 and 17:00 UTC and show all slots."""
    
    import random
    
    # Build fixed 30-minute slots from 12:00 to 17:00 (inclusive), excluding 17:30
    slots = [
        f"{hour:02d}:{minute:02d} UTC"
        for hour in range(12, 18)
        for minute in (0, 30)
        if not (hour == 17 and minute == 30)
    ]
    
    chosen_time = random.choice(slots)
    
    embed = discord.Embed(
        title="⏰ Match Time (30‑min slots)",
        description=f"**Your random match time:** {chosen_time}",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
                    )
                                       
    embed.add_field(
        name="🕒 Range",
        value="From 12:00 to 17:00 UTC (every 30 minutes)",
        inline=False
    )
                    
    embed.set_footer(text="Match Time Generator • Winterfell Arena Esports")
    
    await interaction.response.send_message(embed=embed)

## Removed test-poster command per request


@tree.command(name="unassigned_events", description="List events without a judge assigned (Judges/Organizers)")
async def unassigned_events(interaction: discord.Interaction):
    """Show all scheduled events that do not currently have a judge assigned."""
    try:
        # Allow Head Organizer, Head Helper, Helper Team, and Judges to view
        user_role_ids = [role.id for role in interaction.user.roles]
        org_role_ids = (
            ROLE_IDS.get("head_organizer", []) + 
            ROLE_IDS.get("deputy_server_head", []) + 
            ROLE_IDS.get("Tournament_organizer", []) + 
            ROLE_IDS.get("Tournament_supervision", [])
        )
        is_org = any(rid in user_role_ids for rid in org_role_ids)
        is_h_helper = any(rid in user_role_ids for rid in ROLE_IDS["head_helper"])
        is_helper_team = any(rid in user_role_ids for rid in ROLE_IDS["helper_team"])
        is_judge = any(rid in user_role_ids for rid in ROLE_IDS["judge"])

        if not (is_org or is_h_helper or is_helper_team or is_judge):
            await interaction.response.send_message("❌ You need Organizer or Judge role to view unassigned events.", ephemeral=True)
            return

        # Build list of unassigned events
        unassigned = []
        for event_id, data in scheduled_events.items():
            if not data.get('judge'):
                unassigned.append((event_id, data))

        # If none, inform
        if not unassigned:
            await interaction.response.send_message("✅ All events currently have a judge assigned.", ephemeral=True)
            return

        # Sort by datetime if present
        try:
            unassigned.sort(key=lambda x: x[1].get('datetime') or datetime.datetime.max)
        except Exception:
            pass

        # Create embed summary
        embed = discord.Embed(
            title="📝 Unassigned Events",
            description="Events without a judge. Use the message link to take the schedule.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )

        # Add up to 25 entries (Discord practical limit for a single embed field block)
        lines = []
        for idx, (ev_id, data) in enumerate(unassigned[:25], start=1):
            round_label = data.get('round', 'Round')
            date_str = data.get('date_str', 'N/A')
            time_str = data.get('time_str', 'N/A')
            ch_id = data.get('schedule_channel_id') or data.get('channel_id')
            msg_id = data.get('schedule_message_id')
            team1 = data.get('team1_captain')
            team2 = data.get('team2_captain')
            team1_name = getattr(team1, 'display_name', 'Unknown') if team1 else 'Unknown'
            team2_name = getattr(team2, 'display_name', 'Unknown') if team2 else 'Unknown'

            link = None
            try:
                if interaction.guild and ch_id and msg_id:
                    link = f"https://discord.com/channels/{interaction.guild.id}/{ch_id}/{msg_id}"
            except Exception:
                link = None

            if link:
                line = f"{idx}. {team1_name} vs {team2_name} • {round_label} • {time_str} • {date_str}\n↪ {link}"
            else:
                line = f"{idx}. {team1_name} vs {team2_name} • {round_label} • {time_str} • {date_str}"
            lines.append(line)

        embed.add_field(
            name=f"Available ({len(unassigned)})",
            value="\n\n".join(lines),
            inline=False
        )

        embed.set_footer(text="Use the link to open the original schedule and press Take Schedule.")

        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"Error in unassigned_events: {e}")
        try:
            await interaction.response.send_message("❌ An error occurred while fetching unassigned events.", ephemeral=True)
        except Exception:
            pass

@events_group.command(name="delete", description="Delete a scheduled event.")
async def delete(interaction: discord.Interaction):
    # Check permissions - only Head Organizer, Head Helper or Helper Team (and Bot Owner)
    if not has_event_create_permission(interaction):
        await interaction.response.send_message("❌ You need **Head Organizer**, **Head Helper** or **Helper Team** role to delete events.", ephemeral=True)
        return
    
    try:
        # Check if there are any scheduled events
        if not scheduled_events:
            await interaction.response.send_message(f"❌ No scheduled events found to delete.\n\n**Debug Info:**\n• Scheduled events count: {len(scheduled_events)}\n• Events in memory: {list(scheduled_events.keys()) if scheduled_events else 'None'}", ephemeral=True)
            return
        
        # Create dropdown with event names
        class EventDeleteView(View):
            def __init__(self):
                super().__init__(timeout=60)
                
            @discord.ui.select(
                placeholder="Select an event to delete...",
                options=[
                    discord.SelectOption(
                        label=f"{event_data.get('team1_name', 'Unknown')} VS {event_data.get('team2_name', 'Unknown')}",
                        description=f"{event_data.get('round', 'Unknown Round')} - {event_data.get('date_str', 'No date')} at {event_data.get('time_str', 'No time')}",
                        value=event_id
                    )
                    for event_id, event_data in list(scheduled_events.items())[:25]  # Discord limit of 25 options
                ]
            )
            async def select_event(self, select_interaction: discord.Interaction, select: discord.ui.Select):
                selected_event_id = select.values[0]
                
                # Get event details for confirmation
                event_data = scheduled_events[selected_event_id]
                
                # Cancel any scheduled reminders
                if selected_event_id in reminder_tasks:
                    reminder_tasks[selected_event_id].cancel()
                    del reminder_tasks[selected_event_id]
                
                # Remove judge assignment if exists
                
                # Delete the original schedule message if it exists
                deleted_message = False
                if 'schedule_message_id' in event_data and 'schedule_channel_id' in event_data:
                    try:
                        schedule_channel = select_interaction.guild.get_channel(event_data['schedule_channel_id'])
                        if schedule_channel:
                            schedule_message = await schedule_channel.fetch_message(event_data['schedule_message_id'])
                            await schedule_message.delete()
                            deleted_message = True
                    except discord.NotFound:
                        pass  # Message already deleted
                    except Exception as e:
                        print(f"Error deleting schedule message: {e}")
                
                # Clean up any temporary poster files
                if 'poster_path' in event_data:
                    try:
                        import os
                        if os.path.exists(event_data['poster_path']):
                            os.remove(event_data['poster_path'])
                    except Exception as e:
                        print(f"Error deleting poster file: {e}")
                
                # Remove from scheduled events
                del scheduled_events[selected_event_id]
                
                # Save events to file
                save_scheduled_events()
                
                # Create confirmation embed
                embed = discord.Embed(
                    title="🗑️ Event Deleted",
                    description=f"Event has been successfully deleted.",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                
                embed.add_field(
                    name="📋 Deleted Event Details",
                    value=f"**Title:** {event_data.get('title', 'N/A')}\n**Round:** {event_data.get('round', 'N/A')}\n**Time:** {event_data.get('time_str', 'N/A')}\n**Date:** {event_data.get('date_str', 'N/A')}",
                    inline=False
                )
                
                # Build actions completed list
                actions_completed = [
                    "• Event removed from schedule",
                    "• Reminder cancelled"
                ]
                
                if deleted_message:
                    actions_completed.append("• Original schedule message deleted")
                
                if 'poster_path' in event_data:
                    actions_completed.append("• Temporary poster file cleaned up")
                
                embed.add_field(
                    name="✅ Actions Completed",
                    value="\n".join(actions_completed),
                    inline=False
                )
                
                embed.set_footer(text="Event Management • Winterfell Arena Esports")
                
                await select_interaction.response.edit_message(embed=embed, view=None)
        
        # Create initial embed
        embed = discord.Embed(
            title="🗑️ Delete Event",
            description="Select an event from the dropdown below to delete it.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Available Events",
            value=f"Found {len(scheduled_events)} scheduled event(s)",
            inline=False
        )
        
        embed.set_footer(text="Event Management • Winterfell Arena Esports")
        
        view = EventDeleteView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


@events_group.command(name="edit", description="Edit an event. Select an event by title or edit the one in this channel.")
@app_commands.describe(
    title="Search for event to edit or enter a new tournament name",
    captain1="New Team 1 Captain",
    captain2="New Team 2 Captain",
    team1="Update Team 1 Name",
    team2="Update Team 2 Name",
    hour="Update Hour (0-23)",
    minute="Update Minute (0-59)",
    date="Update Date",
    month="Update Month",
    round="Update Round",
    group="Update Group"
)
@app_commands.choices(
    round=[
        app_commands.Choice(name="R1", value="R1"),
        app_commands.Choice(name="R2", value="R2"),
        app_commands.Choice(name="R3", value="R3"),
        app_commands.Choice(name="R4", value="R4"),
        app_commands.Choice(name="R5", value="R5"),
        app_commands.Choice(name="R6", value="R6"),
        app_commands.Choice(name="R7", value="R7"),
        app_commands.Choice(name="R8", value="R8"),
        app_commands.Choice(name="R9", value="R9"),
        app_commands.Choice(name="R10", value="R10"),
        app_commands.Choice(name="Qualifier", value="Qualifier"),
        app_commands.Choice(name="Semi Final", value="Semi Final"),
        app_commands.Choice(name="Final", value="Final"),
    ],
    group=[
        app_commands.Choice(name="Group A", value="Group A"),
        app_commands.Choice(name="Group B", value="Group B"),
        app_commands.Choice(name="Group C", value="Group C"),
        app_commands.Choice(name="Group D", value="Group D"),
        app_commands.Choice(name="Group E", value="Group E"),
        app_commands.Choice(name="Group F", value="Group F"),
        app_commands.Choice(name="Group G", value="Group G"),
        app_commands.Choice(name="Group H", value="Group H"),
        app_commands.Choice(name="Group I", value="Group I"),
        app_commands.Choice(name="Group J", value="Group J"),
        app_commands.Choice(name="Winner", value="Winner"),
        app_commands.Choice(name="Loser", value="Loser"),
    ]
)
async def edit(
    interaction: discord.Interaction,
    title: str = None,
    captain1: discord.Member = None,
    captain2: discord.Member = None,
    team1: str = None,
    team2: str = None,
    hour: int = None,
    minute: int = None,
    date: int = None,
    month: int = None,
    round: app_commands.Choice[str] = None,
    group: app_commands.Choice[str] = None
):
    """Edit the event in this ticket channel"""
    
    # Defer the response to give us more time for processing
    await interaction.response.defer(ephemeral=True)
    
    # Check permissions - Bot Owner, Head Organizer, Head Helper or Helper Team can edit events
    if interaction.user.id != BOT_OWNER_ID:
        if not has_event_create_permission(interaction):
            await interaction.followup.send("❌ You need **Bot Owner**, **Head Organizer**, **Head Helper** or **Helper Team** role to edit events.", ephemeral=True)
            return
    
    # Find event - either via specific title selection (autocomplete value is ID) 
    # or find in current channel as fallback
    event_to_edit = None
    event_id = None
    
    # Priority 1: Check if title is actually a selected event ID from autocomplete
    if title and title in scheduled_events:
        event_id = title
        event_to_edit = scheduled_events[event_id]
        # Since title was used as a selector ID, we clear it so we don't 
        # accidentally rename the tournament to the ID string later
        title = None
    else:
        # Priority 2: Fallback to finding event in current channel
        current_channel_id = interaction.channel.id
        for ev_id, event_data in scheduled_events.items():
            if event_data.get('channel_id') == current_channel_id:
                event_to_edit = event_data
                event_id = ev_id
                break
    
    if not event_to_edit:
        await interaction.followup.send("❌ No event found in this ticket channel. Use `/events create` to create an event first.", ephemeral=True)
        return
    
    # NEW: Check if match has already started or is within 20 minutes
    now_utc = datetime.datetime.now(pytz.UTC)
    match_time_utc = event_to_edit['datetime']
    if match_time_utc.tzinfo is None:
        match_time_utc = match_time_utc.replace(tzinfo=pytz.UTC)
    
    time_until_match = match_time_utc - now_utc
    minutes_until_match = time_until_match.total_seconds() / 60

    if minutes_until_match < 0:
        await interaction.followup.send("❌ This match has already started or finished. You can no longer edit its details.", ephemeral=True)
        return
        
    if minutes_until_match < 20:
        await interaction.followup.send("❌ You cannot edit an event that is starting in less than 20 minutes.\n\n"
                                        "**Why?** This ensures the match reminder system works correctly for all participants.\n"
                                        "**What to do?** Please edit events at least 20 minutes before they start, or delete this event and create a new one.", ephemeral=True)
        return
    
    # Check if at least one field is provided
    if not any([title, captain1, captain2, team1, team2, hour is not None, minute is not None, date is not None, month is not None, round, group]):
        await interaction.followup.send("❌ Please provide at least one field to update.", ephemeral=True)
        return
    
    # Validate input parameters only if provided
    if hour is not None and not (0 <= hour <= 23):
        await interaction.followup.send("❌ Hour must be between 0 and 23", ephemeral=True)
        return
    
    if date is not None and not (1 <= date <= 31):
        await interaction.followup.send("❌ Date must be between 1 and 31", ephemeral=True)
        return

    if month is not None and not (1 <= month <= 12):
        await interaction.followup.send("❌ Month must be between 1 and 12", ephemeral=True)
        return
            
    if minute is not None and not (0 <= minute <= 59):
        await interaction.followup.send("❌ Minute must be between 0 and 59", ephemeral=True)
        return

    try:
        # Get current event data
        current_datetime = event_to_edit.get('datetime', datetime.datetime.now())
        current_hour = hour if hour is not None else current_datetime.hour
        current_minute = minute if minute is not None else current_datetime.minute
        current_date = date if date is not None else current_datetime.day
        current_month = month if month is not None else current_datetime.month
        
        # Create new datetime
        current_year = datetime.datetime.now().year
        new_datetime = datetime.datetime(current_year, current_month, current_date, current_hour, current_minute)
        
        # Check if new time is also at least 20 minutes in the future
        now_naive_utc = datetime.datetime.now(pytz.UTC).replace(tzinfo=None)
        if (new_datetime - now_naive_utc).total_seconds() < 1200:
             await interaction.followup.send("❌ The new match time must be at least 20 minutes in the future to ensure reminders work properly. Please choose a later time or delete/recreate the event.", ephemeral=True)
             return
        
        # Calculate time differences 
        # (Check if calculate_time_difference is accessible or needs to be called)
        time_info = calculate_time_difference(new_datetime) if 'calculate_time_difference' in globals() else {'utc_time': 'Unknown', 'minutes_remaining': 0}

        # Update only provided fields
        if team1:
            event_to_edit['team1_name'] = team1
        if team2:
            event_to_edit['team2_name'] = team2
        # Use provided captain if any, else keep current
        if captain1:
            event_to_edit['captain1_id'] = captain1.id
        if captain2:
            event_to_edit['captain2_id'] = captain2.id
        
        # Rebuild display names (resolving mentions if they were typed in team fields)
        def resolve_name(val):
            if not val: return val
            match = re.search(r'<@!?(\d+)>', str(val))
            if match:
                m_id = int(match.group(1))
                m = interaction.guild.get_member(m_id)
                if m: return m.display_name
            return str(val)

        t1_name = event_to_edit.get('team1_name', 'Team 1')
        t2_name = event_to_edit.get('team2_name', 'Team 2')
        c1_id = event_to_edit.get('captain1_id')
        c2_id = event_to_edit.get('captain2_id')
        
        # Update display names for poster/other logic if needed
        event_to_edit['team1_display_name'] = resolve_name(t1_name)
        event_to_edit['team2_display_name'] = resolve_name(t2_name)

        if c1_id: 
            if str(t1_name).strip() == f"<@{c1_id}>" or str(t1_name).strip() == f"<@!{c1_id}>":
                event_to_edit['team1_captain'] = f"<@{c1_id}>"
            else:
                event_to_edit['team1_captain'] = f"{t1_name} (<@{c1_id}>)"
        else: 
            event_to_edit['team1_captain'] = t1_name
            
        if c2_id: 
             if str(t2_name).strip() == f"<@{c2_id}>" or str(t2_name).strip() == f"<@!{c2_id}>":
                event_to_edit['team2_captain'] = f"<@{c2_id}>"
             else:
                event_to_edit['team2_captain'] = f"{t2_name} (<@{c2_id}>)"
        else: 
            event_to_edit['team2_captain'] = t2_name

        if hour is not None or minute is not None or date is not None or month is not None:
            event_to_edit['datetime'] = new_datetime
            event_to_edit['time_str'] = time_info['utc_time']
            event_to_edit['date_str'] = f"{current_date:02d}/{current_month:02d}"
            event_to_edit['minutes_left'] = time_info['minutes_remaining']
        if round:
            round_label = round.value if isinstance(round, app_commands.Choice) else str(round)
            event_to_edit['round'] = round_label
        if title:
            event_to_edit['tournament'] = title
        if group:
            event_to_edit['group'] = group.value
        
        # Save updated events
        save_scheduled_events()
        
        # Schedule the 10-minute reminder with updated event data
        try:
            await schedule_ten_minute_reminder(event_id, event_to_edit.get('team1_captain'), event_to_edit.get('team2_captain'), event_to_edit.get('judge'), interaction.channel, new_datetime)
        except Exception as e:
            print(f"Error scheduling reminder for updated event {event_id}: {e}")
        
        # Get updated event details for public posting
        team1_captain = event_to_edit.get('team1_captain')
        team2_captain = event_to_edit.get('team2_captain')
        round_info = event_to_edit.get('round', 'Unknown')
        tournament_info = event_to_edit.get('tournament', 'Unknown')
        time_info_display = event_to_edit.get('time_str', 'Unknown')
        date_info_display = event_to_edit.get('date_str', 'Unknown')
        group_info = event_to_edit.get('group', '')
        
        # Create public embed for updated event (similar to event-create)
        embed = discord.Embed(
            title="📝 Event Updated",
            description=f"**Event has been updated by {interaction.user.mention}**",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        # Event Details Section
        embed.add_field(
            name="📋 Updated Event Details", 
            value=f"**Team 1:** {team1_captain}\n"
                  f"**Team 2:** {team2_captain}\n"
                  f"**UTC Time:** {time_info_display}\n"
                  f"**Local Time:** <t:{int(new_datetime.timestamp())}:F> (<t:{int(new_datetime.timestamp())}:R>)\n"
                  f"**Round:** {round_info}\n"
                  f"**Tournament:** {tournament_info}\n"
                  f"**Channel:** {interaction.channel.mention}",
            inline=False
        )
        
        if group_info:
            embed.add_field(
                name="🏆 Group Assignment",
                value=f"**Group:** {group_info}",
                inline=False
            )
        
        # Add spacing
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        
        # Captains Section
        captains_text = f"**Captains/Teams**\n"
        captains_text += f"▪ Team 1: {team1_captain}\n"
        captains_text += f"▪ Team 2: {team2_captain}"
        embed.add_field(name="", value=captains_text, inline=False)
        
        embed.set_footer(text=f"Event Updated • {ORGANIZATION_NAME}")
        
        # Post the updated event publicly in the channel
        await interaction.channel.send(embed=embed)
        
        # Notify Judge and both Captains about the update
        judge = event_to_edit.get('judge')
        notification_text = f"🔔 {team1_captain} {team2_captain}"
        if judge:
            if hasattr(judge, 'mention'):
                notification_text += f" {judge.mention}"
            else:
                notification_text += f" <@{judge}>"
        
        # Clean names for notify embed
        def get_name(val):
            match = re.search(r'<@!?(\d+)>', str(val))
            if match:
                 m = interaction.guild.get_member(int(match.group(1)))
                 if m: return m.display_name
            return str(val)

        t1_notify_name = get_name(team1_captain)
        t2_notify_name = get_name(team2_captain)

        notify_embed = discord.Embed(
            title="⚠️ Match Details Updated",
            description=f"The details for this match have been updated by {interaction.user.mention}.\n\n"
                        f"**Teams:** {t1_notify_name} vs {t2_notify_name}\n"
                        f"**Schedule:** {event_to_edit.get('time_str')} on {event_to_edit.get('date_str')}\n\n"
                        f"Please check the updated schedule details above.",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        notify_embed.set_footer(text=f"{ORGANIZATION_NAME} • Automated Notification")
        
        await interaction.channel.send(content=notification_text, embed=notify_embed)
        
        # Send private confirmation to the user who edited
        await interaction.followup.send("✅ Event updated successfully and all parties notified!", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error updating event: {str(e)}", ephemeral=True)


@edit.autocomplete('title')
async def title_autocomplete(interaction: discord.Interaction, current: str):
    matches = []
    # Get all scheduled events
    for ev_id, data in scheduled_events.items():
        t1 = data.get('team1_name', 'T1')
        t2 = data.get('team2_name', 'T2')
        rnd = data.get('round', '')
        
        # Create a descriptive match name for the dropdown
        name = f"{t1} vs {t2}"
        if rnd:
            name += f" ({rnd})"
        
        # Filter based on current input
        if current.lower() in name.lower():
            matches.append(app_commands.Choice(name=name, value=ev_id))
            if len(matches) >= 25: # Discord limit
                break
    return matches



@tree.command(name="general_tie_breaker", description="To break a tie between two teams using the highest total score")
@app_commands.describe(
    tm1_name="Name of the first team. By default, it is Alpha",
    tm1_pl1_score="Score of the first player of the first team",
    tm1_pl2_score="Score of the second player of the first team", 
    tm1_pl3_score="Score of the third player of the first team",
    tm1_pl4_score="Score of the fourth player of the first team",
    tm1_pl5_score="Score of the fifth player of the first team",
    tm2_name="Name of the second team. By default, it is Bravo",
    tm2_pl1_score="Score of the first player of the second team",
    tm2_pl2_score="Score of the second player of the second team",
    tm2_pl3_score="Score of the third player of the second team",
    tm2_pl4_score="Score of the fourth player of the second team",
    tm2_pl5_score="Score of the fifth player of the second team"
)
async def general_tie_breaker(
    interaction: discord.Interaction,
    tm1_pl1_score: int,
    tm1_pl2_score: int,
    tm1_pl3_score: int,
    tm1_pl4_score: int,
    tm1_pl5_score: int,
    tm2_pl1_score: int,
    tm2_pl2_score: int,
    tm2_pl3_score: int,
    tm2_pl4_score: int,
    tm2_pl5_score: int,
    tm1_name: str = "Alpha",
    tm2_name: str = "Bravo"
):
    """Break a tie between two teams using the highest total score"""
    
    # Check permissions - only organizers and helpers can use this command
    if not has_event_create_permission(interaction):
        await interaction.response.send_message("❌ You need **Organizers** or **Helpers Tournament** role to use tie breaker.", ephemeral=True)
        return
    
    # Calculate team totals
    tm1_total = tm1_pl1_score + tm1_pl2_score + tm1_pl3_score + tm1_pl4_score + tm1_pl5_score
    tm2_total = tm2_pl1_score + tm2_pl2_score + tm2_pl3_score + tm2_pl4_score + tm2_pl5_score
    
    # Determine winner
    if tm1_total > tm2_total:
        winner = tm1_name
        winner_total = tm1_total
        loser = tm2_name
        loser_total = tm2_total
        color = discord.Color.green()
    elif tm2_total > tm1_total:
        winner = tm2_name
        winner_total = tm2_total
        loser = tm1_name
        loser_total = tm1_total
        color = discord.Color.green()
    else:
        # Still tied
        winner = "TIE"
        winner_total = tm1_total
        loser = ""
        loser_total = tm2_total
        color = discord.Color.orange()
    
    # Create result embed
    embed = discord.Embed(
        title="🏆 Tie Breaker Results",
        description="Results based on highest total team score",
        color=color,
        timestamp=discord.utils.utcnow()
    )
    
    # Team 1 scores
    embed.add_field(
        name=f"🔵 {tm1_name} Team",
        value=f"Player 1: `{tm1_pl1_score}`\n"
              f"Player 2: `{tm1_pl2_score}`\n"
              f"Player 3: `{tm1_pl3_score}`\n"
              f"Player 4: `{tm1_pl4_score}`\n"
              f"Player 5: `{tm1_pl5_score}`\n"
              f"**Total: {tm1_total}**",
        inline=True
    )
    
    # Team 2 scores
    embed.add_field(
        name=f"🔴 {tm2_name} Team",
        value=f"Player 1: `{tm2_pl1_score}`\n"
              f"Player 2: `{tm2_pl2_score}`\n"
              f"Player 3: `{tm2_pl3_score}`\n"
              f"Player 4: `{tm2_pl4_score}`\n"
              f"Player 5: `{tm2_pl5_score}`\n"
              f"**Total: {tm2_total}**",
        inline=True
    )
    
    # Add spacing
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    
    # Result
    if winner == "TIE":
        embed.add_field(
            name="🤝 Final Result",
            value=f"**STILL TIED!**\n"
                  f"Both teams scored {tm1_total} points\n"
                  f"Additional tie-breaking method needed",
            inline=False
        )
    else:
        embed.add_field(
            name="🏆 Winner",
            value=f"**{winner}** wins the tie breaker!\n"
                  f"**{winner}**: {winner_total} points\n"
                  f"**{loser}**: {loser_total} points\n"
                  f"Difference: {abs(winner_total - loser_total)} points",
            inline=False
        )
    
    embed.set_footer(text=f"Tie Breaker • Calculated by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)


@tree.command(name="add_captain", description="Add two captains to a tournament match and rename the channel")
@app_commands.describe(
    round="Round of the tournament (R1-R10, Q, SF, Final)",
    team1="Name of the first team",
    captain1="Mention Captain of Team 1",
    team2="Name of the second team",
    captain2="Mention Captain of Team 2",
    bracket="Optional bracket identifier (e.g., A, B, Winner, Loser)"
)
@app_commands.choices(
    round=[
        app_commands.Choice(name="R1", value="R1"),
        app_commands.Choice(name="R2", value="R2"),
        app_commands.Choice(name="R3", value="R3"),
        app_commands.Choice(name="R4", value="R4"),
        app_commands.Choice(name="R5", value="R5"),
        app_commands.Choice(name="R6", value="R6"),
        app_commands.Choice(name="R7", value="R7"),
        app_commands.Choice(name="R8", value="R8"),
        app_commands.Choice(name="R9", value="R9"),
        app_commands.Choice(name="R10", value="R10"),
        app_commands.Choice(name="Qualifier", value="Q"),
        app_commands.Choice(name="Semi Final", value="SF"),
        app_commands.Choice(name="Final", value="Final")
    ]
)
async def add_captain(interaction: discord.Interaction, round: str, team1: str, captain1: discord.Member, team2: str, captain2: discord.Member, bracket: str = None):
    """Add two captains to a tournament match and rename the channel with tournament rules."""
    try:
        # Check permissions - only Head Helper, Helper Team, Head Organizer, or Bot Owner can add captains
        if not has_event_create_permission(interaction):
            await interaction.response.send_message("❌ You don't have permission to use this command. Only staff (Helper/Organizer) or Bot Owner can add captains.", ephemeral=True)
            return
        
        # Validate round parameter
        valid_rounds = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "Q", "SF", "Final"]
        if round not in valid_rounds:
            await interaction.response.send_message("❌ Invalid round. Please select R1-R10, Q, SF, or Final.", ephemeral=True)
            return
        
        # Get current channel
        channel = interaction.channel
        
        # Create new channel name using team names
        if bracket:
            new_name = f"{bracket}-{round.lower()}-{team1.lower()}-vs-{team2.lower()}"
        else:
            new_name = f"{round.lower()}-{team1.lower()}-vs-{team2.lower()}"
        
        # Remove special characters and spaces, replace with hyphens
        new_name = re.sub(r'[^a-zA-Z0-9\-]', '-', new_name)
        new_name = re.sub(r'-+', '-', new_name)  # Replace multiple hyphens with single hyphen
        new_name = new_name.strip('-')  # Remove leading/trailing hyphens
        
        # Ensure channel name is within Discord's limits (100 characters max)
        if len(new_name) > 100:
            new_name = new_name[:100]
        
        # Rename the channel
        try:
            await channel.edit(name=new_name)
            await interaction.response.send_message(f"✅ Channel renamed to `{new_name}`", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to rename this channel.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Failed to rename channel: {e}", ephemeral=True)
            return
        
        # Add both captains to the channel
        try:
            # Add captain 1 to the channel
            await channel.set_permissions(captain1, 
                                         view_channel=True,
                                         send_messages=True)
            
            # Add captain 2 to the channel
            await channel.set_permissions(captain2, 
                                         view_channel=True,
                                         send_messages=True)
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Channel renamed but couldn't add captains - missing permissions.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"⚠️ Channel renamed but error adding captains: {e}", ephemeral=True)
        
        # Send tournament rules message
        rules_embed = discord.Embed(
            title="🏆 Tournament Match Setup",
            description="Please use this channel for all tournament discussions.",
            color=0x00ff00
        )
        
        # Add logo as thumbnail (top right)
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "Winterfell Arena Esports Logo.jpg")
            with open(logo_path, "rb") as logo_file:
                logo_data = io.BytesIO(logo_file.read())
                logo_file = discord.File(logo_data, filename="logo.jpg")
                rules_embed.set_thumbnail(url="attachment://logo.jpg")
        except FileNotFoundError:
            print("Warning: Winterfell Arena Esports Logo.jpg not found, skipping logo")
        except Exception as e:
            print(f"Warning: Could not load logo: {e}")
        
        rules_embed.add_field(
            name="📋 Tournament Information",
            value=(
                "• Refer to https://discord.com/channels/1097272892984676432/1474159759258161173 for match schedules and pairings.\n"
                "• Refer to https://discord.com/channels/1097272892984676432/1473773972851003454 for official updates.\n"
                "• Refer to https://discord.com/channels/1097272892984676432/1474159724659474442 for tournament guidelines and regulations."
            ),
            inline=False
        )
        
        rules_embed.add_field(
            name="👥 Match Participants",
            value=f"**Round:** {round}\n**Team 1:** {team1} ({captain1.mention})\n**Team 2:** {team2} ({captain2.mention})",
            inline=False
        )
        
        rules_embed.add_field(
            name="🆘 Need Help?",
            value="If you require any assistance, please ping <@&1473773792995315913> and they will be happy to assist.",
            inline=False
        )
        
        rules_embed.add_field(
            name="🤝 Cooperation",
            value="We appreciate your cooperation and wish you a competitive and fair tournament.",
            inline=False
        )
        
        rules_embed.set_footer(text=f"{ORGANIZATION_NAME} | {interaction.user.name} ✰—• • {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}")
        
        # Send the rules message with logo
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "Winterfell Arena Esports Logo.jpg")
            with open(logo_path, "rb") as logo_file:
                logo_data = io.BytesIO(logo_file.read())
                logo_file = discord.File(logo_data, filename="logo.jpg")
                await channel.send(embed=rules_embed, file=logo_file)
        except FileNotFoundError:
            print("Warning: Winterfell Arena Esports Logo.jpg not found, sending embed without logo")
            await channel.send(embed=rules_embed)
        except Exception as e:
            print(f"Warning: Could not send logo, sending embed without logo: {e}")
            await channel.send(embed=rules_embed)
        
        
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in add_captain command: {e}")


@tree.command(name="maps", description="Randomly select 3, 5, or 7 maps for gameplay")
@app_commands.describe(
    count="Number of maps to select (3, 5, or 7)"
)
async def maps(interaction: discord.Interaction, count: int):
    """Randomly selects 3, 5, or 7 maps from the available map pool"""
    
    import random
    
    # Predefined map list
    maps_list = [
        "New Storm (2024)",
        "Arid Frontier", 
        "Islands of Iceland",
        "Unexplored Rocks",
        "Arctic",
        "Lost City",
        "Polar Frontier",
        "Hidden Dragon",
        "Monstrous Maelstrom",
        "Two Samurai",
        "Stone Peaks",
        "Viking Bay",
        "Greenlands",
        "Old Storm"
    ]
    
    # Validate count
    if count not in [3, 5, 7]:
        await interaction.response.send_message("❌ Please select 3, 5, or 7 maps only.", ephemeral=True)
        return
    
    # Randomly select the specified number of maps
    selected_maps = random.sample(maps_list, count)
    
    embed = discord.Embed(
        title=f"🗺️ Random Map Selection {ORGANIZATION_NAME}",
        description=f"**Randomly selected {count} map(s):**",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )
    
    # Add selected maps as a field
    selected_maps_text = "\n".join([f"• {map_name}" for map_name in selected_maps])
    embed.add_field(
        name=f"🎯 Selected Maps ({count})",
        value=selected_maps_text,
        inline=False
    )
    
    embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
    await interaction.response.send_message(embed=embed)


@tree.command(name="test_channels", description="Test if bot can access configured channels (Organizer only)")
async def test_channels(interaction: discord.Interaction):
    """Test channel access for debugging"""
    
    # Check permissions (Owner or Head Organizer)
    if not has_organizer_permission(interaction):
        await interaction.response.send_message(
            "❌ You need to be **Bot Owner** or **Head Organizer** to use this command.",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="🔍 Channel Access Test",
        description="Testing bot access to configured channels...",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    # Test each channel
    for channel_name, channel_id in CHANNEL_IDS.items():
        channel = interaction.guild.get_channel(channel_id)
        
        if channel:
            # Check if bot can send messages
            perms = channel.permissions_for(interaction.guild.me)
            can_send = perms.send_messages
            can_embed = perms.embed_links
            can_attach = perms.attach_files
            can_mention = perms.mention_everyone
            
            status = "✅" if (can_send and can_embed) else "⚠️"
            details = f"Channel: {channel.mention}\n"
            details += f"• Send Messages: {'✅' if can_send else '❌'}\n"
            details += f"• Embed Links: {'✅' if can_embed else '❌'}\n"
            details += f"• Attach Files: {'✅' if can_attach else '❌'}\n"
            details += f"• Mention Everyone: {'✅' if can_mention else '❌'}"
            
            embed.add_field(
                name=f"{status} {channel_name.replace('_', ' ').title()}",
                value=details,
                inline=False
            )
        else:
            embed.add_field(
                name=f"❌ {channel_name.replace('_', ' ').title()}",
                value=f"Channel ID `{channel_id}` not found!\nThe channel may have been deleted or the ID is wrong.",
                inline=False
            )
    
    embed.set_footer(text=f"{ORGANIZATION_NAME}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="choose", description="Randomly choose from a list of options")
@app_commands.describe(
    options="List of options separated by commas"
)
async def choose(interaction: discord.Interaction, options: str):
    """Randomly selects one option from a comma-separated list"""
    
    import random
    
    # Handle comma-separated options (original functionality)
    option_list = [option.strip() for option in options.split(',') if option.strip()]
    
    # Validate input
    if len(option_list) < 2:
        await interaction.response.send_message("❌ Please provide at least 2 options separated by commas.", ephemeral=True)
        return
    
    if len(option_list) > 20:
        await interaction.response.send_message("❌ Too many options! Please provide 20 or fewer options.", ephemeral=True)
        return
    
    # Randomly select one option
    chosen_option = random.choice(option_list)
    
    # Create embed
    embed = discord.Embed(
        title="🎲 Random Choice",
        description=f"**Selected:** {chosen_option}",
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    
    # Add all options as a field
    options_text = "\n".join([f"• {option}" for option in option_list])
    embed.add_field(
        name=f"📋 Available Options ({len(option_list)})",
        value=options_text,
        inline=False
    )
    
    embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
    
    await interaction.response.send_message(embed=embed)










@tree.command(name="exchange", description="Exchange a Judge or Recorder for an event")
@app_commands.describe(
    role="Role to exchange",
    new_user="The new user taking the role"
)
@app_commands.choices(
    role=[
        app_commands.Choice(name="Judge", value="judge"),
        app_commands.Choice(name="Recorder", value="recorder"),
    ]
)
async def exchange(interaction: discord.Interaction, role: app_commands.Choice[str], new_user: discord.Member):
    """Exchanges a staff member for events in the current channel."""
    
    current_channel_id = interaction.channel.id
    event_found = False
    
    for ev_id, data in scheduled_events.items():
        if data.get('channel_id') == current_channel_id:
            event_found = True
            
            # Update memory
            if role.value == "judge":
                scheduled_events[ev_id]['judge'] = new_user
                try:
                    sheet_manager.update_event_staff(ev_id, judge_name=new_user.name)
                except Exception as e:
                    print(f"Error updating sheet: {e}")
            else:
                scheduled_events[ev_id]['recorder'] = new_user
                try:
                    sheet_manager.update_event_staff(ev_id, recorder_name=new_user.name)
                except Exception as e:
                    print(f"Error updating sheet: {e}")
            
            save_scheduled_events()
            
            # Announce
            await interaction.response.send_message(f"✅ {new_user.mention} is now the **{role.name}** for this event.", ephemeral=False)
            
            # Additional Notification for all parties
            team1 = data.get('team1_captain')
            team2 = data.get('team2_captain')
            current_judge = data.get('judge')
            
            pings = ""
            if team1: pings += f"{team1.mention} "
            if team2: pings += f"{team2.mention} "
            if current_judge: pings += f"{current_judge.mention} "
            
            notify_embed = discord.Embed(
                title="🔄 Staff Exchange Notification",
                description=f"Staff assignment for this match has been updated.\n\n"
                            f"**Role:** {role.name}\n"
                            f"**New Staff:** {new_user.mention}\n"
                            f"**Updated by:** {interaction.user.mention}",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            notify_embed.set_footer(text=f"{ORGANIZATION_NAME} • Match Update")
            
            if pings:
                await interaction.channel.send(content=f"🔔 {pings}", embed=notify_embed)
            break
            
    if not event_found:
        await interaction.response.send_message("❌ No scheduled event found in this channel.", ephemeral=True)

@tree.command(name="tournament-setup", description="Wipe all old data and set up for a new tournament (Bot Owner Only)")
async def tournament_setup(interaction: discord.Interaction):
    # Only bot owner
    if not await interaction.client.is_owner(interaction.user) and interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ This command is restricted to the Bot Owner ONLY.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=False)
    
    status = []
    
    # 1. Connection check
    if db and sheet_manager.client:
        status.append("✅ **Connections:** Firebase and Google Sheets are Connected.")
    elif db:
        status.append("⚠️ **Connections:** Firebase Connected, but Google Sheets disconnected.")
    elif sheet_manager.client:
        status.append("⚠️ **Connections:** Google Sheets Connected, but Firebase disconnected.")
    else:
        status.append("❌ **Connections:** Missing database connection! Aborting.")
        await interaction.followup.send("\n".join(status))
        return
        
    # 2. Sheet Cleaned
    try:
        sheet_manager.erase_sheets()
        status.append("✅ **Spreadsheets:** Previous records cleared (Headers preserved).")
    except Exception as e:
        status.append(f"❌ **Spreadsheets:** Failed to clear sheets - {e}")

    # 3. Clean local collections
    global scheduled_events, staff_stats, tournament_rules
    scheduled_events.clear()
    staff_stats.clear()
    tournament_rules.clear()
    
    # 4. Clean Firebase Collections
    try:
        if db:
            batch = db.batch()
            
            # Events
            docs = db.collection('scheduled_events').stream()
            for doc in docs:
                batch.delete(doc.reference)
                
            # Staff Stats
            docs = db.collection('staff_stats').stream()
            for doc in docs:
                batch.delete(doc.reference)
                
            # Settings
            db.collection('settings').document('tournament_rules').set({'rules': {}})
                
            batch.commit()
            status.append("✅ **Database:** All previous matches & staff stats permanently deleted from server.")
    except Exception as e:
        status.append(f"❌ **Database:** Failed to wipe Firebase - {e}")
        
    status.append("✅ **Staff Leaderboard:** Cleaned and reset to zero.")
    
    # Overwrite JSON (Fail safes)
    save_scheduled_events()
    save_staff_stats()
    save_rules()
    
    embed = discord.Embed(
        title="🛠️ Tournament Reset & Setup Complete",
        description="\n".join(status),
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="⚠️ Next Steps Required:",
        value="1. **Bracket Link:** Please upload the new bracket link.\n"
              "2. **Tournament Rules:** Please run `/rules` to write and publish the new tournament rules.",
        inline=False
    )
    
    embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
    
    await interaction.followup.send(embed=embed)


if __name__ == "__main__":
    # Load persistent data on startup
    load_scheduled_events()
    load_rules()
    load_staff_stats()
    
    # Get Discord token from environment
    token = os.environ.get("DISCORD_TOKEN")
    
    # Fallback method if direct get doesn't work
    if not token:
        for key, value in os.environ.items():
            if 'DISCORD' in key and 'TOKEN' in key:
                token = value
                break
    
    if not token:
        # Try to load from .env file directly if needed
        try:
            if os.path.exists(".env"):
                print("Loading token from .env file...")
                with open(".env", "r") as f:
                    for line in f:
                        if line.startswith("DISCORD_TOKEN="):
                            token = line.strip().split("=", 1)[1]
                            break
        except Exception as e:
            print(f"Error reading .env file: {e}")

    if not token:
        print("❌ Discord token not found in environment variables.")
        print("Please set your Discord bot token in the DISCORD_TOKEN environment variable.")
        print("You can also create a .env file with: DISCORD_TOKEN=your_token_here")
        exit(1)
    
    try:
        print("🚀 Starting Discord bot...")
        print("📡 Connecting to Discord...")
        bot.run(token, log_handler=None)  # Disable default logging to reduce startup time
    except discord.LoginFailure:
        print("❌ Invalid Discord token. Please check your bot token.")
        exit(1)
    except discord.HTTPException as e:
        print(f"❌ HTTP error connecting to Discord: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        exit(1)
