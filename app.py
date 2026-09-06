import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput
import os
import json
import secrets
import asyncio
import aiohttp
import requests
import threading
import time
from datetime import datetime, timedelta
import random
import re
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Initialize bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Firebase setup (mock for local/railway testing)
class FirebaseDB:
    def __init__(self):
        self.data = {}
        self.load_data()
    
    def load_data(self):
        try:
            if os.path.exists('./data/db.json'):
                with open('./data/db.json', 'r') as f:
                    self.data = json.load(f)
            else:
                self.data = {'users': {}, 'guilds': {}, 'giveaways': {}, 'tickets': {}, 'notes': {}}
                self.save_data()
        except:
            self.data = {'users': {}, 'guilds': {}, 'giveaways': {}, 'tickets': {}, 'notes': {}}
            self.save_data()
    
    def save_data(self):
        try:
            os.makedirs('./data', exist_ok=True)
            with open('./data/db.json', 'w') as f:
                json.dump(self.data, f, indent=2)
        except:
            pass
    
    def get_user(self, user_id, guild_id):
        user_id = str(user_id)
        guild_id = str(guild_id)
        if guild_id not in self.data['users']:
            self.data['users'][guild_id] = {}
        if user_id not in self.data['users'][guild_id]:
            self.data['users'][guild_id][user_id] = {
                'verified': False,
                'profile': {},
                'tickets': [],
                'notes': []
            }
            self.save_data()
        return self.data['users'][guild_id][user_id]
    
    def set_user(self, user_id, guild_id, data):
        user_id = str(user_id)
        guild_id = str(guild_id)
        if guild_id not in self.data['users']:
            self.data['users'][guild_id] = {}
        self.data['users'][guild_id][user_id] = data
        self.save_data()
    
    def get_guild(self, guild_id):
        guild_id = str(guild_id)
        if guild_id not in self.data['guilds']:
            return None
        return self.data['guilds'][guild_id]
    
    def set_guild(self, guild_id, data):
        guild_id = str(guild_id)
        self.data['guilds'][guild_id] = data
        self.save_data()

firebase = FirebaseDB()

# Verification data storage
verification_sessions = {}

# Keep alive function for Railway
def keep_alive():
    """Keep the bot alive on Railway free tier"""
    while True:
        try:
            url = os.getenv('WEBSITE_URL', 'http://localhost:8080')
            if url and url != 'http://localhost:8080':
                requests.get(url, timeout=5)
        except:
            pass
        time.sleep(300)  # Ping every 5 minutes

# ============ SETUP VIEW ============
class SetupView(View):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
    
    async def setup_all(self, guild):
        """Create all channels and roles"""
        try:
            category = await guild.create_category("📋 Server Management")
        except:
            category = discord.utils.get(guild.categories, name="📋 Server Management")
            if not category:
                category = await guild.create_category("📋 Server Management")
        
        # Create channels
        try:
            verify_channel = await guild.create_text_channel("🔐-verification", category=category)
        except:
            verify_channel = discord.utils.get(guild.text_channels, name="🔐-verification")
            if not verify_channel:
                verify_channel = await guild.create_text_channel("🔐-verification", category=category)
        
        try:
            ticket_channel = await guild.create_text_channel("🎫-tickets", category=category)
        except:
            ticket_channel = discord.utils.get(guild.text_channels, name="🎫-tickets")
            if not ticket_channel:
                ticket_channel = await guild.create_text_channel("🎫-tickets", category=category)
        
        try:
            giveaway_channel = await guild.create_text_channel("🎉-giveaways", category=category)
        except:
            giveaway_channel = discord.utils.get(guild.text_channels, name="🎉-giveaways")
            if not giveaway_channel:
                giveaway_channel = await guild.create_text_channel("🎉-giveaways", category=category)
        
        try:
            mod_channel = await guild.create_text_channel("🛡️-mod-logs", category=category)
        except:
            mod_channel = discord.utils.get(guild.text_channels, name="🛡️-mod-logs")
            if not mod_channel:
                mod_channel = await guild.create_text_channel("🛡️-mod-logs", category=category)
        
        # Create roles
        try:
            verified_role = await guild.create_role(name="✅ Verified", color=discord.Color.green())
        except:
            verified_role = discord.utils.get(guild.roles, name="✅ Verified")
            if not verified_role:
                verified_role = await guild.create_role(name="✅ Verified", color=discord.Color.green())
        
        try:
            unverified_role = await guild.create_role(name="❌ Unverified", color=discord.Color.red())
        except:
            unverified_role = discord.utils.get(guild.roles, name="❌ Unverified")
            if not unverified_role:
                unverified_role = await guild.create_role(name="❌ Unverified", color=discord.Color.red())
        
        try:
            mod_role = await guild.create_role(name="🛡️ Moderator", color=discord.Color.blue())
        except:
            mod_role = discord.utils.get(guild.roles, name="🛡️ Moderator")
            if not mod_role:
                mod_role = await guild.create_role(name="🛡️ Moderator", color=discord.Color.blue())
        
        try:
            admin_role = await guild.create_role(name="👑 Admin", color=discord.Color.gold())
        except:
            admin_role = discord.utils.get(guild.roles, name="👑 Admin")
            if not admin_role:
                admin_role = await guild.create_role(name="👑 Admin", color=discord.Color.gold())
        
        try:
            helper_role = await guild.create_role(name="🤝 Helper", color=discord.Color.purple())
        except:
            helper_role = discord.utils.get(guild.roles, name="🤝 Helper")
            if not helper_role:
                helper_role = await guild.create_role(name="🤝 Helper", color=discord.Color.purple())
        
        try:
            giveaway_role = await guild.create_role(name="🎁 Giveaway", color=discord.Color.magenta())
        except:
            giveaway_role = discord.utils.get(guild.roles, name="🎁 Giveaway")
            if not giveaway_role:
                giveaway_role = await guild.create_role(name="🎁 Giveaway", color=discord.Color.magenta())
        
        # Store in database
        guild_data = {
            'category_id': category.id,
            'channels': {
                'verify': verify_channel.id,
                'tickets': ticket_channel.id,
                'giveaways': giveaway_channel.id,
                'mod_logs': mod_channel.id
            },
            'roles': {
                'verified': verified_role.id,
                'unverified': unverified_role.id,
                'mod': mod_role.id,
                'admin': admin_role.id,
                'helper': helper_role.id,
                'giveaway': giveaway_role.id
            }
        }
        firebase.set_guild(guild.id, guild_data)
        
        return verify_channel, ticket_channel, giveaway_channel
    
    @discord.ui.button(label="⚡ Setup All", style=discord.ButtonStyle.success, emoji="⚡")
    async def setup_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin who ran /setup can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Setup everything
            verify_channel, ticket_channel, giveaway_channel = await self.setup_all(interaction.guild)
            
            # Send verification embed
            await self.send_verification_message(verify_channel)
            
            # Send ticket message
            await self.send_ticket_message(ticket_channel)
            
            # Send giveaway message
            await self.send_giveaway_message(giveaway_channel)
            
            await interaction.followup.send("✅ All systems setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error during setup: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🔐 Verification", style=discord.ButtonStyle.primary, emoji="🔐")
    async def setup_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin who ran /setup can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        guild = interaction.guild
        
        try:
            category = discord.utils.get(guild.categories, name="📋 Server Management")
            if not category:
                category = await guild.create_category("📋 Server Management")
            
            verify_channel = discord.utils.get(guild.text_channels, name="🔐-verification")
            if not verify_channel:
                verify_channel = await guild.create_text_channel("🔐-verification", category=category)
            
            await self.send_verification_message(verify_channel)
            await interaction.followup.send("✅ Verification system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎫 Tickets", style=discord.ButtonStyle.secondary, emoji="🎫")
    async def setup_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin who ran /setup can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        guild = interaction.guild
        
        try:
            category = discord.utils.get(guild.categories, name="📋 Server Management")
            if not category:
                category = await guild.create_category("📋 Server Management")
            
            ticket_channel = discord.utils.get(guild.text_channels, name="🎫-tickets")
            if not ticket_channel:
                ticket_channel = await guild.create_text_channel("🎫-tickets", category=category)
            
            await self.send_ticket_message(ticket_channel)
            await interaction.followup.send("✅ Ticket system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎁 Giveaways", style=discord.ButtonStyle.primary, emoji="🎁")
    async def setup_giveaways(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin who ran /setup can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        guild = interaction.guild
        
        try:
            category = discord.utils.get(guild.categories, name="📋 Server Management")
            if not category:
                category = await guild.create_category("📋 Server Management")
            
            giveaway_channel = discord.utils.get(guild.text_channels, name="🎉-giveaways")
            if not giveaway_channel:
                giveaway_channel = await guild.create_text_channel("🎉-giveaways", category=category)
            
            await self.send_giveaway_message(giveaway_channel)
            await interaction.followup.send("✅ Giveaway system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="👑 Roles", style=discord.ButtonStyle.secondary, emoji="👑")
    async def setup_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin who ran /setup can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        guild = interaction.guild
        
        try:
            # Create roles if not exist
            await guild.create_role(name="✅ Verified", color=discord.Color.green())
            await guild.create_role(name="❌ Unverified", color=discord.Color.red())
            await guild.create_role(name="🛡️ Moderator", color=discord.Color.blue())
            await guild.create_role(name="👑 Admin", color=discord.Color.gold())
            await guild.create_role(name="🤝 Helper", color=discord.Color.purple())
            await guild.create_role(name="🎁 Giveaway", color=discord.Color.magenta())
            
            await interaction.followup.send("✅ Roles created successfully!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🛡️ Moderation", style=discord.ButtonStyle.danger, emoji="🛡️")
    async def setup_moderation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin who ran /setup can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        guild = interaction.guild
        
        try:
            category = discord.utils.get(guild.categories, name="📋 Server Management")
            if not category:
                category = await guild.create_category("📋 Server Management")
            
            mod_channel = discord.utils.get(guild.text_channels, name="🛡️-mod-logs")
            if not mod_channel:
                mod_channel = await guild.create_text_channel("🛡️-mod-logs", category=category)
            
            await interaction.followup.send("✅ Moderation system setup complete! Auto-moderation is now active.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    async def send_verification_message(self, channel):
        embed = discord.Embed(
            title="🔐 **VERIFICATION REQUIRED**",
            description="""
            **Why verify?**
            • 🛡️ **Security** - Keep your account safe
            • 🎮 **Access** - Unlock all server features
            • 👤 **Identity** - Verify your Discord identity
            • 🏆 **Benefits** - Get access to exclusive channels
            
            **How to verify:**
            1. Type `!verify` in chat
            2. Check your DMs for a code
            3. Type `!confirm <code>` to verify
            """,
            color=discord.Color.blue()
        )
        embed.set_footer(text="EDITH Authentication System v2.0")
        
        await channel.send(embed=embed)
    
    async def send_ticket_message(self, channel):
        embed = discord.Embed(
            title="🎫 **TICKET SYSTEM**",
            description="""
            **Need help? Create a ticket!**
            
            Select the type of support you need:
            • 🛠️ **Server Related** - Server issues, suggestions
            • 👮 **Contact Mods** - Report users, moderation issues
            • ❓ **Others** - General questions, feedback
            
            Click a button below to create your ticket!
            """,
            color=discord.Color.purple()
        )
        
        view = TicketView()
        await channel.send(embed=embed, view=view)
    
    async def send_giveaway_message(self, channel):
        embed = discord.Embed(
            title="🎉 **GIVEAWAYS**",
            description="""
            **Welcome to the Giveaway Center!**
            
            🎁 Host and participate in exciting giveaways!
            👑 Admin only: Use the button below to host
            ⏰ Winners are automatically selected
            
            *Join the fun and win amazing prizes!*
            """,
            color=discord.Color.gold()
        )
        
        view = GiveawayMainView()
        await channel.send(embed=embed, view=view)

# ============ VERIFICATION SYSTEM ============
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Verify Now!", style=discord.ButtonStyle.success, emoji="✅")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        # Generate verification code
        code = secrets.token_hex(4)
        verification_sessions[user_id] = {
            'code': code,
            'guild_id': guild_id,
            'username': str(interaction.user),
            'timestamp': datetime.now().isoformat()
        }
        
        embed = discord.Embed(
            title="🔐 **Verification Code**",
            description=f"""
            Your verification code is: `{code}`
            
            Please type: `!confirm {code}` to verify yourself.
            This code expires in 10 minutes.
            """,
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============ TICKET SYSTEM ============
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🛠️ Server Related", style=discord.ButtonStyle.primary, emoji="🛠️")
    async def server_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Server Related")
    
    @discord.ui.button(label="👮 Contact Mods", style=discord.ButtonStyle.danger, emoji="👮")
    async def mod_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Contact Mods")
    
    @discord.ui.button(label="❓ Others", style=discord.ButtonStyle.secondary, emoji="❓")
    async def other_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Others")
    
    async def create_ticket(self, interaction, ticket_type):
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild = interaction.guild
            category = discord.utils.get(guild.categories, name="📋 Server Management")
            
            if not category:
                category = await guild.create_category("📋 Server Management")
            
            ticket_name = f"ticket-{interaction.user.name}-{secrets.token_hex(3)}".lower()
            
            # Get mod role
            mod_role = discord.utils.get(guild.roles, name="🛡️ Moderator")
            admin_role = discord.utils.get(guild.roles, name="👑 Admin")
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            if admin_role:
                overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            channel = await guild.create_text_channel(ticket_name, category=category, overwrites=overwrites)
            
            # Send ticket embed
            embed = discord.Embed(
                title=f"🎫 Ticket: {ticket_type}",
                description=f"**Created by:** {interaction.user.mention}\n**Type:** {ticket_type}\n**Created at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                color=discord.Color.blue()
            )
            
            view = TicketControlView(interaction.user.id, channel.id)
            await channel.send(f"{interaction.user.mention} {mod_role.mention if mod_role else ''}", embed=embed, view=view)
            
            # Store in database
            ticket_data = {
                'channel_id': channel.id,
                'user_id': interaction.user.id,
                'type': ticket_type,
                'created_at': datetime.now().isoformat(),
                'status': 'open'
            }
            firebase.data['tickets'][str(channel.id)] = ticket_data
            firebase.save_data()
            
            await interaction.followup.send(f"✅ Ticket created! {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error creating ticket: {str(e)}", ephemeral=True)

class TicketControlView(View):
    def __init__(self, user_id, channel_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.channel_id = channel_id
    
    @discord.ui.button(label="➕ Add User", style=discord.ButtonStyle.success, emoji="➕")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Remove User", style=discord.ButtonStyle.danger, emoji="➖")
    async def remove_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⛔ Ban User", style=discord.ButtonStyle.danger, emoji="⛔")
    async def ban_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BanUserModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📄 Transcript", style=discord.ButtonStyle.secondary, emoji="📄")
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            channel = interaction.channel
            messages = []
            async for msg in channel.history(limit=100):
                messages.append(f"{msg.author}: {msg.content}")
            
            transcript = "\n".join(reversed(messages))
            import io
            file = discord.File(io.BytesIO(transcript.encode()), f"transcript-{channel.name}.txt")
            await interaction.followup.send(file=file, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You don't have permission to close this ticket!", ephemeral=True)
            return
        
        await interaction.response.defer()
        channel = interaction.channel
        await channel.send("🔒 Ticket is being closed...")
        
        # Update database
        if str(channel.id) in firebase.data['tickets']:
            firebase.data['tickets'][str(channel.id)]['status'] = 'closed'
            firebase.save_data()
        
        await asyncio.sleep(2)
        await channel.delete()
    
    @discord.ui.button(label="📝 Special Note", style=discord.ButtonStyle.primary, emoji="📝")
    async def special_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = NoteModal(self.channel_id)
        await interaction.response.send_modal(modal)

class AddUserModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="Add User to Ticket")
        self.channel_id = channel_id
        self.user_id_input = TextInput(label="User ID or Mention", placeholder="Enter user ID or @mention", required=True)
        self.add_item(self.user_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
            return
        
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await channel.set_permissions(user, read_messages=True, send_messages=True)
                await channel.send(f"✅ {user.mention} has been added to this ticket!")
                await interaction.response.send_message(f"✅ Added {user.mention} to ticket!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class RemoveUserModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="Remove User from Ticket")
        self.channel_id = channel_id
        self.user_id_input = TextInput(label="User ID or Mention", placeholder="Enter user ID or @mention", required=True)
        self.add_item(self.user_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
            return
        
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await channel.set_permissions(user, read_messages=False, send_messages=False)
                await channel.send(f"❌ {user.mention} has been removed from this ticket!")
                await interaction.response.send_message(f"✅ Removed {user.mention} from ticket!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class BanUserModal(Modal):
    def __init__(self):
        super().__init__(title="Ban User")
        self.user_id_input = TextInput(label="User ID", placeholder="Enter user ID", required=True)
        self.reason_input = TextInput(label="Reason", placeholder="Why ban this user?", required=False)
        self.add_item(self.user_id_input)
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_id_input.value)
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await user.ban(reason=self.reason_input.value or "Banned from ticket")
                await interaction.response.send_message(f"✅ Banned {user.mention}!", ephemeral=True)
                await interaction.channel.send(f"⛔ {user.mention} has been banned!")
        except:
            await interaction.response.send_message("❌ Failed to ban user!", ephemeral=True)

class NoteModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="Add Special Note")
        self.channel_id = channel_id
        self.note_input = TextInput(label="Note", placeholder="Enter your note here...", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.note_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Store note in user's profile under this guild
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        user_data = firebase.get_user(user_id, guild_id)
        if 'notes' not in user_data:
            user_data['notes'] = []
        
        user_data['notes'].append({
            'note': self.note_input.value,
            'ticket': str(self.channel_id),
            'moderator': str(interaction.user),
            'timestamp': datetime.now().isoformat()
        })
        
        firebase.set_user(user_id, guild_id, user_data)
        
        await interaction.response.send_message("✅ Note saved successfully!", ephemeral=True)

# ============ GIVEAWAY SYSTEM ============
class GiveawayMainView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎁 Host Giveaway", style=discord.ButtonStyle.success, emoji="🎁")
    async def host_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        
        modal = GiveawayModal()
        await interaction.response.send_modal(modal)

class GiveawayModal(Modal):
    def __init__(self):
        super().__init__(title="Host a Giveaway")
        self.name = TextInput(label="Giveaway Name", placeholder="Enter giveaway name", required=True)
        self.duration = TextInput(label="Duration (minutes)", placeholder="e.g., 60", required=True)
        self.winners = TextInput(label="Number of Winners", placeholder="e.g., 1", required=True)
        self.prize = TextInput(label="Prize", placeholder="What's the prize?", required=True)
        self.add_item(self.name)
        self.add_item(self.duration)
        self.add_item(self.winners)
        self.add_item(self.prize)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            duration_minutes = int(self.duration.value)
            winners_count = int(self.winners.value)
            end_time = datetime.now() + timedelta(minutes=duration_minutes)
            
            giveaway_id = secrets.token_hex(8)
            
            # Create giveaway embed
            embed = discord.Embed(
                title=f"🎉 **{self.name.value}**",
                description=f"""
                **Prize:** {self.prize.value}
                **Hosted by:** {interaction.user.mention}
                **Duration:** {duration_minutes} minutes
                **Winners:** {winners_count}
                **Ends at:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}
                
                Click the button below to participate!
                """,
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
            
            view = GiveawayParticipateView(giveaway_id, end_time, winners_count, interaction.user.id)
            msg = await interaction.response.send_message(embed=embed, view=view)
            
            # Store giveaway
            firebase.data['giveaways'][giveaway_id] = {
                'name': self.name.value,
                'prize': self.prize.value,
                'host': interaction.user.id,
                'duration': duration_minutes,
                'winners': winners_count,
                'end_time': end_time.isoformat(),
                'participants': [],
                'channel_id': interaction.channel.id,
                'message_id': None
            }
            firebase.save_data()
            
            # Start countdown
            asyncio.create_task(self.giveaway_countdown(giveaway_id, interaction.channel, end_time))
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers!", ephemeral=True)
    
    async def giveaway_countdown(self, giveaway_id, channel, end_time):
        await asyncio.sleep((end_time - datetime.now()).total_seconds())
        
        # Get giveaway data
        giveaway_data = firebase.data['giveaways'].get(giveaway_id)
        if not giveaway_data:
            return
        
        participants = giveaway_data.get('participants', [])
        if len(participants) < giveaway_data['winners']:
            await channel.send(f"❌ Not enough participants for giveaway **{giveaway_data['name']}**!")
            return
        
        # Select winners
        winners = random.sample(participants, min(giveaway_data['winners'], len(participants)))
        winner_mentions = [f"<@{winner}>" for winner in winners]
        
        embed = discord.Embed(
            title=f"🎉 **GIVEAWAY COMPLETE!**",
            description=f"""
            **Giveaway:** {giveaway_data['name']}
            **Prize:** {giveaway_data['prize']}
            **Host:** <@{giveaway_data['host']}>
            **Winners:** {', '.join(winner_mentions)}
            
            🎊 Congratulations to all winners!
            Please create a ticket within 24 hours to claim your prize!
            """,
            color=discord.Color.green()
        )
        
        # Get giveaway role
        giveaway_role = discord.utils.get(channel.guild.roles, name="🎁 Giveaway")
        role_mention = giveaway_role.mention if giveaway_role else "@everyone"
        
        await channel.send(f"{role_mention} <@{giveaway_data['host']}>")
        await channel.send(embed=embed)

class GiveawayParticipateView(View):
    def __init__(self, giveaway_id, end_time, winners_count, host_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.end_time = end_time
        self.winners_count = winners_count
        self.host_id = host_id
    
    @discord.ui.button(label="🎯 Participate", style=discord.ButtonStyle.success, emoji="🎯")
    async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway_data = firebase.data['giveaways'].get(self.giveaway_id)
        if not giveaway_data:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return
        
        if datetime.now() > datetime.fromisoformat(giveaway_data['end_time']):
            await interaction.response.send_message("❌ This giveaway has ended!", ephemeral=True)
            return
        
        if interaction.user.id in giveaway_data['participants']:
            await interaction.response.send_message("❌ You're already participating!", ephemeral=True)
            return
        
        giveaway_data['participants'].append(interaction.user.id)
        firebase.save_data()
        
        await interaction.response.send_message("✅ You're now participating!", ephemeral=True)
    
    @discord.ui.button(label="❌ Un-Participate", style=discord.ButtonStyle.danger, emoji="❌")
    async def unparticipate(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway_data = firebase.data['giveaways'].get(self.giveaway_id)
        if not giveaway_data:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return
        
        if interaction.user.id in giveaway_data['participants']:
            giveaway_data['participants'].remove(interaction.user.id)
            firebase.save_data()
            await interaction.response.send_message("✅ Removed from giveaway!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You're not participating!", ephemeral=True)
    
    @discord.ui.button(label="🗑️ Delete Giveaway", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        
        del firebase.data['giveaways'][self.giveaway_id]
        firebase.save_data()
        await interaction.response.send_message("✅ Giveaway deleted!", ephemeral=True)
        await interaction.message.delete()
    
    @discord.ui.button(label="🔄 Reroll", style=discord.ButtonStyle.primary, emoji="🔄")
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        
        giveaway_data = firebase.data['giveaways'].get(self.giveaway_id)
        if not giveaway_data:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return
        
        participants = giveaway_data.get('participants', [])
        if not participants:
            await interaction.response.send_message("❌ No participants to reroll!", ephemeral=True)
            return
        
        new_winner = random.choice(participants)
        await interaction.response.send_message(f"🔄 New winner: <@{new_winner}>!", ephemeral=True)

# ============ MODERATION EVENTS ============
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Auto-moderation: Bad words filter
    bad_words = ['badword1', 'badword2', 'badword3', 'fuck', 'shit', 'damn']  # Add your bad words
    if any(word in message.content.lower() for word in bad_words):
        try:
            await message.delete()
            warn_msg = await message.channel.send(f"{message.author.mention}, please watch your language! 🚫")
            await asyncio.sleep(5)
            await warn_msg.delete()
        except:
            pass
        return
    
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    # Assign unverified role
    unverified_role = discord.utils.get(member.guild.roles, name="❌ Unverified")
    if unverified_role:
        try:
            await member.add_roles(unverified_role)
        except:
            pass

# ============ COMMANDS ============
@bot.command(name='setup')
@commands.has_permissions(administrator=True)
async def setup_command(ctx):
    """Admin setup command"""
    view = SetupView(ctx.author)
    embed = discord.Embed(
        title="🤖 **EDITH - Ultimate Server Management Bot**",
        description="""
        **Welcome to EDITH!** 🌟
        
        Your all-in-one server management solution:
        
        ✅ **Verification System** - Secure OAuth2 verification
        ✅ **Moderation Suite** - Auto-moderation & logging
        ✅ **Ticket System** - Advanced support tickets
        ✅ **Role Management** - Automated role assignments
        ✅ **Giveaway System** - Host & manage giveaways
        
        **My Honor** 🏆
        *Built with ❤️ for your server*
        """,
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    await ctx.send(embed=embed, view=view)

@bot.command(name='verify')
async def verify_command(ctx):
    """Start verification process"""
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)
    
    # Generate a simple code
    code = secrets.token_hex(4)
    verification_sessions[user_id] = {
        'code': code,
        'guild_id': guild_id,
        'username': str(ctx.author),
        'timestamp': datetime.now().isoformat()
    }
    
    embed = discord.Embed(
        title="🔐 Verification Required",
        description=f"""
        Your verification code is: `{code}`
        
        Please type: `!confirm {code}` to verify yourself.
        This code expires in 10 minutes.
        """,
        color=discord.Color.blue()
    )
    
    try:
        await ctx.author.send(embed=embed)
        await ctx.send(f"{ctx.author.mention}, I've sent you a verification code in DMs!")
    except:
        await ctx.send(f"{ctx.author.mention}, please enable DMs or check your privacy settings!")

@bot.command(name='confirm')
async def confirm_verification(ctx, code: str = None):
    """Confirm verification with code"""
    if not code:
        await ctx.send("❌ Please provide the code! Usage: `!confirm <code>`")
        return
    
    user_id = str(ctx.author.id)
    session = verification_sessions.get(user_id)
    
    if not session:
        await ctx.send("❌ No verification request found. Use `!verify` first!")
        return
    
    if session['code'] != code:
        await ctx.send("❌ Invalid code! Please check and try again.")
        return
    
    # Check if expired (10 minutes)
    if (datetime.now() - datetime.fromisoformat(session['timestamp'])).seconds > 600:
        await ctx.send("❌ Code expired! Use `!verify` again.")
        del verification_sessions[user_id]
        return
    
    # Verify user
    guild_id = session['guild_id']
    guild = ctx.guild
    
    # Store in database
    user_data = firebase.get_user(user_id, guild_id)
    user_data['verified'] = True
    user_data['profile'] = {
        'username': str(ctx.author),
        'verified_at': datetime.now().isoformat(),
        'guild': guild.name,
        'guild_id': guild_id
    }
    firebase.set_user(user_id, guild_id, user_data)
    
    # Assign roles
    verified_role = discord.utils.get(guild.roles, name="✅ Verified")
    unverified_role = discord.utils.get(guild.roles, name="❌ Unverified")
    
    try:
        if verified_role:
            if unverified_role:
                await ctx.author.remove_roles(unverified_role)
            await ctx.author.add_roles(verified_role)
            await ctx.send(f"✅ {ctx.author.mention} has been verified! Welcome to {guild.name}! 🎉")
        else:
            await ctx.send("✅ Verification successful! (No verified role found)")
    except:
        await ctx.send("✅ Verification successful! (Could not assign role)")
    
    del verification_sessions[user_id]

@bot.command(name='ping')
async def ping(ctx):
    """Check bot latency"""
    await ctx.send(f"🏓 Pong! Latency: {round(bot.latency * 1000)}ms")

@bot.command(name='shutdown')
@commands.is_owner()
async def shutdown(ctx):
    """Shutdown the bot"""
    await ctx.send("🔴 Shutting down...")
    await bot.close()

@bot.command(name='help')
async def help_command(ctx):
    """Show all commands"""
    embed = discord.Embed(
        title="📚 **EDITH Bot Commands**",
        description="""
        **Admin Commands:**
        `!setup` - Setup all systems (Admin only)
        
        **User Commands:**
        `!verify` - Start verification process
        `!confirm <code>` - Complete verification
        `!ping` - Check bot latency
        `!help` - Show this message
        """,
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

# ============ RUN BOT ============
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ ERROR: DISCORD_TOKEN not found in environment variables!")
        print("Make sure you have a .env file with DISCORD_TOKEN=your_token")
        exit(1)
    
    # Start keep-alive thread for Railway
    if os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('WEBSITE_URL'):
        threading.Thread(target=keep_alive, daemon=True).start()
        print("🔄 Keep-alive thread started for Railway")
    
    print("""
    ╔════════════════════════════════════════╗
    ║         🚀 EDITH BOT STARTING          ║
    ╠════════════════════════════════════════╣
    ║    Ready for GitHub & Railway!         ║
    ╚════════════════════════════════════════╝
    """)
    
    bot.run(token)
