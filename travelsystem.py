import interactions
from interactions import Extension, Embed, SlashContext, OptionType, slash_command

class TravelSystem(Extension):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(
        name="change_location",
        description="Travel to an accessible location",
        options=[
            {
                "name": "destination",
                "description": "The location you want to travel to",
                "type": OptionType.STRING,
                "required": True,
                "autocomplete": True,
            }
        ]
    )
    async def change_location(self, ctx: SlashContext, destination: str):
        current_location_id = await self.get_current_location_id(ctx.author.id)
        accessible_locations = await self.get_accessible_locations(current_location_id)

        if destination in [loc['name'] for loc in accessible_locations]:
            if await self.check_conditions(ctx.author.id, destination):
                await self.update_location(ctx.author.id, destination)
                await ctx.send(f"You have successfully traveled to {destination}.")
            else:
                await ctx.send("You do not meet the conditions required to travel to this location.", ephemeral=True)
        else:
            await ctx.send("The specified location is not accessible.", ephemeral=True)

    @change_location.autocomplete("destination")
    async def autocomplete(self, ctx: SlashContext, query: str):
        current_location_id = await self.get_current_location_id(ctx.author.id)
        accessible_locations = await self.get_accessible_locations(current_location_id)

        matching_locations = [
            loc['name'] for loc in accessible_locations if query.lower() in loc['name'].lower()
        ]
        await ctx.send(choices=matching_locations)

    async def get_current_location_id(self, user_id):
        async with self.bot.db.pool.acquire() as conn:
            query = "SELECT current_location FROM public.players WHERE userid = $1"
            result = await conn.fetchrow(query, user_id)
            return result['current_location']

    async def get_accessible_locations(self, current_location_id):
        async with self.bot.db.pool.acquire() as conn:
            query = """
            SELECT l2.locationid, l2.name
            FROM public.locations l1
            JOIN public.locations l2 ON l1.parentlocationid = l2.locationid OR l2.parentlocationid = l1.locationid
            WHERE l1.locationid = $1
            """
            results = await conn.fetch(query, current_location_id)
            return results

    async def check_conditions(self, user_id, destination):
        # Implement the logic to check if the player meets the conditions for traveling to the destination
        # For example, check if the player has the required item or stats
        return True  # Placeholder, replace with actual condition checks

    async def update_location(self, user_id, destination):
        async with self.bot.db.pool.acquire() as conn:
            query = "UPDATE public.players SET current_location = (SELECT locationid FROM public.locations WHERE name = $1) WHERE userid = $2"
            await conn.execute(query, destination, user_id)

    async def display_locations(self, ctx, current_location_id):
        available_paths = await self.get_available_paths(current_location_id)
        connected_locations = await self.get_connected_locations(current_location_id)

        description = ""
        for path in available_paths:
            description += f"Path to: {path['to_location_name']} - Condition: {path['condition_description']}\n"

        for loc in connected_locations:
            description += f"{loc['name']}\n"  # Only display location name

        embed = Embed(
            title="Available Travel Paths",
            description=description,
            color=0x00FF00
        )

        await ctx.send(embed=embed)

    async def get_available_paths(self, current_location_id):
        async with self.bot.db.pool.acquire() as conn:
            query = """
            SELECT p.path_id, 
                   CASE 
                     WHEN p.from_location_id = $1 THEN l_to.name 
                     ELSE l_from.name 
                   END AS to_location_name, 
                   p.condition, 
                   p.condition_description
            FROM public.paths p
            JOIN public.locations l_from ON p.from_location_id = l_from.locationid
            JOIN public.locations l_to ON p.to_location_id = l_to.locationid
            WHERE p.from_location_id = $1 OR p.to_location_id = $1
            """
            results = await conn.fetch(query, current_location_id)
            return results

    async def get_connected_locations(self, current_location_id):
        async with self.bot.db.pool.acquire() as conn:
            query = """
            SELECT l2.locationid, l2.name
            FROM public.locations l1
            JOIN public.locations l2 ON l1.parentlocationid = l2.locationid OR l2.parentlocationid = l1.locationid
            WHERE l1.locationid = $1
            """
            results = await conn.fetch(query, current_location_id)
            return results

def setup(bot):
    TravelSystem(bot)
