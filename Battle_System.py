from interactions import SlashContext, Extension, Button, ButtonStyle, ComponentContext, component_callback, Embed
import random
import asyncio
import re
import logging

class BattleSystem(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.active_battles = {}

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

        # Store battle information
        self.active_battles[player_id] = {
            'enemy_health': enemy_health,
            'enemy': enemy
        }

        # Fetch resistances, attributes, and damage modifiers
        player_resistances = self.extract_resistances(player_stats)
        enemy_resistances = self.extract_resistances(enemy)
        player_attributes = self.extract_attributes(player_stats)
        enemy_attributes = self.extract_attributes(enemy)

        # Prompt player for action
        await self.prompt_player_action(ctx, player_id, player_health, enemy, enemy_health, player_attributes, enemy_attributes, player_resistances, enemy_resistances)

    @component_callback(re.compile(r"^attack_\d+_\d+$"))
    async def attack_button_handler(self, ctx: ComponentContext):
        # Extract player ID and enemy ID from the custom ID
        _, player_id, enemy_id = ctx.custom_id.split("_")
        player_id, enemy_id = int(player_id), int(enemy_id)

        # Fetch player stats and enemy details
        player_stats = await self.db.fetchrow("""
            SELECT * FROM player_data WHERE playerid = $1
        """, player_id)

        if player_id not in self.active_battles:
            await ctx.send("No active battle found.", ephemeral=True)
            return

        # Get the current battle data
        battle_data = self.active_battles[player_id]
        enemy = battle_data['enemy']
        enemy_health = battle_data['enemy_health']

        player_attack_roll = self.roll_dice() + player_stats['dexterity']
        critical_hit = False

        # Determine if it's a critical hit
        if player_attack_roll - player_stats['dexterity'] == 20 or player_attack_roll >= 2 * (10 + enemy['agility']):
            critical_hit = True

        # Calculate hit success based on dexterity vs agility
        if player_attack_roll > 10 + enemy['agility']:
            # Check if enemy blocks the attack
            if random.randint(1, 100) <= enemy.get('block_chance', 0):
                await ctx.send(f"{enemy['name']} blocked your attack!", ephemeral=True)
            else:
                base_damage = player_stats['strength']
                resistance_percentage = enemy.get('physical_resistance', 0)
                multiplier = 1 - (resistance_percentage / 100)
                damage_dealt = max(0, base_damage * multiplier)

                if critical_hit:
                    damage_dealt *= 1.5  # Critical hits deal 1.5x damage

                # Update enemy's health
                enemy_health -= damage_dealt
                battle_data['enemy_health'] = enemy_health

                # Notify the player about the damage dealt, even if it's zero
                await ctx.send(f"You dealt {damage_dealt} damage to {enemy['name']}. Remaining enemy health: {enemy_health}", ephemeral=True)
        else:
            await ctx.send(f"You missed your attack on {enemy['name']}!", ephemeral=True)

        # Now it's enemy's turn to attack
        await self.enemy_attack(ctx, player_id, enemy)

        # Check if either the enemy or player has reached zero health
        await self.handle_combat_end(ctx, player_id, enemy)

    async def enemy_attack(self, ctx, player_id, enemy):
        # Fetch player stats
        player_stats = await self.db.fetchrow("""
            SELECT * FROM player_data WHERE playerid = $1
        """, player_id)

        if player_id not in self.active_battles:
            return  # If no active battle, stop further processing

        player_health = player_stats['health']
        enemy_attack_roll = self.roll_dice() + enemy['dexterity']

        if enemy_attack_roll > 10 + player_stats['agility']:  # Hit success based on dexterity vs agility
            # Check if player blocks the attack
            if random.randint(1, 100) <= player_stats.get('block_chance', 0):
                await ctx.send(f"You blocked {enemy['name']}'s attack!", ephemeral=True)
            else:
                damage_received = max(0, enemy['strength'] - player_stats['physical_resistance'])
                player_health -= damage_received

                # Update player's health in the database
                await self.db.execute("""
                    UPDATE player_data
                    SET health = $1
                    WHERE playerid = $2
                """, player_health, player_id)

                await ctx.send(f"{enemy['name']} dealt {damage_received} damage to you. Remaining player health: {player_health}", ephemeral=True)
        else:
            await ctx.send(f"{enemy['name']} missed their attack!", ephemeral=True)

    async def handle_combat_end(self, ctx, player_id, enemy):
        """Handles the ending of combat when either the player or enemy reaches zero health."""
        # Fetch updated player and enemy health
        player_stats = await self.db.fetchrow("""
            SELECT * FROM player_data WHERE playerid = $1
        """, player_id)

        if player_id not in self.active_battles:
            return  # If no active battle, stop further processing

        player_health = player_stats['health']
        enemy_health = self.active_battles[player_id]['enemy_health']

        # Handle case where both are near zero
        if player_health <= 0 and enemy_health <= 0:
            player_agility = player_stats['agility']
            enemy_agility = enemy['agility']

            if player_agility >= enemy_agility:
                # Player wins
                await ctx.send(f"You defeated {enemy['name']} just in time!", ephemeral=True)
                await self.handle_enemy_defeat(ctx, player_id, enemy['enemyid'])
            else:
                # Enemy wins
                await ctx.send(f"{enemy['name']} defeated you just before your strike!", ephemeral=True)
                await self.db.execute("""
                    UPDATE player_data
                    SET health = $1
                    WHERE playerid = $2
                """, 0, player_id)
            del self.active_battles[player_id]
            return

        # Handle case where only the enemy is defeated
        if enemy_health <= 0:
            await ctx.send(f"{enemy['name']} has been defeated!", ephemeral=True)
            await self.handle_enemy_defeat(ctx, player_id, enemy['enemyid'])
            del self.active_battles[player_id]
            return

        # Handle case where only the player is defeated
        if player_health <= 0:
            await ctx.send("You have been defeated!", ephemeral=True)
            await self.db.execute("""
                UPDATE player_data
                SET health = $1
                WHERE playerid = $2
            """, 0, player_id)
            del self.active_battles[player_id]
            return


        # Ensure enemy's health is reset after a battle if they were defeated
        if enemy_health <= 0:
            await self.db.execute("""
                UPDATE enemies
                SET health = $1
                WHERE enemyid = $2
            """, enemy['max_health'], enemy['enemyid'])


    async def handle_enemy_defeat(self, ctx: SlashContext, player_id: int, enemy_id: int):
        # Fetch drop chances for this enemy
        drop_list = await self.db.fetch("""
            SELECT itemid, droprate, quantity
            FROM enemyloot
            WHERE enemyid = $1
        """, enemy_id)

        if not drop_list:
            await ctx.send("No loot available from this enemy.", ephemeral=True)
            return

        # Determine which items are dropped
        await self.roll_for_loot(ctx, player_id, drop_list)


    async def roll_for_loot(self, ctx, player_id, drop_list):
        for drop in drop_list:
            if random.uniform(0, 100) <= drop['droprate']:
                # Ensure that itemid is converted to an integer
                itemid = int(drop['itemid'])
                quantity = drop['quantity']

                # Ensure the player has room in their inventory
                has_slots = await self.db.can_add_to_inventory(player_id)
                if not has_slots:
                    await ctx.send("You don't have enough space in your inventory for the loot.", ephemeral=True)
                    return

                # Fetch the item name from the items table
                item = await self.db.fetchrow("""
                    SELECT name FROM items WHERE itemid = $1
                """, itemid)

                if not item:
                    await ctx.send("Error: Unable to retrieve item data.", ephemeral=True)
                    return

                # Add the item to inventory
                await self.db.execute("""
                    INSERT INTO inventory (playerid, itemid, quantity, isequipped)
                    VALUES ($1, $2, $3, false)
                    ON CONFLICT (playerid, itemid) DO UPDATE SET quantity = inventory.quantity + $3
                """, player_id, itemid, quantity)

                await ctx.send(f"x** {quantity}  {item['name']}!** Added to your inventory.", ephemeral=True)


            
    @component_callback(re.compile(r"^ability_\d+_\d+$"))
    async def ability_button_handler(self, ctx: ComponentContext):
        try:
            # Extract player ID and enemy ID from the custom ID
            parts = ctx.custom_id.split("_")
            if len(parts) != 3:
                await ctx.send("Error: Invalid button ID format.", ephemeral=True)
                return

            # Parse player ID and enemy ID
            button_player_id = int(parts[1])
            enemy_id = int(parts[2])

            # Debugging information to verify what's happening
            print(f"[Debug] Custom ID: {ctx.custom_id}")
            print(f"[Debug] Player ID from button: {button_player_id}, Author Discord ID: {ctx.author.id}")

            # Fetch the player's data using the Discord ID to verify identity
            player_data = await self.db.fetchrow("""
                SELECT playerid FROM players
                WHERE discord_id = $1
            """, ctx.author.id)

            if not player_data:
                await ctx.send("Error: Player not found.", ephemeral=True)
                return

            # Extract the actual player ID from the database
            actual_player_id = player_data['playerid']

            # Compare player ID from the button with the actual player ID retrieved from the database
            if button_player_id != actual_player_id:
                print("[Debug] Authorization failed - Player IDs do not match.")
                await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
                return

            # Proceed if authorized
            await ctx.defer(ephemeral=True)

            # Fetch the player's equipped abilities
            abilities = await self.db.fetch("""
                SELECT pa.*, a.*
                FROM player_abilities pa
                JOIN abilities a ON pa.ability_id = a.ability_id
                WHERE pa.playerid = $1 AND pa.is_equipped = TRUE
            """, actual_player_id)

            if not abilities:
                await ctx.send("You have no equipped abilities to use.", ephemeral=True)
                return

            # Create buttons for each equipped ability
            ability_buttons = [
                Button(
                    style=ButtonStyle.SECONDARY,
                    label=ability['name'],
                    custom_id=f"cast_ability_{actual_player_id}_{enemy_id}_{ability['ability_id']}"
                ) for ability in abilities
            ]

            # Send the prompt for the player to choose an ability
            await ctx.send(
                content="Choose an ability to use:",
                components=[ability_buttons],
                ephemeral=True
            )

        except (ValueError, IndexError) as e:
            # Handle any parsing issues
            print(f"[Error] Failed to parse button interaction: {e}")
            await ctx.send("Error: Could not process button interaction.", ephemeral=True)
            

    @component_callback(re.compile(r"^cast_ability_\d+_\d+_\d+$"))
    async def cast_ability_handler(self, ctx: ComponentContext):
        try:
            # Parse player ID, enemy ID, and ability ID
            parts = ctx.custom_id.split("_")
            player_id = int(parts[2])
            enemy_id = int(parts[3])
            ability_id = int(parts[4])

            # Fetch player, ability, and enemy data
            player_data = await self.db.fetchrow("SELECT * FROM player_data WHERE playerid = $1", player_id)
            player_ability = await self.db.fetchrow("SELECT * FROM abilities WHERE ability_id = $1", ability_id)
            enemy = await self.db.fetchrow("SELECT * FROM enemies WHERE enemyid = $1", enemy_id)

            if not (player_data and player_ability and enemy):
                await ctx.send("Error: Missing required data for the ability.", ephemeral=True)
                return

            # Check if the player has enough mana to cast the ability
            mana_cost = player_ability.get('mana_cost', 0)
            current_mana = player_data.get('mana', 0)

            if current_mana < mana_cost:
                await ctx.send(f"You do not have enough mana to cast {player_ability['name']}! (Required: {mana_cost}, Available: {current_mana})", ephemeral=True)
                return

            # Deduct mana cost and update the player_data table
            updated_mana = current_mana - mana_cost
            await self.db.execute("""
                UPDATE player_data
                SET mana = $1
                WHERE playerid = $2
            """, updated_mana, player_id)

            # Notify the player about mana deduction
            logging.info(f"Player {player_id} cast {player_ability['name']} (Mana Cost: {mana_cost}). Remaining Mana: {updated_mana}")

             # Calculate hit chance
            scaling_attribute = player_ability['scaling_attribute']
            player_roll = self.roll_dice() + player_data.get(scaling_attribute, 0)
            enemy_roll = self.roll_dice() + enemy['agility']

            if player_roll < enemy_roll:
                # Ability missed
                await ctx.send(f"You tried to use {player_ability['name']} but {enemy['name']} dodged it!", ephemeral=True)
                # Proceed to enemy's turn even if dodged
                await self.enemy_attack(ctx, player_id, enemy)
                return

            
            # Initialize total damage
            total_damage = 0

            # Use the static method to get damage-resistance mapping
            damage_resistance_mapping = self.get_damage_resistance_mapping()

            # Iterate through damage types explicitly set in the ability
            for damage_type, (min_col, max_col, resistance_col) in self.get_damage_resistance_mapping().items():
                min_damage = player_ability.get(min_col, 0)
                max_damage = player_ability.get(max_col, 0)

                if min_damage > 0 and max_damage > 0:
                    ability_damage = random.randint(min_damage, max_damage)  # Roll within the range
                    player_damage_modifier = player_data.get(f"{damage_type}_damage", 0)
                    enemy_resistance = enemy.get(resistance_col, 0)

                    # Debugging: Log the rolled value
                    logging.info(f"Rolled {damage_type}_damage: {ability_damage}")

                    # Handle resistance: Negative resistance increases damage, positive reduces it
                    if enemy_resistance < 0:
                        effective_damage = max(0, (ability_damage + player_damage_modifier) - enemy_resistance)
                    else:
                        effective_damage = max(0, (ability_damage + player_damage_modifier) - enemy_resistance)

                    # Debugging: Log the effective damage
                    logging.info(f"Effective {damage_type}_damage after resistance: {effective_damage}")

                    total_damage += effective_damage


            # Apply total damage to the enemy
            enemy_health = max(0, self.active_battles[player_id]['enemy_health'] - total_damage)
            self.active_battles[player_id]['enemy_health'] = enemy_health

            await ctx.send(
                f"You used {player_ability['name']} and dealt {total_damage:.1f} damage "
                f"to {enemy['name']} (rolled {ability_damage}). Remaining enemy health: {enemy_health}.",
                ephemeral=True
            )


            # Check for combat end
            await self.handle_combat_end(ctx, player_id, enemy)

            # Enemy counterattack if still alive
            if enemy_health > 0:
                await self.enemy_attack(ctx, player_id, enemy)

        except Exception as e:
            logging.error(f"Error in cast_ability_handler: {e}")
            await ctx.send("An error occurred while using the ability.", ephemeral=True)








        




    '''async def handle_combat_end(self, ctx, player_id, enemy):
        """Handles the ending of combat when either the player or enemy reaches zero health."""
        # Fetch updated player and enemy health
        player_stats = await self.db.fetchrow("""
            SELECT * FROM player_data WHERE playerid = $1
        """, player_id)

        player_health = player_stats['health']
        enemy_health = self.active_battles[player_id]['enemy_health']

        # Handle case if the enemy is defeated
        if enemy_health <= 0:
            await ctx.send(f"{enemy['name']} has been defeated!", ephemeral=True)
            await self.handle_enemy_defeat(ctx, player_id, enemy['enemyid'])
            del self.active_battles[player_id]  # Remove the battle as it's over
            return

        # Handle case if the player is defeated
        if player_health <= 0:
            await ctx.send("You have been defeated!", ephemeral=True)
            # Update player's health to zero in the database
            await self.db.execute("""
                UPDATE player_data
                SET health = $1
                WHERE playerid = $2
            """, 0, player_id)
            del self.active_battles[player_id]  # Remove the battle as it's over'''







    async def use_ability(self, ctx, player_id, player_stats, enemy):
        # Logic for handling ability usage
        abilities = await self.db.fetch("""
            SELECT * FROM abilities WHERE player_id = $1
        """, player_id)

        if not abilities:
            await ctx.send("You have no abilities to use.", ephemeral=True)
            return

        # For now, pick the first ability
        ability = abilities[0]

        total_damage = 0
        scaling_attribute = ability['scaling_attribute']
        scaling_value = player_stats.get(scaling_attribute, 0)

        for damage_type in ['physical', 'fire', 'ice', 'lightning', 'poison', 'magic', 'crushing', 'piercing', 'water', 'earth', 'light', 'dark', 'air', 'corrosive']:
            damage = ability.get(f'{damage_type}_damage', 0) + scaling_value
            resistance = enemy.get(f'{damage_type}_resistance', 0)
            damage_after_resistance = max(0, damage * (1 - resistance / 100.0))
            total_damage += damage_after_resistance

        enemy_health = max(0, enemy['health'] - total_damage)

        # Update the enemy's health in the database
        await self.db.execute("""
            UPDATE enemies SET health = $1
            WHERE enemyid = $2
        """, enemy_health, enemy['enemyid'])

        if total_damage > 0:
            await ctx.send(f"You used {ability['name']} and dealt {total_damage} damage to {enemy['name']}. Remaining enemy health: {enemy_health}", ephemeral=True)
        else:
            await ctx.send(f"You used {ability['name']} but it had no effect on {enemy['name']}.", ephemeral=True)

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
    
    @staticmethod
    def get_damage_resistance_mapping():
        return {
            'fire': ('fire_damage_min', 'fire_damage_max', 'fire_resistance'),
            'ice': ('ice_damage_min', 'ice_damage_max', 'ice_resistance'),
            'lightning': ('lightning_damage_min', 'lightning_damage_max', 'lightning_resistance'),
            'poison': ('poison_damage_min', 'poison_damage_max', 'poison_resistance'),
            'magic': ('magic_damage_min', 'magic_damage_max', 'magic_resistance'),
            'crushing': ('crushing_damage_min', 'crushing_damage_max', 'crushing_resistance'),
            'piercing': ('piercing_damage_min', 'piercing_damage_max', 'piercing_resistance'),
            'water': ('water_damage_min', 'water_damage_max', 'water_resistance'),
            'earth': ('earth_damage_min', 'earth_damage_max', 'earth_resistance'),
            'light': ('light_damage_min', 'light_damage_max', 'light_resistance'),
            'dark': ('dark_damage_min', 'dark_damage_max', 'dark_resistance'),
            'air': ('air_damage_min', 'air_damage_max', 'air_resistance'),
            'corrosive': ('corrosive_damage_min', 'corrosive_damage_max', 'corrosive_resistance'),
        }


# Setup function to load this as an extension
def setup(bot):
    BattleSystem(bot)
