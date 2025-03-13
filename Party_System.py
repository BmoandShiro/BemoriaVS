from interactions import (
    Extension, 
    SlashContext, 
    slash_command, 
    slash_option, 
    OptionType,
    Embed,
    ButtonStyle,
    Button,
    User,
    component_callback
)
import asyncio
from datetime import datetime, timedelta
import re

class PartySystem(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @slash_command(name="party", description="Party management commands")
    @slash_option(
        name="action",
        description="What party action to perform",
        required=True,
        opt_type=OptionType.STRING,
        choices=[
            {"name": "create", "value": "create"},
            {"name": "join", "value": "join"},
            {"name": "leave", "value": "leave"},
            {"name": "disband", "value": "disband"},
            {"name": "info", "value": "info"},
            {"name": "kick", "value": "kick"},
            {"name": "ready", "value": "ready"}
        ]
    )
    async def party_command(self, ctx: SlashContext, action: str):
        player_id = await self.db.get_or_create_player(ctx.author.id)
        
        if action == "create":
            await self.create_party(ctx, player_id)
        elif action == "join":
            await self.show_join_menu(ctx, player_id)
        elif action == "leave":
            await self.leave_party(ctx, player_id)
        elif action == "disband":
            await self.disband_party(ctx, player_id)
        elif action == "info":
            await self.show_party_info(ctx, player_id)
        elif action == "kick":
            await self.show_kick_menu(ctx, player_id)
        elif action == "ready":
            await self.toggle_ready_status(ctx, player_id)

    async def create_party(self, ctx: SlashContext, player_id: int):
        """Create a new party with the player as leader."""
        # Check if player is already in a party
        existing_party = await self.db.fetchrow("""
            SELECT p.* FROM parties p
            JOIN party_members pm ON p.party_id = pm.party_id
            WHERE pm.player_id = $1 AND p.is_active = true
        """, player_id)

        if existing_party:
            await ctx.send("You are already in a party!", ephemeral=True)
            return

        # Create new party
        party = await self.db.fetchrow("""
            INSERT INTO parties (leader_id, party_name, max_size, is_active)
            VALUES ($1, $2, 4, true)
            RETURNING *
        """, player_id, f"{ctx.author.display_name}'s Party")

        # Add player as leader
        await self.db.execute("""
            INSERT INTO party_members (party_id, player_id, role)
            VALUES ($1, $2, 'leader')
        """, party['party_id'], player_id)

        await ctx.send(f"Party '{party['party_name']}' created! You are the leader.", ephemeral=True)
        
        # Create updated party menu buttons
        party_info_button = Button(
            style=ButtonStyle.PRIMARY,
            label="Party Info",
            custom_id=f"party_info_{player_id}"
        )
        
        invite_button = Button(
            style=ButtonStyle.SUCCESS,
            label="Invite Player",
            custom_id=f"party_invite_{player_id}"
        )
        
        disband_button = Button(
            style=ButtonStyle.DANGER,
            label="Disband Party",
            custom_id=f"party_disband_{player_id}"
        )
        
        # Send updated menu
        await ctx.send(
            "Party Management:",
            components=[[party_info_button, invite_button, disband_button]],
            ephemeral=True
        )

    async def show_invite_menu(self, ctx: SlashContext, player_id: int):
        # Check if player is in a party
        party = await self.db.fetchrow("""
            SELECT p.* FROM parties p
            JOIN party_members pm ON p.party_id = pm.party_id
            WHERE pm.player_id = $1 AND p.is_active = true
        """, player_id)

        if not party:
            await ctx.send("You must be in a party to invite players!", ephemeral=True)
            return

        # Get current party size
        member_count = await self.db.fetchval("""
            SELECT COUNT(*) FROM party_members
            WHERE party_id = $1
        """, party['party_id'])

        if member_count >= party['max_size']:
            await ctx.send("Party is already full!", ephemeral=True)
            return

        # Create an embed with instructions
        embed = Embed(
            title="Invite Players to Party",
            description="To invite a player, use the command below and mention them:",
            color=0x00FF00
        )
        embed.add_field(
            name="Command Format",
            value="`/party_invite @PlayerName`",
            inline=False
        )
        embed.add_field(
            name="Example",
            value="Type: `/party_invite @John`\nThis will send an invite to John to join your party.",
            inline=False
        )
        embed.add_field(
            name="Current Party Size",
            value=f"{member_count}/{party['max_size']} members",
            inline=False
        )

        await ctx.send(embeds=[embed], ephemeral=True)

    async def show_join_menu(self, ctx: SlashContext, player_id: int):
        # Get pending invites for this player
        invites = await self.db.fetch("""
            SELECT pi.*, p.party_name, pd.username as inviter_name
            FROM party_invites pi
            JOIN parties p ON pi.party_id = p.party_id
            JOIN player_data pd ON pi.inviter_id = pd.playerid
            WHERE pi.invitee_id = $1 
            AND pi.status = 'pending'
            AND pi.expires_at > NOW()
        """, player_id)

        if not invites:
            await ctx.send("You have no pending party invites.", ephemeral=True)
            return

        # Create embed with invite list
        embed = Embed(title="Pending Party Invites", color=0x00FF00)
        for invite in invites:
            embed.add_field(
                name=invite['party_name'],
                value=f"Invited by: {invite['inviter_name']}\nExpires: <t:{int(invite['expires_at'].timestamp())}:R>",
                inline=False
            )

        # Add accept/decline buttons for each invite
        components = []
        for invite in invites:
            accept_button = Button(
                style=ButtonStyle.SUCCESS,
                label=f"Accept {invite['party_name']}",
                custom_id=f"party_accept_{invite['invite_id']}"
            )
            decline_button = Button(
                style=ButtonStyle.DANGER,
                label=f"Decline {invite['party_name']}",
                custom_id=f"party_decline_{invite['invite_id']}"
            )
            components.extend([accept_button, decline_button])

        await ctx.send(embeds=[embed], components=components, ephemeral=True)

    async def leave_party(self, ctx: SlashContext, player_id: int):
        # Get player's current party
        party = await self.db.fetchrow("""
            SELECT p.* FROM parties p
            JOIN party_members pm ON p.party_id = pm.party_id
            WHERE pm.player_id = $1 AND p.is_active = true
        """, player_id)

        if not party:
            await ctx.send("You are not in a party!", ephemeral=True)
            return

        if party['leader_id'] == player_id:
            # Leader leaving = disband party
            await self.disband_party(ctx, player_id)
            return

        # Remove player from party
        await self.db.execute("""
            DELETE FROM party_members
            WHERE party_id = $1 AND player_id = $2
        """, party['party_id'], player_id)

        await ctx.send("You have left the party.", ephemeral=True)

    async def disband_party(self, ctx: SlashContext, player_id: int):
        # Check if player is party leader
        party = await self.db.fetchrow("""
            SELECT p.* FROM parties p
            WHERE p.leader_id = $1 AND p.is_active = true
        """, player_id)

        if not party:
            await ctx.send("You must be a party leader to disband it!", ephemeral=True)
            return

        # Mark party as inactive and remove all members
        await self.db.execute("""
            UPDATE parties SET is_active = false
            WHERE party_id = $1
        """, party['party_id'])

        await self.db.execute("""
            DELETE FROM party_members
            WHERE party_id = $1
        """, party['party_id'])

        await ctx.send("Party has been disbanded.", ephemeral=True)

    async def show_party_info(self, ctx: SlashContext, player_id: int):
        # Get player's current party and its members
        party_info = await self.db.fetch("""
            SELECT 
                p.party_id,
                p.party_name,
                p.leader_id,
                pm.player_id,
                pm.role,
                pm.ready_status,
                players.discord_id
            FROM parties p
            JOIN party_members pm ON p.party_id = pm.party_id
            JOIN players ON pm.player_id = players.playerid
            WHERE p.party_id = (
                SELECT party_id FROM party_members 
                WHERE player_id = $1
            )
            AND p.is_active = true
        """, player_id)

        if not party_info:
            await ctx.send("You are not in a party!", ephemeral=True)
            return

        # Create embed with party information
        embed = Embed(
            title=party_info[0]['party_name'],
            color=0x00FF00
        )

        for member in party_info:
            # Get Discord member object to get their display name
            discord_member = ctx.guild.get_member(int(member['discord_id']))
            username = discord_member.display_name if discord_member else f"Player {member['player_id']}"
            
            status = "✅" if member['ready_status'] else "❌"
            leader_star = "👑 " if member['player_id'] == member['leader_id'] else ""
            embed.add_field(
                name=f"{leader_star}{username} ({member['role']})",
                value=f"Ready: {status}",
                inline=True
            )

        await ctx.send(embeds=[embed], ephemeral=True)

    async def show_kick_menu(self, ctx: SlashContext, player_id: int):
        # Check if player is party leader
        party = await self.db.fetchrow("""
            SELECT p.* FROM parties p
            WHERE p.leader_id = $1 AND p.is_active = true
        """, player_id)

        if not party:
            await ctx.send("You must be a party leader to kick members!", ephemeral=True)
            return

        # Get party members
        members = await self.db.fetch("""
            SELECT pm.player_id, pd.username
            FROM party_members pm
            JOIN player_data pd ON pm.player_id = pd.playerid
            WHERE pm.party_id = $1 AND pm.player_id != $2
        """, party['party_id'], player_id)

        if not members:
            await ctx.send("No other members in the party to kick!", ephemeral=True)
            return

        # Create kick buttons for each member
        components = []
        for member in members:
            kick_button = Button(
                style=ButtonStyle.DANGER,
                label=f"Kick {member['username']}",
                custom_id=f"party_kick_{member['player_id']}"
            )
            components.append(kick_button)

        await ctx.send("Select a member to kick:", components=components, ephemeral=True)

    async def toggle_ready_status(self, ctx: SlashContext, player_id: int):
        # Toggle ready status for the player
        result = await self.db.fetchrow("""
            UPDATE party_members
            SET ready_status = NOT ready_status
            WHERE player_id = $1
            AND party_id = (
                SELECT party_id FROM party_members 
                WHERE player_id = $1
            )
            RETURNING ready_status
        """, player_id)

        if not result:
            await ctx.send("You are not in a party!", ephemeral=True)
            return

        status = "ready" if result['ready_status'] else "not ready"
        await ctx.send(f"You are now {status}.", ephemeral=True)

        # Check if all party members are ready
        all_ready = await self.db.fetchval("""
            SELECT BOOL_AND(ready_status)
            FROM party_members
            WHERE party_id = (
                SELECT party_id FROM party_members 
                WHERE player_id = $1
            )
        """, player_id)

        if all_ready:
            await ctx.send("All party members are ready! You can now start a battle.", ephemeral=True)

    async def get_player_party_info(self, player_id: int):
        """Get party information for a player."""
        # Get the player's current party and role
        party_info = await self.db.fetchrow("""
            SELECT p.*, pm.role
            FROM parties p
            JOIN party_members pm ON p.party_id = pm.party_id
            WHERE pm.player_id = $1 AND p.is_active = true
        """, player_id)

        return dict(party_info) if party_info else None

    @slash_command(name="party_invite", description="Invite a player to your party")
    @slash_option(
        name="player",
        description="The player to invite",
        required=True,
        opt_type=OptionType.USER
    )
    async def invite_command(self, ctx: SlashContext, player: User):
        inviter_id = await self.db.get_or_create_player(ctx.author.id)
        invitee_id = await self.db.get_or_create_player(player.id)

        # Check if inviter is in a party and is the leader
        party = await self.db.fetchrow("""
            SELECT p.* FROM parties p
            WHERE p.leader_id = $1 AND p.is_active = true
        """, inviter_id)

        if not party:
            await ctx.send("You must be a party leader to invite players!", ephemeral=True)
            return

        # Check if party is full
        member_count = await self.db.fetchval("""
            SELECT COUNT(*) FROM party_members
            WHERE party_id = $1
        """, party['party_id'])

        if member_count >= party['max_size']:
            await ctx.send("Party is already full!", ephemeral=True)
            return

        # Check if invitee is already in a party
        existing_party = await self.db.fetchrow("""
            SELECT p.* FROM parties p
            JOIN party_members pm ON p.party_id = pm.party_id
            WHERE pm.player_id = $1 AND p.is_active = true
        """, invitee_id)

        if existing_party:
            await ctx.send("That player is already in a party!", ephemeral=True)
            return

        # Create invite
        await self.db.execute("""
            INSERT INTO party_invites (party_id, inviter_id, invitee_id)
            VALUES ($1, $2, $3)
        """, party['party_id'], inviter_id, invitee_id)

        # Create accept/decline buttons
        accept_button = Button(
            style=ButtonStyle.SUCCESS,
            label="Accept",
            custom_id=f"party_accept_{party['party_id']}"
        )
        decline_button = Button(
            style=ButtonStyle.DANGER,
            label="Decline",
            custom_id=f"party_decline_{party['party_id']}"
        )

        # Send invite message to invitee
        await ctx.send(f"Invited {player.mention} to join your party!", ephemeral=True)
        await player.send(
            f"{ctx.author.mention} has invited you to join their party!",
            components=[[accept_button, decline_button]]
        )

    @component_callback(re.compile(r"^party_accept_\d+$"))
    async def handle_party_accept(self, ctx):
        party_id = int(ctx.custom_id.split("_")[2])
        player_id = await self.db.get_or_create_player(ctx.author.id)

        # Check if invite is still valid
        invite = await self.db.fetchrow("""
            SELECT * FROM party_invites
            WHERE party_id = $1 AND invitee_id = $2
            AND status = 'pending' AND expires_at > NOW()
        """, party_id, player_id)

        if not invite:
            await ctx.send("This invite has expired or is no longer valid.", ephemeral=True)
            return

        # Check if party is still active and has space
        party = await self.db.fetchrow("""
            SELECT p.*, COUNT(pm.player_id) as member_count
            FROM parties p
            LEFT JOIN party_members pm ON p.party_id = pm.party_id
            WHERE p.party_id = $1 AND p.is_active = true
            GROUP BY p.party_id
        """, party_id)

        if not party:
            await ctx.send("This party no longer exists.", ephemeral=True)
            return

        if party['member_count'] >= party['max_size']:
            await ctx.send("This party is now full.", ephemeral=True)
            return

        # Add player to party
        await self.db.execute("""
            INSERT INTO party_members (party_id, player_id)
            VALUES ($1, $2)
        """, party_id, player_id)

        # Update invite status
        await self.db.execute("""
            UPDATE party_invites
            SET status = 'accepted'
            WHERE party_id = $1 AND invitee_id = $2
        """, party_id, player_id)

        await ctx.send("You have joined the party!", ephemeral=True)

    @component_callback(re.compile(r"^party_decline_\d+$"))
    async def handle_party_decline(self, ctx):
        party_id = int(ctx.custom_id.split("_")[2])
        player_id = await self.db.get_or_create_player(ctx.author.id)

        # Update invite status
        await self.db.execute("""
            UPDATE party_invites
            SET status = 'declined'
            WHERE party_id = $1 AND invitee_id = $2
        """, party_id, player_id)

        await ctx.send("You have declined the party invite.", ephemeral=True)

    @component_callback(re.compile(r"^party_kick_\d+$"))
    async def handle_party_kick(self, ctx):
        target_id = int(ctx.custom_id.split("_")[2])
        kicker_id = await self.db.get_or_create_player(ctx.author.id)

        # Check if kicker is party leader
        party = await self.db.fetchrow("""
            SELECT p.* FROM parties p
            WHERE p.leader_id = $1 AND p.is_active = true
        """, kicker_id)

        if not party:
            await ctx.send("You must be a party leader to kick members!", ephemeral=True)
            return

        # Remove player from party
        await self.db.execute("""
            DELETE FROM party_members
            WHERE party_id = $1 AND player_id = $2
        """, party['party_id'], target_id)

        # Get kicked player's username
        kicked_player = await self.db.fetchrow("""
            SELECT username FROM player_data WHERE playerid = $1
        """, target_id)

        await ctx.send(f"Kicked {kicked_player['username']} from the party.", ephemeral=True)

    @component_callback(re.compile(r"^party_info_\d+$"))
    async def handle_party_info_button(self, ctx):
        player_id = int(ctx.custom_id.split("_")[2])
        await self.show_party_info(ctx, player_id)

    @component_callback(re.compile(r"^party_disband_\d+$"))
    async def handle_party_disband_button(self, ctx):
        player_id = int(ctx.custom_id.split("_")[2])
        
        # Verify the user's identity
        discord_id = await self.db.get_discord_id(player_id)
        if ctx.author.id != discord_id:
            await ctx.send("You are not authorized to disband this party.", ephemeral=True)
            return
            
        await self.disband_party(ctx, player_id)

    @component_callback(re.compile(r"^party_create_\d+$"))
    async def handle_party_create_button(self, ctx):
        player_id = int(ctx.custom_id.split("_")[2])
        
        # Verify the user's identity
        discord_id = await self.db.get_discord_id(player_id)
        if ctx.author.id != discord_id:
            await ctx.send("You are not authorized to create a party.", ephemeral=True)
            return
            
        await self.create_party(ctx, player_id)

    @component_callback(re.compile(r"^party_invite_\d+$"))
    async def handle_party_invite_button(self, ctx):
        player_id = int(ctx.custom_id.split("_")[2])
        
        # Verify the user's identity
        discord_id = await self.db.get_discord_id(player_id)
        if ctx.author.id != discord_id:
            await ctx.send("You are not authorized to invite players.", ephemeral=True)
            return
            
        await self.show_invite_menu(ctx, player_id)

def setup(bot):
    """Setup function to add the extension to the bot."""
    return PartySystem(bot) 