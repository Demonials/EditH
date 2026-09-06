import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
import json
import secrets
import asyncio
import random
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Initialize bot with slash commands
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Simple database for Railway
class SimpleDB:
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
        return self.data['guilds'].get(guild_id)
    
    def set_guild(self, guild_id, data):
        guild_id = str(guild_id)
        self.data['guilds'][guild_id] = data
        self.save_data()

db = SimpleDB()

# Verification storage
verification_sessions = {}

# ============ SETUP VIEW ============
class SetupView(View):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
    
    async def setup_all(self, guild):
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
        roles_to_create = [
            ("✅ Verified", discord.Color.green()),
            ("❌ Unverified", discord.Color.red()),
            ("🛡️ Moderator", discord.Color.blue()),
            ("👑 Admin", discord.Color.gold()),
            ("🤝 Helper", discord.Color.purple()),
            ("🎁 Giveaway", discord.Color.magenta())
        ]
        
        created_roles = {}
        for role_name, color in roles_to_create:
            try:
                role = await guild.create_role(name=role_name, color=color)
                created_roles[role_name] = role.id
            except:
                role = discord.utils.get(guild.roles, name=role_name)
                if role:
                    created_roles[role_name] = role.id
        
        # Store in database
        guild_data = {
            'category_id': category.id,
            'channels': {
                'verify': verify_channel.id,
                'tickets': ticket_channel.id,
                'giveaways': giveaway_channel.id,
                'mod_logs': mod_channel.id
            },
            'roles': created_roles
        }
        db.set_guild(guild.id, guild_data)
        
        return verify_channel, ticket_channel, giveaway_channel
    
    @discord.ui.button(label="⚡ Setup All", style=discord.ButtonStyle.success, emoji="⚡")
    async def setup_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        try:
            verify_channel, ticket_channel, giveaway_channel = await self.setup_all(interaction.guild)
            await self.send_verification_message(verify_channel)
            await self.send_ticket_message(ticket_channel)
            await self.send_giveaway_message(giveaway_channel)
            await interaction.followup.send("✅ All systems setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🔐 Verification", style=discord.ButtonStyle.primary, emoji="🔐")
    async def setup_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            category = discord.utils.get(interaction.guild.categories, name="📋 Server Management")
            if not category:
                category = await interaction.guild.create_category("📋 Server Management")
            verify_channel = discord.utils.get(interaction.guild.text_channels, name="🔐-verification")
            if not verify_channel:
                verify_channel = await interaction.guild.create_text_channel("🔐-verification", category=category)
            await self.send_verification_message(verify_channel)
            await interaction.followup.send("✅ Verification system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎫 Tickets", style=discord.ButtonStyle.secondary, emoji="🎫")
    async def setup_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            category = discord.utils.get(interaction.guild.categories, name="📋 Server Management")
            if not category:
                category = await interaction.guild.create_category("📋 Server Management")
            ticket_channel = discord.utils.get(interaction.guild.text_channels, name="🎫-tickets")
            if not ticket_channel:
                ticket_channel = await interaction.guild.create_text_channel("🎫-tickets", category=category)
            await self.send_ticket_message(ticket_channel)
            await interaction.followup.send("✅ Ticket system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎁 Giveaways", style=discord.ButtonStyle.primary, emoji="🎁")
    async def setup_giveaways(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            category = discord.utils.get(interaction.guild.categories, name="📋 Server Management")
            if not category:
                category = await interaction.guild.create_category("📋 Server Management")
            giveaway_channel = discord.utils.get(interaction.guild.text_channels, name="🎉-giveaways")
            if not giveaway_channel:
                giveaway_channel = await interaction.guild.create_text_channel("🎉-giveaways", category=category)
            await self.send_giveaway_message(giveaway_channel)
            await interaction.followup.send("✅ Giveaway system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="👑 Roles", style=discord.ButtonStyle.secondary, emoji="👑")
    async def setup_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            roles = [
                ("✅ Verified", discord.Color.green()),
                ("❌ Unverified", discord.Color.red()),
                ("🛡️ Moderator", discord.Color.blue()),
                ("👑 Admin", discord.Color.gold()),
                ("🤝 Helper", discord.Color.purple()),
                ("🎁 Giveaway", discord.Color.magenta())
            ]
            for role_name, color in roles:
                try:
                    await interaction.guild.create_role(name=role_name, color=color)
                except:
                    pass
            await interaction.followup.send("✅ Roles created successfully!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🛡️ Moderation", style=discord.ButtonStyle.danger, emoji="🛡️")
    async def setup_moderation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            category = discord.utils.get(interaction.guild.categories, name="📋 Server Management")
            if not category:
                category = await interaction.guild.create_category("📋 Server Management")
            mod_channel = discord.utils.get(interaction.guild.text_channels, name="🛡️-mod-logs")
            if not mod_channel:
                mod_channel = await interaction.guild.create_text_channel("🛡️-mod-logs", category=category)
            await interaction.followup.send("✅ Moderation system setup complete!", ephemeral=True)
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
            
            **How to verify:**
            Click the **Verify** button below!
            """,
            color=discord.Color.blue()
        )
        view = VerifyView()
        await channel.send(embed=embed, view=view)
    
    async def send_ticket_message(self, channel):
        embed = discord.Embed(
            title="🎫 **TICKET SYSTEM**",
            description="Select the type of support you need:",
            color=discord.Color.purple()
        )
        view = TicketView()
        await channel.send(embed=embed, view=view)
    
    async def send_giveaway_message(self, channel):
        embed = discord.Embed(
            title="🎉 **GIVEAWAYS**",
            description="Host and participate in exciting giveaways!",
            color=discord.Color.gold()
        )
        view = GiveawayMainView()
        await channel.send(embed=embed, view=view)

# ============ VERIFICATION SYSTEM ============
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✅ Verify Now!", style=discord.ButtonStyle.success, emoji="✅")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        code = secrets.token_hex(4)
        verification_sessions[user_id] = {
            'code': code,
            'guild_id': str(interaction.guild.id),
            'username': str(interaction.user),
            'timestamp': datetime.now().isoformat()
        }
        
        embed = discord.Embed(
            title="🔐 Verification Code",
            description=f"Your code: `{code}`\nType `/confirm {code}` to verify",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============ SLASH COMMANDS ============
@bot.tree.command(name="setup", description="Setup all systems (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    """Admin setup command"""
    view = SetupView(interaction.user)
    embed = discord.Embed(
        title="🤖 **EDITH - Ultimate Server Management Bot**",
        description="""
        **Welcome to EDITH!** 🌟
        
        Your all-in-one server management solution:
        
        ✅ **Verification System** - Secure verification
        ✅ **Moderation Suite** - Auto-moderation & logging
        ✅ **Ticket System** - Advanced support tickets
        ✅ **Role Management** - Automated role assignments
        ✅ **Giveaway System** - Host & manage giveaways
        
        **My Honor** 🏆
        *Built with ❤️ for your server*
        """,
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="verify", description="Start verification process")
async def slash_verify(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    code = secrets.token_hex(4)
    verification_sessions[user_id] = {
        'code': code,
        'guild_id': str(interaction.guild.id),
        'username': str(interaction.user),
        'timestamp': datetime.now().isoformat()
    }
    
    embed = discord.Embed(
        title="🔐 Verification Required",
        description=f"Your verification code is: `{code}`\nType: `/confirm {code}`",
        color=discord.Color.blue()
    )
    try:
        await interaction.user.send(embed=embed)
        await interaction.response.send_message(f"{interaction.user.mention}, check your DMs!", ephemeral=True)
    except:
        await interaction.response.send_message(f"{interaction.user.mention}, please enable DMs!", ephemeral=True)

@bot.tree.command(name="confirm", description="Complete verification with code")
async def slash_confirm(interaction: discord.Interaction, code: str):
    user_id = str(interaction.user.id)
    session = verification_sessions.get(user_id)
    
    if not session:
        await interaction.response.send_message("❌ Use `/verify` first!", ephemeral=True)
        return
    
    if session['code'] != code:
        await interaction.response.send_message("❌ Invalid code!", ephemeral=True)
        return
    
    if (datetime.now() - datetime.fromisoformat(session['timestamp'])).seconds > 600:
        await interaction.response.send_message("❌ Code expired! Use `/verify` again.", ephemeral=True)
        del verification_sessions[user_id]
        return
    
    # Verify user
    guild = interaction.guild
    user_data = db.get_user(user_id, str(guild.id))
    user_data['verified'] = True
    user_data['profile'] = {
        'username': str(interaction.user),
        'verified_at': datetime.now().isoformat(),
        'guild': guild.name
    }
    db.set_user(user_id, str(guild.id), user_data)
    
    # Assign roles
    verified_role = discord.utils.get(guild.roles, name="✅ Verified")
    unverified_role = discord.utils.get(guild.roles, name="❌ Unverified")
    
    if verified_role:
        if unverified_role:
            await interaction.user.remove_roles(unverified_role)
        await interaction.user.add_roles(verified_role)
        await interaction.response.send_message(f"✅ {interaction.user.mention} is now verified! 🎉")
    else:
        await interaction.response.send_message("✅ Verification successful!")
    
    del verification_sessions[user_id]

@bot.tree.command(name="ping", description="Check bot latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! {round(interaction.client.latency * 1000)}ms")

@bot.tree.command(name="shutdown", description="Shutdown the bot (Owner only)")
async def slash_shutdown(interaction: discord.Interaction):
    if interaction.user.id != bot.owner_id:
        await interaction.response.send_message("❌ Only the bot owner can use this!", ephemeral=True)
        return
    await interaction.response.send_message("🔴 Shutting down...")
    await bot.close()

# ============ TICKET SYSTEM ============
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🛠️ Server Related", style=discord.ButtonStyle.primary)
    async def server_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Server Related")
    
    @discord.ui.button(label="👮 Contact Mods", style=discord.ButtonStyle.danger)
    async def mod_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Contact Mods")
    
    @discord.ui.button(label="❓ Others", style=discord.ButtonStyle.secondary)
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
            
            embed = discord.Embed(
                title=f"🎫 Ticket: {ticket_type}",
                description=f"Created by: {interaction.user.mention}\nType: {ticket_type}\nCreated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                color=discord.Color.blue()
            )
            
            view = TicketControlView(interaction.user.id, channel.id)
            await channel.send(embed=embed, view=view)
            
            db.data['tickets'][str(channel.id)] = {
                'channel_id': channel.id,
                'user_id': interaction.user.id,
                'type': ticket_type,
                'created_at': datetime.now().isoformat(),
                'status': 'open'
            }
            db.save_data()
            
            await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

class TicketControlView(View):
    def __init__(self, user_id, channel_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.channel_id = channel_id
    
    @discord.ui.button(label="➕ Add User", style=discord.ButtonStyle.success)
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Remove User", style=discord.ButtonStyle.danger)
    async def remove_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⛔ Ban User", style=discord.ButtonStyle.danger)
    async def ban_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BanUserModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📄 Transcript", style=discord.ButtonStyle.secondary)
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
    
    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger)
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No permission!", ephemeral=True)
            return
        
        await interaction.response.defer()
        channel = interaction.channel
        await channel.send("🔒 Closing ticket...")
        db.data['tickets'][str(channel.id)]['status'] = 'closed'
        db.save_data()
        await asyncio.sleep(2)
        await channel.delete()
    
    @discord.ui.button(label="📝 Special Note", style=discord.ButtonStyle.primary)
    async def special_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = NoteModal(self.channel_id)
        await interaction.response.send_modal(modal)

class AddUserModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="Add User")
        self.channel_id = channel_id
        self.user_id_input = TextInput(label="User ID or Mention", required=True)
        self.add_item(self.user_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await channel.set_permissions(user, read_messages=True, send_messages=True)
                await channel.send(f"✅ {user.mention} added to ticket!")
                await interaction.response.send_message("✅ User added!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class RemoveUserModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="Remove User")
        self.channel_id = channel_id
        self.user_id_input = TextInput(label="User ID or Mention", required=True)
        self.add_item(self.user_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await channel.set_permissions(user, read_messages=False, send_messages=False)
                await channel.send(f"❌ {user.mention} removed from ticket!")
                await interaction.response.send_message("✅ User removed!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class BanUserModal(Modal):
    def __init__(self):
        super().__init__(title="Ban User")
        self.user_id_input = TextInput(label="User ID", required=True)
        self.reason_input = TextInput(label="Reason", required=False)
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
        self.note_input = TextInput(label="Note", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.note_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        user_data = db.get_user(user_id, guild_id)
        if 'notes' not in user_data:
            user_data['notes'] = []
        user_data['notes'].append({
            'note': self.note_input.value,
            'ticket': str(self.channel_id),
            'moderator': str(interaction.user),
            'timestamp': datetime.now().isoformat()
        })
        db.set_user(user_id, guild_id, user_data)
        await interaction.response.send_message("✅ Note saved!", ephemeral=True)

# ============ GIVEAWAY SYSTEM ============
class GiveawayMainView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎁 Host Giveaway", style=discord.ButtonStyle.success)
    async def host_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        modal = GiveawayModal()
        await interaction.response.send_modal(modal)

class GiveawayModal(Modal):
    def __init__(self):
        super().__init__(title="Host Giveaway")
        self.name = TextInput(label="Giveaway Name", required=True)
        self.duration = TextInput(label="Duration (minutes)", required=True)
        self.winners = TextInput(label="Number of Winners", required=True)
        self.prize = TextInput(label="Prize", required=True)
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
            
            embed = discord.Embed(
                title=f"🎉 {self.name.value}",
                description=f"""
                **Prize:** {self.prize.value}
                **Host:** {interaction.user.mention}
                **Duration:** {duration_minutes} minutes
                **Winners:** {winners_count}
                **Ends:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}
                """,
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
            
            view = GiveawayParticipateView(giveaway_id, end_time, winners_count, interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view)
            
            db.data['giveaways'][giveaway_id] = {
                'name': self.name.value,
                'prize': self.prize.value,
                'host': interaction.user.id,
                'winners': winners_count,
                'end_time': end_time.isoformat(),
                'participants': []
            }
            db.save_data()
            
            asyncio.create_task(self.giveaway_countdown(giveaway_id, interaction.channel, end_time))
        except ValueError:
            await interaction.response.send_message("❌ Invalid numbers!", ephemeral=True)
    
    async def giveaway_countdown(self, giveaway_id, channel, end_time):
        await asyncio.sleep((end_time - datetime.now()).total_seconds())
        giveaway_data = db.data['giveaways'].get(giveaway_id)
        if not giveaway_data:
            return
        
        participants = giveaway_data.get('participants', [])
        if len(participants) < giveaway_data['winners']:
            await channel.send(f"❌ Not enough participants for **{giveaway_data['name']}**!")
            return
        
        winners = random.sample(participants, min(giveaway_data['winners'], len(participants)))
        winner_mentions = [f"<@{winner}>" for winner in winners]
        
        embed = discord.Embed(
            title="🎉 GIVEAWAY COMPLETE!",
            description=f"""
            **Giveaway:** {giveaway_data['name']}
            **Prize:** {giveaway_data['prize']}
            **Winners:** {', '.join(winner_mentions)}
            
            🎊 Congratulations! Create a ticket within 24 hours to claim!
            """,
            color=discord.Color.green()
        )
        
        giveaway_role = discord.utils.get(channel.guild.roles, name="🎁 Giveaway")
        host = giveaway_data['host']
        
        await channel.send(f"{giveaway_role.mention if giveaway_role else '@everyone'} <@{host}>")
        await channel.send(embed=embed)

class GiveawayParticipateView(View):
    def __init__(self, giveaway_id, end_time, winners_count, host_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.end_time = end_time
        self.host_id = host_id
    
    @discord.ui.button(label="🎯 Participate", style=discord.ButtonStyle.success)
    async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if not giveaway_data:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return
        if datetime.now() > datetime.fromisoformat(giveaway_data['end_time']):
            await interaction.response.send_message("❌ Giveaway ended!", ephemeral=True)
            return
        if interaction.user.id in giveaway_data['participants']:
            await interaction.response.send_message("❌ Already participating!", ephemeral=True)
            return
        
        giveaway_data['participants'].append(interaction.user.id)
        db.save_data()
        await interaction.response.send_message("✅ You're participating!", ephemeral=True)
    
    @discord.ui.button(label="❌ Un-Participate", style=discord.ButtonStyle.danger)
    async def unparticipate(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if giveaway_data and interaction.user.id in giveaway_data['participants']:
            giveaway_data['participants'].remove(interaction.user.id)
            db.save_data()
            await interaction.response.send_message("✅ Removed from giveaway!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not participating!", ephemeral=True)
    
    @discord.ui.button(label="🗑️ Delete Giveaway", style=discord.ButtonStyle.danger)
    async def delete_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        del db.data['giveaways'][self.giveaway_id]
        db.save_data()
        await interaction.response.send_message("✅ Giveaway deleted!", ephemeral=True)
        await interaction.message.delete()
    
    @discord.ui.button(label="🔄 Reroll", style=discord.ButtonStyle.primary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if giveaway_data and giveaway_data['participants']:
            new_winner = random.choice(giveaway_data['participants'])
            await interaction.response.send_message(f"🔄 New winner: <@{new_winner}>!", ephemeral=True)

# ============ MODERATION ============
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Bad word filter
    bad_words = ['badword1', 'badword2', 'badword3', 'fuck', 'shit', 'damn']
    if any(word in message.content.lower() for word in bad_words):
        try:
            await message.delete()
            warn = await message.channel.send(f"{message.author.mention}, watch your language! 🚫")
            await asyncio.sleep(5)
            await warn.delete()
        except:
            pass
        return
    
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    unverified_role = discord.utils.get(member.guild.roles, name="❌ Unverified")
    if unverified_role:
        try:
            await member.add_roles(unverified_role)
        except:
            pass

@bot.event
async def on_ready():
    print(f"""
    ╔════════════════════════════════════════╗
    ║         🚀 EDITH BOT ONLINE            ║
    ╠════════════════════════════════════════╣
    ║ Name: {bot.user.name}                  ║
    ║ ID: {bot.user.id}                      ║
    ║ Slash Commands: Syncing...             ║
    ╚════════════════════════════════════════╝
    """)
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands!")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

# ============ RUN ============
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ No DISCORD_TOKEN found!")
        exit(1)
    print("🚀 Starting EDITH Bot with slash commands...")
    bot.run(token)
