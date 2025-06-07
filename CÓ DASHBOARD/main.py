
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime, timedelta
import threading
from flask import Flask, render_template, jsonify
import time

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
bot_start_time = None

def get_bot_data():
    """Get bot data for web dashboard"""
    if not bot.is_ready():
        return {
            'bot_online': False,
            'servers': [],
            'total_servers': 0,
            'total_members': 0,
            'uptime': '0 seconds'
        }
    
    # Calculate uptime
    uptime_str = 'Unknown'
    if bot_start_time:
        uptime_seconds = int(time.time() - bot_start_time)
        uptime_delta = timedelta(seconds=uptime_seconds)
        
        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        elif hours > 0:
            uptime_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            uptime_str = f"{minutes}m {seconds}s"
        else:
            uptime_str = f"{seconds}s"
    
    servers_data = []
    total_members = 0
    total_channels = 0
    total_backups = 0
    
    for guild in bot.guilds:
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
        
        server_info = {
            'id': str(guild.id),
            'name': guild.name,
            'description': guild.description,
            'owner_name': owner_name,
            'invite_url': None,
            'icon_url': str(guild.icon.url) if guild.icon else None
        }
        
        servers_data.append(server_info)
        total_members += guild.member_count
        total_channels += len(guild.channels)
    
    return {
        'bot_online': True,
        'servers': servers_data,
        'total_servers': len(servers_data),
        'uptime': uptime_str
    }

# Flask web dashboard
web_app = Flask(__name__)

@web_app.route('/')
def dashboard():
    """Main dashboard page"""
    data = get_bot_data()
    return render_template('index.html', **data)

def run_web_server():
    """Run the Flask web server"""
    web_app.run(host='0.0.0.0', port=5000, debug=False)

@bot.event
async def on_ready():
    global bot_start_time
    bot_start_time = time.time()
    print(f'{bot.user} has logged in!')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
        
        # Start web dashboard in a separate thread
        web_thread = threading.Thread(target=run_web_server)
        web_thread.daemon = True
        web_thread.start()
        print("Web dashboard started at http://localhost:5000")
        
    except Exception as e:
        print(f'Failed to sync commands: {e}')

@bot.tree.command(name="load-backup", description="Create a backup of the server")
@app_commands.describe(backup_name="Name for the backup file (optional)")
async def backup_server(interaction: discord.Interaction, backup_name: str = None):
    # Check if user has administrator permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
        return
    
    await interaction.response.defer(thinking=True)
    
    guild = interaction.guild
    backup_data = {
        "server_info": {
            "name": guild.name,
            "id": str(guild.id),
            "description": guild.description,
            "owner_id": str(guild.owner_id),
            "verification_level": str(guild.verification_level),
            "backup_date": datetime.now().isoformat()
        },
        "channels": [],
        "categories": [],
        "roles": [],
        "emojis": []
    }
    
    # Backup categories
    for category in guild.categories:
        category_data = {
            "name": category.name,
            "id": str(category.id),
            "position": category.position,
            "overwrites": []
        }
        
        # Save permission overwrites
        for target, overwrite in category.overwrites.items():
            category_data["overwrites"].append({
                "target_type": "role" if isinstance(target, discord.Role) else "member",
                "target_id": str(target.id),
                "allow": overwrite.pair()[0].value,
                "deny": overwrite.pair()[1].value
            })
        
        backup_data["categories"].append(category_data)
    
    # Backup channels
    for channel in guild.channels:
        if isinstance(channel, discord.CategoryChannel):
            continue
            
        channel_data = {
            "name": channel.name,
            "id": str(channel.id),
            "type": str(channel.type),
            "position": channel.position,
            "category_id": str(channel.category.id) if channel.category else None,
            "overwrites": []
        }
        
        # Add specific data based on channel type
        if isinstance(channel, discord.TextChannel):
            channel_data.update({
                "topic": channel.topic,
                "slowmode_delay": channel.slowmode_delay,
                "nsfw": channel.nsfw
            })
        elif isinstance(channel, discord.VoiceChannel):
            channel_data.update({
                "bitrate": channel.bitrate,
                "user_limit": channel.user_limit
            })
        
        # Save permission overwrites
        for target, overwrite in channel.overwrites.items():
            channel_data["overwrites"].append({
                "target_type": "role" if isinstance(target, discord.Role) else "member",
                "target_id": str(target.id),
                "allow": overwrite.pair()[0].value,
                "deny": overwrite.pair()[1].value
            })
        
        backup_data["channels"].append(channel_data)
    
    # Backup roles
    for role in guild.roles:
        if role.name == "@everyone":
            continue
            
        role_data = {
            "name": role.name,
            "id": str(role.id),
            "color": role.color.value,
            "hoist": role.hoist,
            "mentionable": role.mentionable,
            "permissions": role.permissions.value,
            "position": role.position
        }
        backup_data["roles"].append(role_data)
    
    # Backup emojis
    for emoji in guild.emojis:
        emoji_data = {
            "name": emoji.name,
            "id": str(emoji.id),
            "animated": emoji.animated,
            "url": str(emoji.url)
        }
        backup_data["emojis"].append(emoji_data)
    
    # Create backups directory if it doesn't exist
    if not os.path.exists("backups"):
        os.makedirs("backups")
    
    # Generate filename with server ID for server-specific backups
    server_dir = f"backups/{guild.id}"
    if not os.path.exists(server_dir):
        os.makedirs(server_dir)
    
    if backup_name:
        filename = f"{server_dir}/{backup_name}_{guild.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    else:
        filename = f"{server_dir}/{guild.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Save backup to file
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        
        # Create embed for success message
        embed = discord.Embed(
            title="✅ Server Backup Complete!",
            description=f"Successfully backed up **{guild.name}**",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📊 Backup Stats",
            value=f"**Categories:** {len(backup_data['categories'])}\n"
                  f"**Channels:** {len(backup_data['channels'])}\n"
                  f"**Roles:** {len(backup_data['roles'])}\n"
                  f"**Emojis:** {len(backup_data['emojis'])}",
            inline=False
        )
        
        embed.add_field(
            name="📁 File",
            value=f"`{filename}`",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Backup Failed",
            description=f"An error occurred while creating the backup: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed)

@bot.tree.command(name="list-backups", description="List all available server backups")
async def list_backups(interaction: discord.Interaction):
    server_backup_dir = f"backups/{interaction.guild.id}"
    if not os.path.exists(server_backup_dir):
        await interaction.response.send_message("📁 No backups found for this server.", ephemeral=True)
        return
    
    backup_files = [f for f in os.listdir(server_backup_dir) if f.endswith('.json')]
    
    if not backup_files:
        await interaction.response.send_message("📁 No backup files found.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📋 Available Backups",
        description=f"Found {len(backup_files)} backup file(s)",
        color=discord.Color.blue()
    )
    
    # Show up to 10 most recent backups
    backup_files.sort(reverse=True)
    for i, filename in enumerate(backup_files[:10]):
        file_path = os.path.join(server_backup_dir, filename)
        file_size = os.path.getsize(file_path)
        embed.add_field(
            name=f"📄 {filename}",
            value=f"Size: {file_size:,} bytes",
            inline=False
        )
    
    if len(backup_files) > 10:
        embed.set_footer(text=f"Showing 10 of {len(backup_files)} backups")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="reset-file", description="Remove all backup files")
async def reset_backup_files(interaction: discord.Interaction):
    # Check if user has administrator permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
        return
    
    await interaction.response.defer(thinking=True)
    
    # Check if server backup directory exists
    server_backup_dir = f"backups/{interaction.guild.id}"
    if not os.path.exists(server_backup_dir):
        await interaction.followup.send("📁 No backups found for this server - nothing to delete.")
        return
    
    try:
        # Get list of all backup files for this server
        backup_files = [f for f in os.listdir(server_backup_dir) if f.endswith('.json')]
        
        if not backup_files:
            await interaction.followup.send("📁 No backup files found - nothing to delete.")
            return
        
        # Delete all backup files for this server
        deleted_count = 0
        for filename in backup_files:
            file_path = os.path.join(server_backup_dir, filename)
            os.remove(file_path)
            deleted_count += 1
        
        # Create success embed
        embed = discord.Embed(
            title="🗑️ Backup Files Deleted!",
            description=f"Successfully deleted {deleted_count} backup file(s)",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📊 Deletion Summary",
            value=f"**Files Deleted:** {deleted_count}\n**Directory:** `backups/`",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Deletion Failed",
            description=f"An error occurred while deleting backup files: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed)

@bot.tree.command(name="blackup", description="Restore server from a backup file")
@app_commands.describe(backup_filename="Name of the backup file to restore from")
async def restore_server(interaction: discord.Interaction, backup_filename: str):
    # Check if user has administrator permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
        return
    
    await interaction.response.defer(thinking=True)
    
    # Check if backup file exists in server directory
    server_backup_dir = f"backups/{interaction.guild.id}"
    backup_path = os.path.join(server_backup_dir, backup_filename)
    if not os.path.exists(backup_path):
        await interaction.followup.send("❌ Backup file not found! Use `/list-backups` to see available backups for this server.")
        return
    
    try:
        # Load backup data
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        guild = interaction.guild
        restored = {"roles": 0, "categories": 0, "channels": 0}
        errors = []
        
        # Restore roles first (excluding @everyone)
        existing_roles = {role.name: role for role in guild.roles}
        for role_data in backup_data["roles"]:
            try:
                if role_data["name"] not in existing_roles:
                    await guild.create_role(
                        name=role_data["name"],
                        color=discord.Color(role_data["color"]),
                        hoist=role_data["hoist"],
                        mentionable=role_data["mentionable"],
                        permissions=discord.Permissions(role_data["permissions"])
                    )
                    restored["roles"] += 1
            except Exception as e:
                errors.append(f"Role '{role_data['name']}': {str(e)}")
        
        # Restore categories
        existing_categories = {cat.name: cat for cat in guild.categories}
        category_mapping = {}
        for cat_data in backup_data["categories"]:
            try:
                if cat_data["name"] not in existing_categories:
                    overwrites = {}
                    # Restore category permissions
                    for overwrite_data in cat_data["overwrites"]:
                        target = None
                        if overwrite_data["target_type"] == "role":
                            target = discord.utils.get(guild.roles, id=int(overwrite_data["target_id"]))
                        else:
                            target = guild.get_member(int(overwrite_data["target_id"]))
                        
                        if target:
                            overwrites[target] = discord.PermissionOverwrite.from_pair(
                                discord.Permissions(overwrite_data["allow"]),
                                discord.Permissions(overwrite_data["deny"])
                            )
                    
                    category = await guild.create_category(
                        name=cat_data["name"],
                        overwrites=overwrites
                    )
                    category_mapping[cat_data["id"]] = category
                    restored["categories"] += 1
                else:
                    category_mapping[cat_data["id"]] = existing_categories[cat_data["name"]]
            except Exception as e:
                errors.append(f"Category '{cat_data['name']}': {str(e)}")
        
        # Restore channels
        existing_channels = {ch.name: ch for ch in guild.channels if not isinstance(ch, discord.CategoryChannel)}
        for channel_data in backup_data["channels"]:
            try:
                if channel_data["name"] not in existing_channels:
                    overwrites = {}
                    # Restore channel permissions
                    for overwrite_data in channel_data["overwrites"]:
                        target = None
                        if overwrite_data["target_type"] == "role":
                            target = discord.utils.get(guild.roles, id=int(overwrite_data["target_id"]))
                        else:
                            target = guild.get_member(int(overwrite_data["target_id"]))
                        
                        if target:
                            overwrites[target] = discord.PermissionOverwrite.from_pair(
                                discord.Permissions(overwrite_data["allow"]),
                                discord.Permissions(overwrite_data["deny"])
                            )
                    
                    category = category_mapping.get(channel_data["category_id"])
                    
                    if channel_data["type"] == "text":
                        await guild.create_text_channel(
                            name=channel_data["name"],
                            category=category,
                            topic=channel_data.get("topic"),
                            slowmode_delay=channel_data.get("slowmode_delay", 0),
                            nsfw=channel_data.get("nsfw", False),
                            overwrites=overwrites
                        )
                    elif channel_data["type"] == "voice":
                        await guild.create_voice_channel(
                            name=channel_data["name"],
                            category=category,
                            bitrate=channel_data.get("bitrate", 64000),
                            user_limit=channel_data.get("user_limit", 0),
                            overwrites=overwrites
                        )
                    
                    restored["channels"] += 1
            except Exception as e:
                errors.append(f"Channel '{channel_data['name']}': {str(e)}")
        
        # Create success embed
        embed = discord.Embed(
            title="🔄 Server Restore Complete!",
            description=f"Successfully restored from backup: `{backup_filename}`",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📊 Restored Items",
            value=f"**Roles:** {restored['roles']}\n"
                  f"**Categories:** {restored['categories']}\n"
                  f"**Channels:** {restored['channels']}",
            inline=False
        )
        
        if errors:
            error_text = "\n".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                error_text += f"\n... and {len(errors) - 5} more errors"
            
            embed.add_field(
                name="⚠️ Errors",
                value=f"```{error_text}```",
                inline=False
            )
        
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Restore Failed",
            description=f"An error occurred while restoring the backup: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed)
    
bot.run('Bottoken')
