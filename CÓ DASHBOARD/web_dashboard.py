
from flask import Flask, render_template, jsonify
import discord
import json
import os
import asyncio
import threading
from datetime import datetime

# Import bot from main.py
import main

app = Flask(__name__)

def get_bot_data():
    """Get bot data including servers and statistics"""
    if not main.bot.is_ready():
        return {
            'bot_online': False,
            'servers': [],
            'total_servers': 0,
            'total_members': 0,
            'total_channels': 0,
            'total_backups': 0
        }
    
    servers_data = []
    total_members = 0
    total_channels = 0
    total_backups = 0
    
    for guild in main.bot.guilds:
        # Count backups for this server
        backup_count = 0
        server_backup_dir = f"backups/{guild.id}"
        if os.path.exists(server_backup_dir):
            backup_files = [f for f in os.listdir(server_backup_dir) if f.endswith('.json')]
            backup_count = len(backup_files)
            total_backups += backup_count
        
        # Get server owner name
        owner_name = "Unknown"
        if guild.owner:
            owner_name = guild.owner.display_name
        
        # Create invite link (if bot has permissions)
        invite_url = None
        try:
            # Try to create an invite for the first text channel
            text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]
            if text_channels and guild.me.guild_permissions.create_instant_invite:
                invite = asyncio.run_in_executor(None, lambda: asyncio.create_task(text_channels[0].create_invite(max_age=0, max_uses=0)))
                # Note: This is a simplified approach, in practice you'd want to handle this more carefully
        except:
            pass
        
        server_info = {
            'id': str(guild.id),
            'name': guild.name,
            'description': guild.description,
            'member_count': guild.member_count,
            'channel_count': len(guild.channels),
            'owner_name': owner_name,
            'backup_count': backup_count,
            'invite_url': invite_url,
            'icon_url': str(guild.icon.url) if guild.icon else None
        }
        
        servers_data.append(server_info)
        total_members += guild.member_count
        total_channels += len(guild.channels)
    
    return {
        'bot_online': True,
        'servers': servers_data,
        'total_servers': len(servers_data),
        'total_members': total_members,
        'total_channels': total_channels,
        'total_backups': total_backups
    }

@app.route('/')
def dashboard():
    """Main dashboard page"""
    data = get_bot_data()
    return render_template('index.html', **data)

@app.route('/api/bot-stats')
def bot_stats():
    """API endpoint for bot statistics"""
    return jsonify(get_bot_data())

@app.route('/api/server/<server_id>')
def server_details(server_id):
    """Get detailed information about a specific server"""
    try:
        guild = main.bot.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        
        # Get backup files for this server
        backups = []
        server_backup_dir = f"backups/{guild.id}"
        if os.path.exists(server_backup_dir):
            backup_files = [f for f in os.listdir(server_backup_dir) if f.endswith('.json')]
            for filename in backup_files:
                file_path = os.path.join(server_backup_dir, filename)
                file_stats = os.stat(file_path)
                backups.append({
                    'filename': filename,
                    'size': file_stats.st_size,
                    'created': datetime.fromtimestamp(file_stats.st_ctime).isoformat()
                })
        
        server_data = {
            'id': str(guild.id),
            'name': guild.name,
            'description': guild.description,
            'member_count': guild.member_count,
            'channel_count': len(guild.channels),
            'role_count': len(guild.roles),
            'emoji_count': len(guild.emojis),
            'owner': {
                'id': str(guild.owner_id),
                'name': guild.owner.display_name if guild.owner else 'Unknown'
            },
            'verification_level': str(guild.verification_level),
            'backups': backups
        }
        
        return jsonify(server_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_web_server():
    """Run the Flask web server"""
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    # Start web server in a separate thread
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    
    print("Web dashboard will be available at http://localhost:5000")
    print("Starting Discord bot...")
