from interactions import SlashContext, Extension, Button, ButtonStyle
import random

class BattleSystem(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @staticmethod
    def roll_dice(sides=20):
        """Simulates a dice roll with given sides (default d20)."""
        return random.randint(1, sides)

    async def start_battle(self, ctx: SlashContext, player_id: int, location_id: int):
        # Fetch a random enemy from the location
        enemy = await self.db.fetchrow("""
            SELECT * FROM enemies WHERE location_id = $1 ORDER BY RANDOM() LIMIT 1
        """, location_id)
        
        if not enemy:
            await ctx.send("No enemies to fight here.", ephemeral=True)
            return

        player_stats = await self.db.fetch_player_details(player_id)
        
        player_health = player_stats['health']
        enemy_health = enemy['health']

        # Fetch resistances, attributes, and damage modifiers
        player_resistances = self.extract_resistances(player_stats)
        enemy_resistances = self.extract_resistances(enemy)
        player_attributes = self.extract_attributes(player_stats)
        enemy_attributes = self.extract_attributes(enemy)

        # Loop until one side loses
        while player_health > 0 and enemy_health > 0:
            # Player action - either basic attack or ability
            player_action = await self.choose_player_action(ctx, player_id)
            if player_action == 'basic_attack':
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
                        base_damage = player_attributes['strength'] + player_stats['attack_power'] - enemy_resistances['physical_resistance']
                        damage_dealt = max(0, base_damage)
                        if critical_hit:
                            damage_dealt *= 1.5  # Critical hits deal 1.5x damage
                        enemy_health -= damage_dealt
                        await ctx.send(f"You dealt {damage_dealt} damage to {enemy['name']}. Remaining enemy health: {enemy_health}", ephemeral=True)
            elif player_action == 'ability':
                await self.use_ability(ctx, player_id, enemy, player_attributes, enemy_resistances, enemy_health)

            # Enemy attack
            enemy_attack_roll = self.roll_dice() + enemy_attributes['dexterity']
            if enemy_attack_roll > 10 + player_attributes['agility']:  # Hit success based on dexterity vs agility
                # Check if player blocks the attack
                if random.randint(1, 100) <= player_resistances.get('block_chance', 0):
                    await ctx.send(f"You blocked {enemy['name']}'s attack!", ephemeral=True)
                else:
                    damage_received = max(0, enemy['attack_power'] - player_resistances['physical_resistance'])
                    player_health -= damage_received
                    await ctx.send(f"{enemy['name']} dealt {damage_received} damage to you. Remaining player health: {player_health}", ephemeral=True)

        if player_health <= 0:
            await ctx.send(f"You have been defeated by {enemy['name']}!", ephemeral=True)
        else:
            await ctx.send(f"You have defeated {enemy['name']}!", ephemeral=True)
            await self.handle_enemy_defeat(ctx, player_id, enemy['enemy_id'])

    async def choose_player_action(self, ctx, player_id):
        """Prompt the player to choose an action (basic attack or use an ability)."""
        # For simplicity, we'll assume player always does basic attack in this implementation
        # This function can be expanded to take player input and choose abilities dynamically
        return 'basic_attack'

    async def use_ability(self, ctx, player_id, enemy, player_attributes, enemy_resistances, enemy_health):
        """Handles the usage of a player's ability during battle."""
        # Fetch player's abilities from the database
        abilities = await self.db.fetch("""
            SELECT * FROM abilities WHERE player_id = $1
        """, player_id)

        if not abilities:
            await ctx.send("You have no abilities to use.", ephemeral=True)
            return

        # For now, pick the first ability (in a real scenario, you would prompt the user to choose)
        ability = abilities[0]

        # Calculate ability effect for each damage type
        total_damage = 0
        for damage_type in ['physical', 'fire', 'ice', 'lightning', 'poison', 'magic', 'crushing', 'piercing', 'water', 'earth', 'light', 'dark', 'air']:
            damage = ability[f'{damage_type}_damage'] + player_attributes.get(ability['scaling_attribute'], 0)
            resistance = enemy_resistances.get(f'{damage_type}_resistance', 0)
            damage_after_resistance = max(0, damage - resistance)
            total_damage += damage_after_resistance

        # Check if enemy blocks the ability
        if random.randint(1, 100) <= enemy_resistances.get('block_chance', 0):
            await ctx.send(f"{enemy['name']} blocked your ability: {ability['name']}!", ephemeral=True)
        else:
            # Apply total damage to enemy
            enemy_health -= total_damage
            await ctx.send(f"You used {ability['name']} and dealt {total_damage} damage to {enemy['name']}. Remaining enemy health: {enemy_health}", ephemeral=True)

        # Update player's mana
        player_attributes['mana'] -= ability['mana_cost']

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
            'block_chance': entity.get('block_chance', 0)
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
            'luck': entity.get('luck', 0)
        }

    async def handle_enemy_defeat(self, ctx: SlashContext, player_id: int, enemy_id: int):
        # Fetch drop chances for this enemy
        drop_list = await self.db.fetch("""
            SELECT edc.item_id, edc.drop_chance
            FROM enemy_drop_chances edc
            WHERE edc.enemy_id = $1
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
