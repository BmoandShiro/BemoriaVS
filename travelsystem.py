import interactions
from interactions import Extension, Embed, listen

class TravelSystem(Extension):
    def __init__(self, bot):
        self.bot = bot

    async def display_locations(self, ctx, current_location_id):
        available_paths = await self.get_available_paths(current_location_id)
        connected_locations = await self.get_connected_locations(current_location_id)

        description = ""
        for path in available_paths:
            description += f"Path to: {path['to_location_name']} - Condition: {path['condition_description']}\n"

        for loc in connected_locations:
            description += f"{loc['name']}\n"

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
