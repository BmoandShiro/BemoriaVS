from interactions import SlashContext, Extension, Button, ButtonStyle, ComponentContext, component_callback, Embed
import random
import asyncio
import re

class BattleSystem(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @staticmethod
    def roll_dice(sides=20):
        """Simulates a dice roll with given sides (default d20)."""
        return random.randint(1, sides)

    @component_callback(re.compile(r"^hunt_\d+$"))
    async def hunt_button_handler(self, ctx: ComponentContext):
        # Extract player ID from the custom ID
        original_user_id = int(ctx.custom_id.split("_")[1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)  # Acknowledge the interaction to prevent expiration

        # Get player data and proceed with hunting logic
        player_id = await self.db.get_or_create_player(ctx.author.id)
        player_data = await self.db.fetchrow("""
            SELECT current_location
            FROM player_data
            WHERE playerid = $1
        """, player_id)

        if not player_data:
            await ctx.send("Error: Unable to retrieve player data.", ephemeral=True)
            return

        # Fetch the current location ID for hunting
        location_id = player_data['current_location']

        # Start the hunting battle sequence
        await self.start_hunt_battle(ctx, player_id, location_id)

    async def prompt_player_action(self, ctx: SlashContext, player_id, player_health, enemy, enemy_health, player_attributes, enemy_attributes, player_resistances, enemy_resistances):
        # Send a message to prompt the player for an action (attack or use ability)
        embed = Embed(
            title=f"Battle with {enemy['name']}",
            description=f"Your health: {player_health}\n{enemy['name']}'s health: {enemy_health}",
            color=0xFF0000  # Red color for battle
        )

        attack_button = Button(
            style=ButtonStyle.PRIMARY,
            label="Attack",
            custom_id=f"attack_{player_id}_{enemy['enemyid']}"
        )
        ability_button = Button(
            style=ButtonStyle.SECONDARY,
            label="Use Ability",
            custom_id=f"ability_{player_id}_{enemy['enemyid']}"
        )

        components = [[attack_button, ability_button]]

        await ctx.send(embeds=[embed], components=components, ephemeral=True)

    # New function for initiating a hunt
    async def start_hunt_battle(self, ctx: SlashContext, player_id: int, location_id: int):
        # Fetch a random enemy from the location for hunting
        enemy = await self.db.fetchrow("""
            SELECT * FROM enemies WHERE locationid = $1 ORDER BY RANDOM() LIMIT 1
        """, location_id)
        
        if not enemy:
            await ctx.send("No enemies to hunt here.", ephemeral=True)
            return

        # Fetch player stats and initialize health values
        player_stats = dict(await self.db.fetch_player_details(player_id))  # Convert asyncpg.Record to dict
        player_health = player_stats['health']
        enemy_health = enemy['health']

        # Fetch resistances, attributes, and damage modifiers
        player_resistances = self.extract_resistances(player_stats)
        enemy_resistances = self.extract_resistances(enemy)
        player_attributes = self.extract_attributes(player_stats)
        enemy_attributes = self.extract_attributes(enemy)

        # Prompt player for action
        await self.prompt_player_action(ctx, player_id, player_health, enemy, enemy_health, player_attributes, enemy_attributes, player_resistances, enemy_resistances)

    @component_callback(re.compile(r"^attack_\d+_\d+$"))
    async def attack_button_handler(self, ctx: ComponentContext):
        await ctx.defer(ephemeral=True)

        # Extract player ID and enemy ID from the custom ID
        ids = ctx.custom_id.split("_")
        player_id = int(ids[1])
        enemy_id = int(ids[2])

        # Fetch player and enemy details
        player_stats = dict(await self.db.fetch_player_details(player_id))  # Convert asyncpg.Record to dict
        enemy = await self.db.fetchrow("""
            SELECT * FROM enemies WHERE enemyid = $1
        """, enemy_id)

        player_health = player_stats['health']
        enemy_health = enemy['health']

        # Fetch resistances, attributes, and damage modifiers
        player_resistances = self.extract_resistances(player_stats)
        enemy_resistances = self.extract_resistances(enemy)
        player_attributes = self.extract_attributes(player_stats)
        enemy_attributes = self.extract_attributes(enemy)

        # Player's attack logic
        player_attack_roll = self.roll_dice() + player_attributes['dexterity']
        critical_hit = False

        # Determine if it's a critical hit
        if player_attack_roll - player_attributes['dexterity'] == 20 or player_attack_roll >= 2 * (10 + enemy_attributes['agility']):
            critical_hit = True

        # Calculate hit success based on dexterity vs agility
        if player_attack_roll > 10 + enemy_attributes['agility']:
            # Check if enemy blocks the attack
            if random.randint(1, 100) <= enemy_resistances.get('block_chance', 0):
                await ctx.send(f"{enemy['name']} blocked your attack!", ephemeral=True)
            else:
                base_damage = player_attributes['strength']
                resistance_percentage = enemy_resistances.get('physical_resistance', 0)
                multiplier = 1 - (resistance_percentage / 100)
                damage_dealt = max(0, base_damage * multiplier)

                if critical_hit:
                    damage_dealt *= 1.5  # Critical hits deal 1.5x damage
                enemy_health -= damage_dealt

                await ctx.send(f"You dealt {damage_dealt} damage to {enemy['name']}. Remaining enemy health: {enemy_health}", ephemeral=True)

        # Update enemy's health
        if enemy_health <= 0:
            await ctx.send(f"You have defeated {enemy['name']}!", ephemeral=True)
            await self.handle_enemy_defeat(ctx, player_id, enemy_id)
        else:
            await self.enemy_attack(ctx, player_id, enemy, player_stats, enemy_health)

    async def enemy_attack(self, ctx: ComponentContext, player_id, enemy, player_stats, enemy_health):
        # Enemy's attack logic
        enemy_attack_roll = self.roll_dice() + enemy['dexterity']
        player_attributes = self.extract_attributes(player_stats)

        if enemy_attack_roll > 10 + player_attributes['agility']:  # Hit success based on dexterity vs agility
            # Check if player blocks the attack
            if random.randint(1, 100) <= player_stats.get('block_chance', 0):
                await ctx.send(f"You blocked {enemy['name']}'s attack!", ephemeral=True)
            else:
                resistance = player_stats.get('physical_resistance', 0)
                damage_received = max(0, enemy['strength'] - resistance)
                player_stats['health'] -= damage_received  # Update player's health

                await ctx.send(f"{enemy['name']} dealt {damage_received} damage to you. Remaining player health: {player_stats['health']}", ephemeral=True)

        # Check if player is defeated
        if player_stats['health'] <= 0:
            await ctx.send(f"You have been defeated by {enemy['name']}!", ephemeral=True)
        else:
            # Prompt player for the next action if they are still alive
            await self.prompt_player_action(ctx, player_id, player_stats['health'], enemy, enemy_health, player_attributes, self.extract_attributes(enemy), self.extract_resistances(player_stats), self.extract_resistances(enemy))

    @staticmethod
    def extract_resistances(entity):
        """Extract resistances from an entity (player or enemy)."""
        return {
            'fire_resistance': entity.get('fire_resistance', 0),
            'ice_resistance': entity.get('ice_resistance', 0),
            'lightning_resistance': entity.get('lightning_resistance', 0),
            'poison_resistance': entity.get('poison_resistance', 0),
            'magic_resistance': entity.get('magic_resistance', 0),
            'physical_resistance': entity.get('physical_resistance', 0),
            'crushing_resistance': entity.get('crushing_resistance', 0),
            'piercing_resistance': entity.get('piercing_resistance', 0),
            'water_resistance': entity.get('water_resistance', 0),
            'earth_resistance': entity.get('earth_resistance', 0),
            'light_resistance': entity.get('light_resistance', 0),
            'dark_resistance': entity.get('dark_resistance', 0),
            'air_resistance': entity.get('air_resistance', 0),
            'sleep_resistance': entity.get('sleep_resistance', 0),
            'block_chance': entity.get('block_chance', 0),
            'corrosive_resistance': entity.get('corrosive_resistance', 0)
        }

    @staticmethod
    def extract_attributes(entity):
        """Extract attributes from an entity (player or enemy)."""
        return {
            'strength': entity.get('strength', 0),
            'dexterity': entity.get('dexterity', 0),
            'intelligence': entity.get('intelligence', 0),
            'wisdom': entity.get('wisdom', 0),
            'agility': entity.get('agility', 0),
            'endurance': entity.get('endurance', 0),
            'charisma': entity.get('charisma', 0),
            'willpower': entity.get('willpower', 0),
            'luck': entity.get('luck', 0),
            'corrosive_damage': entity.get('corrosive_damage', 0)
        }

    async def handle_enemy_defeat(self, ctx: SlashContext, player_id: int, enemy_id: int):
        # Fetch drop chances for this enemy
        drop_list = await self.db.fetch("""
            SELECT edc.item_id, edc.drop_chance
            FROM enemy_drop_chances edc
            WHERE edc.enemyid = $1
        """, enemy_id)

        if not drop_list:
            await ctx.send("No loot available from this enemy.", ephemeral=True)
            return

        # Normalize drop chances
        total_drop_chance = sum(float(drop['drop_chance']) for drop in drop_list)
        normalized_drops = [
            (drop['item_id'], float(drop['drop_chance']) / total_drop_chance) for drop in drop_list
        ]

        # Determine which items are dropped
        await self.roll_for_loot(ctx, player_id, normalized_drops)

    async def roll_for_loot(self, ctx, player_id, normalized_drops):
        roll = random.uniform(0, 1)
        current_weight = 0

        # Iterate over items to determine if they drop
        for item_id, weight in normalized_drops:
            current_weight += weight
            if roll <= current_weight:
                # Ensure the player has room in their inventory
                has_slots = await self.db.can_add_to_inventory(player_id)
                if not has_slots:
                    await ctx.send("You don't have enough space in your inventory for the loot.", ephemeral=True)
                    return

                # Add the item to inventory
                await self.db.execute("""
                    INSERT INTO inventory (playerid, itemid, quantity, isequipped)
                    VALUES ($1, $2, 1, false)
                    ON CONFLICT (playerid, itemid) DO UPDATE SET quantity = inventory.quantity + 1
                """, player_id, item_id)
                await ctx.send(f"**You have received an item!** Check your inventory for item ID: {item_id}.", ephemeral=True)
                return

# Setup function to load this as an extension
def setup(bot):
    BattleSystem(bot)
