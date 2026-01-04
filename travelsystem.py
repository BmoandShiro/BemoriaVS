import interactions
from interactions import Extension, Embed, SlashContext, OptionType, slash_command, AutocompleteContext
import logging

class TravelSystem(Extension):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(
        name="travel_to",
        description="Travel to an accessible location",
        options=[
            {
                "name": "destination",
                "description": "The location you want to travel to",
                "type": OptionType.STRING,
                "required": True,
                "autocomplete": True,  # Enable autocomplete
            }
        ]
    )
    async def travel_to(self, ctx: SlashContext, destination: str):
        player_id = await self.get_player_id(ctx.author.id)
        if player_id is None:
            await ctx.send("Could not find your player data. Please ensure your data is correct.", ephemeral=True)
            return

        # Check if player is in a party
        party = await self.bot.db.fetchrow("""
            SELECT p.*, pm.role
            FROM parties p
            JOIN party_members pm ON p.party_id = pm.party_id
            WHERE pm.player_id = $1 AND p.is_active = true
        """, player_id)

        if party:
            # If player is party leader, move entire party
            if party['leader_id'] == player_id:
                await self.travel_party(ctx, player_id, destination, party['party_id'])
            else:
                # Non-leaders cannot travel solo
                await ctx.send(
                    "You are in a party! Only the party leader can initiate travel. "
                    "Ask your party leader to move the party, or leave the party to travel solo.",
                    ephemeral=True
                )
            return

        # Solo travel (no party)
        current_location_id = await self.get_current_location_id(player_id)
        if current_location_id is None:
            await ctx.send("Could not find your current location. Please try again later.", ephemeral=True)
            return

        accessible_locations = await self.get_connected_locations(current_location_id, player_id)
        destination_location = next((loc for loc in accessible_locations if loc['name'] == destination), None)

        if destination_location:
            await self.update_location(player_id, destination_location['locationid'])
            await ctx.send(f"You have successfully traveled to {destination}.")
        else:
            await ctx.send("The specified location is not accessible or you do not meet the conditions required to travel there.", ephemeral=True)

    @travel_to.autocomplete("destination")
    async def autocomplete(self, ctx: AutocompleteContext):
        player_id = await self.get_player_id(ctx.user.id)
        if player_id is None:
            await ctx.send(choices=[])
            return

        current_location_id = await self.get_current_location_id(player_id)
        accessible_locations = await self.get_connected_locations(current_location_id, player_id)
        matching_locations = [
            loc['name'] for loc in accessible_locations if ctx.input_text.lower() in loc['name'].lower()
        ]
        await ctx.send(choices=matching_locations)

    async def get_player_id(self, discord_id):
        return await self.bot.db.get_or_create_player(discord_id)

    async def get_current_location_id(self, player_id):
        async with self.bot.db.pool.acquire() as conn:
            query = "SELECT current_location FROM public.player_data WHERE playerid = $1"
            result = await conn.fetchrow(query, player_id)
            return result['current_location'] if result else None

    async def get_connected_locations(self, current_location_id, player_id):
        query = """
        SELECT l.locationid, l.name, l.description
        FROM locations l
        JOIN paths p ON p.from_location_id = $1 AND p.to_location_id = l.locationid
        JOIN player_data pd ON pd.playerid = $2
        LEFT JOIN inventory i ON i.playerid = pd.playerid AND i.itemid = l.required_item_id
        WHERE 
            (l.xp_requirement IS NULL OR pd.xp >= l.xp_requirement)
        AND (l.required_item_id IS NULL OR i.itemid IS NOT NULL)
        AND NOT EXISTS (
            SELECT 1
            FROM location_skill_requirements lsr
            LEFT JOIN player_skills_xp ps ON ps.playerid = pd.playerid
            WHERE lsr.locationid = l.locationid
            AND CASE 
                WHEN lsr.skill_id = 1 THEN ps.fire_magic_xp >= lsr.required_level
                WHEN lsr.skill_id = 2 THEN ps.water_magic_xp >= lsr.required_level
                WHEN lsr.skill_id = 3 THEN ps.earth_magic_xp >= lsr.required_level
                WHEN lsr.skill_id = 4 THEN ps.air_magic_xp >= lsr.required_level
                -- Add more conditions for other skill columns as needed
                ELSE FALSE
            END = FALSE
        )
        GROUP BY l.locationid, l.name, l.description;
        """
        async with self.bot.db.pool.acquire() as conn:
            results = await conn.fetch(query, current_location_id, player_id)
            return [{'locationid': row['locationid'], 'name': row['name'], 'description': row['description']} for row in results] if results else []

    async def update_location(self, player_id, location_id):
        async with self.bot.db.pool.acquire() as conn:
            query = "UPDATE public.player_data SET current_location = $1 WHERE playerid = $2"
            await conn.execute(query, location_id, player_id)

    async def travel_party(self, ctx: SlashContext, leader_id: int, destination: str, party_id: int):
        """Move entire party to a destination."""
        # Get leader's current location
        current_location_id = await self.get_current_location_id(leader_id)
        if current_location_id is None:
            await ctx.send("Could not find your current location. Please try again later.", ephemeral=True)
            return

        # Get accessible locations (using leader's requirements)
        accessible_locations = await self.get_connected_locations(current_location_id, leader_id)
        destination_location = next((loc for loc in accessible_locations if loc['name'] == destination), None)

        if not destination_location:
            await ctx.send("The specified location is not accessible or you do not meet the conditions required to travel there.", ephemeral=True)
            return

        # Get location details to check requirements
        location_details = await self.bot.db.fetchrow("""
            SELECT locationid, name, required_item_id, required_item_equipped
            FROM locations
            WHERE locationid = $1
        """, destination_location['locationid'])

        # Get all party members
        party_members = await self.bot.db.fetch("""
            SELECT pm.player_id, players.discord_id
            FROM party_members pm
            JOIN players ON pm.player_id = players.playerid
            WHERE pm.party_id = $1
        """, party_id)

        if not party_members:
            await ctx.send("Error: Could not find party members.", ephemeral=True)
            return

        # Check if location requires an equipped item - if so, verify all party members have it equipped
        if location_details and location_details['required_item_id'] and location_details.get('required_item_equipped'):
            item_name = await self.bot.db.fetchval("""
                SELECT name FROM items WHERE itemid = $1
            """, location_details['required_item_id'])
            
            missing_members = []
            for member in party_members:
                has_item_equipped = await self.bot.db.fetchval("""
                    SELECT COUNT(*) > 0
                    FROM inventory
                    WHERE playerid = $1 AND itemid = $2 AND isequipped = TRUE
                """, member['player_id'], location_details['required_item_id'])
                
                if not has_item_equipped:
                    try:
                        member_user = await self.bot.fetch_user(member['discord_id'])
                        member_name = member_user.display_name if member_user else f"Player {member['player_id']}"
                    except:
                        member_name = f"Player {member['player_id']}"
                    missing_members.append(member_name)
            
            if missing_members:
                member_list = ", ".join(missing_members)
                await ctx.send(
                    f"❌ Cannot travel to **{location_details['name']}**! All party members must have **{item_name}** equipped.\n\n"
                    f"Missing equipped item: {member_list}",
                    ephemeral=True
                )
                return

        # Update location for all party members
        location_name = destination_location['name']
        moved_count = 0
        
        for member in party_members:
            await self.update_location(member['player_id'], destination_location['locationid'])
            moved_count += 1
            
            # Notify each party member (except leader, who gets the main message)
            if member['player_id'] != leader_id:
                try:
                    member_user = await self.bot.fetch_user(member['discord_id'])
                    if member_user:
                        await member_user.send(f"🎯 Your party leader has moved the party to **{location_name}**!")
                except:
                    pass  # Silently fail if can't DM member

        # Send confirmation to leader
        await ctx.send(
            f"✅ Party successfully traveled to **{location_name}**! "
            f"All {moved_count} party member(s) have been moved.",
            ephemeral=True
        )

    async def display_locations(self, ctx, current_location_id):
        player_id = await self.get_player_id(ctx.author.id)
        accessible_locations = await self.get_connected_locations(current_location_id, player_id)
        
        if not accessible_locations:
            await ctx.send("No accessible locations found.", ephemeral=True)
            return

        description = "\n".join([f"**{loc['name']}**: {loc['description']}" for loc in accessible_locations])
        embed = Embed(
            title="Available Travel Destinations",
            description=description,
            color=0x00FF00
        )
        await ctx.send(embed=embed)

def setup(bot):
    TravelSystem(bot)
