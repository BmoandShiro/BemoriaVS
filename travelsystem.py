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
        JOIN player_data pd ON pd.playerid = $2
        LEFT JOIN inventory i ON i.playerid = pd.playerid AND i.itemid = l.required_item_id
        WHERE (l.parentlocationid = $1 OR l.locationid = $1)
        AND (l.xp_requirement IS NULL OR pd.xp >= l.xp_requirement)
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
