# Winterfell Arena Esports Tournament System Bot - Complete Documentation

## Table of Contents
1. [Overview](#overview)
2. [Features](#features)
3. [Commands Reference](#commands-reference)
4. [Judge Leaderboard System](#judge-leaderboard-system)
5. [Enhanced Help System](#enhanced-help-system)
6. [Installation & Setup](#installation--setup)
7. [Configuration](#configuration)
8. [Technical Architecture](#technical-architecture)

---

## Overview

The Winterfell Arena Esports Tournament System is a comprehensive Discord bot designed for managing Modern Warships tournaments. It provides event scheduling, judge management, result tracking, team balancing, and comprehensive help systems.

### Key Capabilities
- **Event Management**: Create, edit, delete tournament events
- **Judge System**: Automated judge assignment with leaderboard tracking
- **Result Recording**: Comprehensive match result logging with screenshots
- **Team Balancing**: Automatic team balancing based on skill levels
- **Interactive Help**: Enhanced help system with detailed command documentation
- **Rule Management**: Tournament rule storage and management

---

## Features

### 🏆 Tournament Management
- **Event Creation**: Schedule matches with captains, times, rounds, and groups
- **Event Editing**: Modify existing events with pre-filled values
- **Event Deletion**: Remove cancelled or incorrect events
- **Group Support**: Full support for Group A-J, Winner/Loser brackets
- **Round Management**: Support for R1-R10, Qualifier, Semi Final, Final

### 👨‍⚖️ Judge System
- **Unlimited Schedules**: Judges can take as many matches as they want
- **Automatic Assignment**: Click-to-take schedule system
- **Judge Leaderboard**: Track most active judges by matches completed
- **Statistics Tracking**: Persistent judge performance data
- **Channel Integration**: Automatic judge addition to event channels

### 📊 Result Tracking
- **Comprehensive Results**: Winner/loser scores with tournament tracking
- **Screenshot Support**: Up to 11 screenshot attachments per result
- **Multi-Channel Posting**: Results posted to multiple channels automatically
- **Staff Attendance**: Automatic staff activity logging
- **Judge Statistics**: Automatic judge leaderboard updates

### 🛠️ Utility Tools
- **Team Balancing**: Algorithm-based team balancing by skill levels
- **Random Time Generator**: Tournament-appropriate time generation
- **Random Choice**: Fair decision making for maps, colors, etc.
- **Rule Management**: Tournament rule storage and display

### 💡 Enhanced Help System
- **Interactive Navigation**: Button-based help exploration
- **Detailed Parameters**: Complete parameter documentation with examples
- **Context-Aware**: Help adapted to user roles and permissions
- **Usage Examples**: Real-world command usage scenarios
- **Tips & Warnings**: Safety information and best practices

---

## Commands Reference

### ⚙️ System Commands

#### `/help`
**Description**: Display comprehensive command guide with role-based filtering and interactive navigation
- **Usage**: `/help`
- **Permissions**: Everyone
- **Features**: 
  - Interactive button navigation
  - Role-based command filtering
  - Detailed parameter documentation
  - Usage examples and tips

#### `/rules`
**Description**: View tournament rules (or manage them if you're an organizer)
- **Usage**: `/rules`
- **Permissions**: Everyone (view) / Head Organizer (manage)
- **Features**: Persistent rule storage with version tracking

#### `/judge-leaderboard`
**Description**: Display judge leaderboard showing most active judges
- **Usage**: `/judge-leaderboard`
- **Permissions**: Everyone
- **Features**:
  - Top 10 judges by matches completed
  - Medal system (🥇🥈🥉) for top 3
  - Last activity tracking
  - Total statistics display

### 🛠️ Utility Commands

#### `/team_balance`
**Description**: Balance two teams based on player skill levels
- **Usage**: `/team_balance levels:<comma-separated levels>`
- **Permissions**: Everyone
- **Parameters**:
  - `levels` (required): Comma-separated list of player skill levels
  - Constraints: Must be numeric values, minimum 2 players
- **Examples**:
  - `/team_balance levels:48,50,51,35` - Balance 4 players
  - `/team_balance levels:45,47,49,52,53,48,46,51` - Balance 8 players

#### `/time`
**Description**: Generate a random match time between 12:00-17:59 UTC
- **Usage**: `/time`
- **Permissions**: Everyone
- **Features**: Tournament-appropriate time window, UTC timezone

#### `/choose`
**Description**: Make a random choice from comma-separated options
- **Usage**: `/choose options:<option1,option2,option3>`
- **Permissions**: Everyone
- **Parameters**:
  - `options` (required): Comma-separated list of choices
  - Constraints: Minimum 2 options, maximum 20 options
- **Examples**:
  - `/choose options:Archipelago,Beacon,Cold Waters` - Choose a map
  - `/choose options:Red,Blue,Green,Yellow` - Pick team colors

### 🏆 Event Management Commands

#### `/event-create`
**Description**: Create new tournament events with Group support and Winner/Loser options
- **Usage**: `/event-create team_1_captain:<@user> team_2_captain:<@user> hour:<0-23> minute:<0-59> date:<1-31> month:<1-12> round:<round> tournament:<name> [group:<A-J/Winner/Loser>]`
- **Permissions**: Head Organizer / Head Helper / Helper Team
- **Parameters**:
  - `team_1_captain` (required): Discord user mention for team 1 captain
  - `team_2_captain` (required): Discord user mention for team 2 captain
  - `hour` (required): Hour in 24-hour format (0-23)
  - `minute` (required): Minute (0-59)
  - `date` (required): Day of month (1-31)
  - `month` (required): Month number (1-12)
  - `round` (required): Tournament round (R1-R10, Qualifier, Semi Final, Final)
  - `tournament` (required): Tournament name
  - `group` (optional): Group designation (Group A-J, Winner, Loser)

#### `/event-edit`
**Description**: Edit existing events to correct mistakes
- **Usage**: `/event-edit`
- **Permissions**: Head Organizer / Head Helper / Helper Team
- **Features**: Interactive menu with pre-filled current values

#### `/event-result`
**Description**: Record match results with comprehensive tournament tracking
- **Usage**: `/event-result winner:<@user> winner_score:<score> loser:<@user> loser_score:<score> tournament:<name> round:<round> [group:<A-J/Winner/Loser>] [remarks:<text>] [screenshots:<1-11>]`
- **Permissions**: Head Organizer / Judge
- **Parameters**:
  - `winner` (required): Winning captain Discord mention
  - `winner_score` (required): Winner's score (positive integer)
  - `loser` (required): Losing captain Discord mention
  - `loser_score` (required): Loser's score (non-negative integer)
  - `tournament` (required): Tournament name (must match event)
  - `round` (required): Tournament round (must match event)
  - `group` (optional): Group designation if applicable
  - `remarks` (optional): Additional match notes
  - `screenshots` (optional): Number of screenshot attachments (1-11)
- **Features**:
  - Multi-channel result posting
  - Automatic judge statistics update
  - Screenshot evidence support
  - Staff attendance logging

#### `/event-delete`
**Description**: Delete scheduled events (use with caution)
- **Usage**: `/event-delete`
- **Permissions**: Head Organizer / Head Helper / Helper Team
- **Features**: Interactive selection menu

#### `/unassigned_events`
**Description**: List all events without a judge assigned
- **Usage**: `/unassigned_events`
- **Permissions**: Head Organizer / Head Helper / Helper Team / Judge
- **Features**: Easy judge assignment overview

#### `/exchange_judge`
**Description**: Exchange an old judge for a new judge for events in current channel
- **Usage**: `/exchange_judge old_judge:<@user> new_judge:<@user>`
- **Permissions**: Head Organizer / Head Helper / Helper Team
- **Parameters**:
  - `old_judge` (required): Judge to be replaced
  - `new_judge` (required): Replacement judge

### 👨‍⚖️ Judge Commands

#### Take Schedule Button
**Description**: Click the 'Take Schedule' button on event posts to assign yourself as judge
- **Usage**: Click button on event announcements
- **Permissions**: Judge / Head Organizer
- **Features**:
  - Unlimited schedule taking for judges
  - Automatic channel addition
  - Real-time assignment updates

---

## Judge Leaderboard System

### Overview
The judge leaderboard system tracks judge activity and encourages participation through gamification.

### Features
- **Automatic Tracking**: Statistics updated when judges use `/event-result`
- **Persistent Storage**: Data saved to `judge_stats.json`
- **Leaderboard Display**: Top 10 judges with medal system
- **Activity Tracking**: Last activity dates and match counts
- **Public Access**: Anyone can view the leaderboard

### Data Structure
```json
{
  "judge_id": {
    "name": "Judge Display Name",
    "matches_judged": 15,
    "last_activity": "2024-01-18T10:30:00"
  }
}
```

### Leaderboard Features
- 🥇🥈🥉 Medal system for top 3 judges
- Match count display for each judge
- Last activity tracking (Today, Yesterday, X days ago)
- Total statistics (total judges, total matches)
- Automatic updates when results are recorded

---

## Enhanced Help System

### Interactive Navigation
The help system features button-based navigation for easy exploration:

#### Category Buttons
- **⚙️ System**: Basic bot functionality
- **🛠️ Utility**: Tournament management tools
- **🏆 Events**: Event management commands (permission-based)
- **👨‍⚖️ Judge**: Judge-specific commands (permission-based)
- **🔄 Back to Overview**: Return to main help

#### Command Detail Views
- **Complete Parameter Documentation**: Types, constraints, examples
- **Usage Examples**: Real-world scenarios with explanations
- **Tips & Warnings**: Safety information and best practices
- **Related Commands**: Workflow suggestions
- **Common Errors**: Troubleshooting information

### Permission-Based Filtering
Help content is automatically filtered based on user roles:
- **Everyone**: System and utility commands
- **Judge**: Additional judge commands
- **Helper/Organizer**: Full event management access
- **Owner**: All commands and features

### Enhanced Documentation Features
- **Parameter Details**: Type, required/optional, constraints, examples
- **Multiple Examples**: Different usage scenarios
- **Safety Warnings**: For commands that affect critical data
- **Efficiency Tips**: Best practices and shortcuts
- **Error Prevention**: Common mistakes and solutions

---

## Installation & Setup

### Prerequisites
- Python 3.8 or higher
- Discord.py library
- Required Python packages (see requirements.txt)

### Environment Variables
Create a `.env` file with:
```
DISCORD_TOKEN=your_bot_token_here
```

### Bot Permissions
The bot requires the following Discord permissions:
- Send Messages
- Use Slash Commands
- Embed Links
- Attach Files
- Read Message History
- Manage Channels (for judge assignment)
- Mention Everyone (for notifications)

### Channel Configuration
Update `CHANNEL_IDS` in the code with your server's channel IDs:
```python
CHANNEL_IDS = {
    "take_schedule": your_schedule_channel_id,
    "results": your_results_channel_id,
    "transcript": your_transcript_channel_id,
    "staff_attendance": your_staff_attendance_channel_id
}
```

### Role Configuration
Update `ROLE_IDS` with your server's role IDs:
```python
ROLE_IDS = {
    "judge": your_judge_role_id,
    "head_helper": your_head_helper_role_id,
    "helper_team": your_helper_team_role_id,
    "head_organizer": your_head_organizer_role_id
}
```

---

## Configuration

### File Structure
```
Guardian Angel/
├── app.py                    # Main bot file
├── .env                      # Environment variables
├── requirements.txt          # Python dependencies
├── scheduled_events.json     # Event storage (auto-generated)
├── tournament_rules.json     # Rules storage (auto-generated)
├── judge_stats.json         # Judge statistics (auto-generated)
└── GUARDIAN_ANGEL_BOT_DOCUMENTATION.md
```

### Data Persistence
The bot automatically creates and manages these JSON files:
- **scheduled_events.json**: Stores all scheduled tournament events
- **tournament_rules.json**: Stores tournament rules with version tracking
- **judge_stats.json**: Stores judge statistics and leaderboard data

### Startup Process
On startup, the bot automatically:
1. Loads scheduled events from file
2. Loads tournament rules from file
3. Loads judge statistics from file
4. Initializes Discord connection
5. Registers slash commands

---

## Technical Architecture

### Core Components

#### Event Management System
- **Event Storage**: JSON-based persistent storage
- **Reminder System**: Automated event reminders
- **Cleanup System**: Automatic event cleanup after results
- **Channel Integration**: Dynamic channel creation and management

#### Judge Management System
- **Assignment Tracking**: Real-time judge assignment management
- **Statistics Engine**: Automatic performance tracking
- **Leaderboard System**: Ranking and display system
- **Unlimited Scheduling**: No limits on judge assignments

#### Help System Architecture
- **Interactive Views**: Discord UI components for navigation
- **Permission Engine**: Role-based content filtering
- **Command Documentation**: Comprehensive parameter and usage documentation
- **Context Awareness**: Channel and role-based help adaptation

#### Data Models
```python
# Event Data Structure
{
    "event_id": {
        "team1_captain": discord.Member,
        "team2_captain": discord.Member,
        "datetime": datetime,
        "tournament": str,
        "round": str,
        "group": str,
        "judge": discord.Member,
        "channel_id": int,
        "result_added": bool
    }
}

# Judge Statistics Structure
{
    "judge_id": {
        "name": str,
        "matches_judged": int,
        "last_activity": datetime
    }
}

# Command Data Structure
{
    "category": {
        "title": str,
        "description": str,
        "commands": [
            {
                "name": str,
                "description": str,
                "usage": str,
                "permissions": str,
                "parameters": [
                    {
                        "name": str,
                        "type": str,
                        "required": bool,
                        "description": str,
                        "constraints": str,
                        "examples": list
                    }
                ],
                "usage_examples": list,
                "tips_and_warnings": list,
                "related_commands": list,
                "common_errors": list
            }
        ]
    }
}
```

### Error Handling
- **Graceful Degradation**: Fallback mechanisms for all major features
- **User-Friendly Messages**: Clear error messages for users
- **Logging System**: Comprehensive error logging for debugging
- **Recovery Mechanisms**: Automatic recovery from common failures

### Performance Considerations
- **Lazy Loading**: Help content loaded on demand
- **Caching**: Command data cached for performance
- **Async Operations**: Non-blocking Discord API interactions
- **Resource Management**: Proper cleanup of Discord UI components

---

## Support & Maintenance

### Regular Maintenance Tasks
1. **Monitor Log Files**: Check for errors and performance issues
2. **Backup Data Files**: Regular backups of JSON data files
3. **Update Dependencies**: Keep Discord.py and other packages updated
4. **Review Judge Statistics**: Monitor judge activity and leaderboard accuracy

### Troubleshooting Common Issues
1. **Bot Not Responding**: Check Discord token and permissions
2. **Commands Not Working**: Verify role IDs and channel IDs
3. **Data Loss**: Restore from JSON backup files
4. **Performance Issues**: Check for memory leaks and optimize queries

### Feature Requests & Bug Reports
For feature requests or bug reports, please provide:
- Detailed description of the issue or request
- Steps to reproduce (for bugs)
- Expected vs actual behavior
- Discord server and bot configuration details

---

*This documentation covers all features and functionality of the Winterfell Arena Esports Tournament System Bot. For technical support or additional information, please contact the development team.*