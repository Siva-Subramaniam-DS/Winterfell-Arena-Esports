# 🎯 Enhanced Discord Event Management Bot

A comprehensive Discord bot for managing tournament events, judge assignments, and team coordination with advanced features and robust error handling.

## ✨ Features

### 🏆 Event Management
- **Event Creation**: Create tournament events with automatic scheduling
- **Judge Assignment**: Smart judge assignment system with workload balancing
- **Automatic Reminders**: 10-minute pre-event notifications
- **Result Recording**: Comprehensive match result logging

### 👨‍⚖️ Judge Management
- **Assignment Tracking**: Persistent judge assignment storage
- **Workload Limits**: Configurable maximum assignments per judge
- **Smart Scheduling**: Prevent judge overloading
- **Assignment Statistics**: Real-time workload monitoring

### 🛡️ Enhanced Reliability
- **Comprehensive Logging**: Multi-level logging with file rotation
- **Error Recovery**: Graceful error handling and state recovery
- **Race Condition Protection**: Thread-safe operations
- **Data Persistence**: Automatic data backup and recovery

### ⚙️ Configuration
- **Environment Variables**: Flexible configuration via .env
- **Feature Flags**: Enable/disable features as needed
- **Validation**: Comprehensive configuration validation
- **Hot Reload**: Configuration updates without restart

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Discord Bot Token
- Required permissions in your Discord server

### Judge System
- Interactive buttons for taking/releasing schedules
- Automatic workload balancing
- Real-time assignment tracking

## 🔧 Advanced Features

### Logging System
- **Multi-level logging**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **File rotation**: Automatic log file management
- **Structured logging**: Consistent log format across modules
- **Performance monitoring**: Track command usage and response times

### Error Handling
- **Graceful degradation**: Continue operation despite errors
- **User-friendly messages**: Clear error communication
- **Automatic recovery**: Self-healing mechanisms
- **Comprehensive logging**: Full error context capture

### Data Management
- **Persistent storage**: JSON-based data persistence
- **Automatic backups**: Regular data snapshots
- **Data validation**: Input sanitization and validation
- **Migration support**: Schema version management

## 🐛 Troubleshooting

### Common Issues

1. **Bot not responding**
   - Check bot token in `.env` file
   - Verify bot permissions in Discord server
   - Check logs in `logs/bot.log`

2. **Commands not syncing**
   - Restart the bot to force command sync
   - Check for errors in `logs/errors.log`
   - Verify bot has application command permissions

3. **Judge assignments not working**
   - Check `data/judge_assignments.json` exists
   - Verify role IDs in configuration
   - Check logs for permission errors

### Log Files
- `logs/bot.log` - General application logs
- `logs/errors.log` - Error-specific logs
- `logs/discord.log` - Discord.py library logs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support, please:
1. Check the troubleshooting section
2. Review log files for errors
3. Create an issue with detailed information
4. Include relevant log excerpts

## 🔄 Version History

### v2.0.0 (Current)
- Enhanced error handling and logging
- Persistent judge assignment storage
- Improved embed manipulation
- Configuration management system
- Comprehensive validation

### v1.0.0
- Basic event management
- Judge assignment system
- Discord slash commands
- Simple embed handling
