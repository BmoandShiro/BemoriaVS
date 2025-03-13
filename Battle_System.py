from interactions import SlashContext, Extension, Button, ButtonStyle, ComponentContext, component_callback, Embed, StringSelectOption, StringSelectMenu
import random
import asyncio
import re
import logging
from datetime import datetime

class BattleSystem(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.active_battles = {}  # Format: {player_id: {'enemy_health': int, 'enemy': dict, 'enemy_effects': list}}

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

        # Fetch player stats from the view
        player_stats = await self.db.fetchrow("""
            SELECT * FROM player_stats_view WHERE playerid = $1
        """, player_id)

        if not player_stats:
            await ctx.send("Error: Could not retrieve player stats.", ephemeral=True)
            return

        # Get current health from player_data
        current_stats = await self.db.fetchrow("""
            SELECT health FROM player_data WHERE playerid = $1
        """, player_id)

        if not current_stats:
            await ctx.send("Error: Could not retrieve current stats.", ephemeral=True)
            return

        # Convert to dict and add playerid
        player_stats = dict(player_stats)
        enemy_health = enemy['health']

        # Store battle information with empty effects list
        self.active_battles[player_id] = {
            'enemy_health': enemy_health,
            'enemy': enemy,
            'enemy_effects': []  # List to store enemy status effects
        }

        # Fetch resistances and attributes
        player_resistances = self.extract_resistances(player_stats)
        enemy_resistances = self.extract_resistances(enemy)
        player_attributes = self.extract_attributes(player_stats)
        enemy_attributes = self.extract_attributes(enemy)

        # Prompt player for action
        await self.prompt_player_action(ctx, player_id, current_stats['health'], enemy, enemy_health, 
                                      player_attributes, enemy_attributes, player_resistances, enemy_resistances)

    @staticmethod
    def extract_resistances(entity):
        """Extract resistances from an entity (player or enemy)."""
        resistance_fields = [
            'fire_resistance', 'ice_resistance', 'lightning_resistance',
            'poison_resistance', 'magic_resistance', 'physical_resistance',
            'crushing_resistance', 'piercing_resistance', 'water_resistance',
            'earth_resistance', 'light_resistance', 'dark_resistance',
            'air_resistance', 'sleep_resistance'
        ]
        
        resistances = {}
        for field in resistance_fields:
            # For players, look for total_{field}
            total_field = f'total_{field}'
            if total_field in entity:
                resistances[field] = entity[total_field]
            else:
                resistances[field] = entity.get(field, 0)
        
        return resistances

    @staticmethod
    def extract_attributes(entity):
        """Extract attributes from an entity (player or enemy)."""
        attribute_fields = [
            'strength', 'dexterity', 'intelligence', 'wisdom',
            'agility', 'endurance', 'charisma', 'willpower', 'luck'
        ]
        
        attributes = {}
        for field in attribute_fields:
            # For players, look for total_{field}
            total_field = f'total_{field}'
            if total_field in entity:
                attributes[field] = entity[total_field]
            else:
                attributes[field] = entity.get(field, 0)
        
        return attributes

    async def calculate_attack_roll(self, attacker_stats: dict, defender_stats: dict) -> tuple[bool, bool, bool]:
        """
        Calculate attack roll results.
        Returns: (hit_success, is_critical, is_blocked)
        """
        # Get the appropriate stats based on whether it's a player (has total_ prefix) or enemy
        attacker_dex = attacker_stats.get('total_dexterity', attacker_stats.get('dexterity', 0))
        attacker_luck = attacker_stats.get('total_luck', attacker_stats.get('luck', 0))
        defender_dex = defender_stats.get('total_dexterity', defender_stats.get('dexterity', 0))
        defender_agi = defender_stats.get('total_agility', defender_stats.get('agility', 0))
        
        # Base attack roll (d20) + attacker's dexterity
        attack_roll = self.roll_dice() + attacker_dex
        
        # Calculate critical chance (base 5% + luck bonus)
        critical_chance = 5 + (attacker_luck * 0.5)
        is_critical = random.uniform(0, 100) <= critical_chance
        
        # Calculate dodge chance (base 5% + defender's agility)
        dodge_chance = 5 + (defender_agi * 0.5)
        is_dodged = random.uniform(0, 100) <= dodge_chance
        
        if is_dodged:
            return False, False, False
            
        # Calculate block chance (base 10% + defender's dexterity)
        block_chance = 10 + (defender_dex * 0.5)
        is_blocked = random.uniform(0, 100) <= block_chance
        
        # Calculate hit success
        hit_threshold = 10 + defender_agi
        hit_success = attack_roll > hit_threshold
        
        return hit_success, is_critical, is_blocked

    async def calculate_damage(self, attacker_stats: dict, defender_stats: dict, 
                             damage_type: str, base_damage: int, is_critical: bool) -> int:
        """
        Calculate final damage after all modifiers.
        Parameters:
        - base_damage: The ability's base damage value
        - damage_type: The type of damage (fire, ice, etc.)
        - defender_stats: Contains the enemy's resistance values
        Returns: Final calculated damage
        """
        # Get resistance for damage type (handle both player and enemy stats)
        resistance_key = f"{damage_type}_resistance"
        total_resistance_key = f"total_{resistance_key}"
        resistance = defender_stats.get(total_resistance_key, defender_stats.get(resistance_key, 0))
        
        # Calculate damage reduction/amplification from resistance
        # Negative resistance increases damage, positive reduces it
        resistance_modifier = 1 - (resistance / 100)
        damage = base_damage * resistance_modifier
        
        # Apply critical hit multiplier if critical
        if is_critical:
            attacker_luck = attacker_stats.get('total_luck', attacker_stats.get('luck', 0))
            critical_multiplier = 1.5 + (attacker_luck * 0.01)
            damage *= critical_multiplier
            
        # Apply status effect modifiers if attacker is a player
        if 'playerid' in attacker_stats:
            status_effects = await self.get_active_effects(attacker_stats['playerid'])
            for effect in status_effects:
                if effect['attribute'].startswith('damage_bonus_'):
                    damage *= (1 + effect['modifier_value'] / 100)
                elif effect['attribute'].startswith('damage_reduction_'):
                    damage *= (1 - effect['modifier_value'] / 100)
                
        # Ensure minimum damage of 1 unless complete immunity (100% or higher resistance)
        return 0 if resistance >= 100 else max(1, int(damage))

    @component_callback(re.compile(r"^attack_\d+_\d+$"))
    async def attack_button_handler(self, ctx: ComponentContext):
        # Extract player ID and enemy ID from the custom ID
        _, player_id, enemy_id = ctx.custom_id.split("_")
        player_id, enemy_id = int(player_id), int(enemy_id)

        # Fetch player stats from the view
        player_stats = await self.db.fetchrow("""
            SELECT * FROM player_stats_view WHERE playerid = $1
        """, player_id)

        if not player_stats:
            await ctx.send("Error: Could not retrieve player stats.", ephemeral=True)
            return

        player_stats = dict(player_stats)

        if player_id not in self.active_battles:
            await ctx.send("No active battle found.", ephemeral=True)
            return

        # Get the current battle data
        battle_data = self.active_battles[player_id]
        enemy = battle_data['enemy']
        enemy_health = battle_data['enemy_health']

        # Calculate attack roll results
        hit_success, is_critical, is_blocked = await self.calculate_attack_roll(
            player_stats, enemy
        )

        if is_blocked:
            await ctx.send(f"{enemy['name']} blocked your attack!", ephemeral=True)
        elif not hit_success:
            await ctx.send(f"You missed your attack on {enemy['name']}!", ephemeral=True)
        else:
            # Calculate damage
            base_damage = player_stats['total_strength']
            damage_dealt = await self.calculate_damage(
                player_stats, enemy,
                'physical', base_damage, is_critical
            )

            # Update enemy's health
            enemy_health -= damage_dealt
            battle_data['enemy_health'] = enemy_health

            # Send combat message
            message = f"You dealt {damage_dealt} damage to {enemy['name']}"
            if is_critical:
                message += " (Critical Hit!)"
            message += f". Remaining enemy health: {enemy_health}"
            await ctx.send(message, ephemeral=True)

        # Enemy's turn
        await self.enemy_attack(ctx, player_id, enemy)

        # Check combat end
        await self.handle_combat_end(ctx, player_id, enemy)

    async def enemy_attack(self, ctx, player_id, enemy):
        # Fetch player stats from the view
        player_stats = await self.db.fetchrow("""
            SELECT * FROM player_stats_view WHERE playerid = $1
        """, player_id)
        
        if not player_stats:
            await ctx.send("Error: Could not retrieve player stats.", ephemeral=True)
            return

        player_stats = dict(player_stats)
        
        # Get current health from player_data
        current_stats = await self.db.fetchrow("""
            SELECT health FROM player_data WHERE playerid = $1
        """, player_id)

        if not current_stats:
            await ctx.send("Error: Could not retrieve current stats.", ephemeral=True)
            return
        
        # Calculate attack roll results for enemy
        hit_success, is_critical, is_blocked = await self.calculate_attack_roll(
            enemy, player_stats
        )

        if is_blocked:
            await ctx.send(f"You blocked {enemy['name']}'s attack!", ephemeral=True)
        elif not hit_success:
            await ctx.send(f"{enemy['name']} missed their attack!", ephemeral=True)
        else:
            # Calculate damage with status effects
            base_damage = enemy['strength']
            damage_received = await self.calculate_damage(
                enemy, player_stats,
                'physical', base_damage, is_critical
            )
            
            # Apply any damage-over-time effects
            dot_effects = [e for e in await self.get_active_effects(player_id) if e['attribute'].startswith('dot_')]
            for dot in dot_effects:
                damage_received += dot['modifier_value']

            # Update player's health
            new_health = current_stats['health'] - damage_received
            new_health = max(0, new_health)  # Ensure health doesn't go below 0
            
            await self.db.execute("""
                UPDATE player_data
                SET health = $1
                WHERE playerid = $2
            """, new_health, player_id)

            # Send combat message
            message = f"{enemy['name']} dealt {damage_received} damage to you"
            if is_critical:
                message += " (Critical Hit!)"
            message += f". Remaining health: {new_health}"
            await ctx.send(message, ephemeral=True)

        # Clean up expired effects
        await self.db.execute("""
            DELETE FROM temporary_effects
            WHERE player_id = $1
            AND start_time + (duration * interval '1 second') <= NOW()
        """, player_id)

    async def handle_combat_end(self, ctx, player_id, enemy):
        """Handles the ending of combat when either the player or enemy reaches zero health."""
        # Fetch current health from player_data
        current_stats = await self.db.fetchrow("""
            SELECT health FROM player_data WHERE playerid = $1
        """, player_id)

        if player_id not in self.active_battles:
            return  # If no active battle, stop further processing

        if not current_stats:
            await ctx.send("Error: Could not retrieve current stats.", ephemeral=True)
            return

        player_health = current_stats['health']  # Use current health from player_data
        enemy_health = self.active_battles[player_id]['enemy_health']

        # Get player stats for attributes
        player_stats = await self.db.fetchrow("""
            SELECT * FROM player_stats_view WHERE playerid = $1
        """, player_id)

        if not player_stats:
            await ctx.send("Error: Could not retrieve player stats.", ephemeral=True)
            return

        # Handle case where both are near zero
        if player_health <= 0 and enemy_health <= 0:
            player_agility = player_stats['total_agility']
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
                    SET health = 0
                    WHERE playerid = $1
                """, player_id)
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
                SET health = 0
                WHERE playerid = $1
            """, player_id)
            del self.active_battles[player_id]
            return

        # If battle continues, prompt for next action
        if player_id in self.active_battles:
            # Fetch resistances and attributes
            player_resistances = self.extract_resistances(player_stats)
            enemy_resistances = self.extract_resistances(enemy)
            player_attributes = self.extract_attributes(player_stats)
            enemy_attributes = self.extract_attributes(enemy)

            # Prompt player for next action using current health
            await self.prompt_player_action(
                ctx, player_id, player_health, enemy, enemy_health,
                player_attributes, enemy_attributes,
                player_resistances, enemy_resistances
            )

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
                ORDER BY a.ability_type, a.name
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

            # Group buttons into rows of up to 5 buttons each
            button_rows = []
            for i in range(0, len(ability_buttons), 5):
                button_rows.append(ability_buttons[i:i+5])

            # Send the prompt for the player to choose an ability
            await ctx.send(
                content="Choose an ability to use:",
                components=button_rows,
                ephemeral=True
            )

        except Exception as e:
            print(f"[Error] Failed to process ability button: {e}")
            await ctx.send("Error: Could not process ability selection.", ephemeral=True)

    async def calculate_ability_hit(self, attacker_stats: dict, defender_stats: dict, ability_type: str) -> tuple[bool, bool]:
        """
        Calculate if an ability hits and if it crits.
        Returns: (hit_success, is_critical)
        """
        # For magical abilities, use intelligence and willpower
        if ability_type in ['fire', 'ice', 'lightning', 'water', 'earth', 'air', 'light', 'dark', 'magic']:
            attacker_stat = attacker_stats.get('total_intelligence', attacker_stats.get('intelligence', 0))
            defender_stat = defender_stats.get('total_willpower', defender_stats.get('willpower', 0))
        else:
            # For physical abilities, use dexterity and agility
            attacker_stat = attacker_stats.get('total_dexterity', attacker_stats.get('dexterity', 0))
            defender_stat = defender_stats.get('total_agility', defender_stats.get('agility', 0))
        
        # Base hit roll (d20) + attacker's relevant stat
        hit_roll = self.roll_dice() + attacker_stat
        
        # Calculate critical chance (base 5% + intelligence/dexterity bonus)
        critical_chance = 5 + (attacker_stat * 0.5)
        is_critical = random.uniform(0, 100) <= critical_chance
        
        # Calculate hit success - abilities are easier to land than physical attacks
        hit_threshold = 8 + defender_stat
        hit_success = hit_roll > hit_threshold
        
        return hit_success, is_critical

    @component_callback(re.compile(r"^cast_ability_\d+_\d+_\d+$"))
    async def cast_ability_handler(self, ctx: ComponentContext):
        try:
            # Extract IDs from custom_id
            _, _, player_id, enemy_id, ability_id = ctx.custom_id.split("_")
            player_id, enemy_id, ability_id = int(player_id), int(enemy_id), int(ability_id)

            # Fetch ability details
            ability = await self.db.fetchrow("""
                SELECT * FROM abilities WHERE ability_id = $1
            """, ability_id)

            if not ability:
                await ctx.send("Error: Could not find ability.", ephemeral=True)
                return

            # Fetch player stats from the view
            player_stats = await self.db.fetchrow("""
                SELECT * FROM player_stats_view WHERE playerid = $1
            """, player_id)

            if not player_stats:
                await ctx.send("Error: Could not retrieve player stats.", ephemeral=True)
                return

            player_stats = dict(player_stats)

            # Get current mana from player_data
            current_stats = await self.db.fetchrow("""
                SELECT mana FROM player_data WHERE playerid = $1
            """, player_id)

            # Check if player has enough mana
            if current_stats['mana'] < ability['mana_cost']:
                await ctx.send("Not enough mana to use this ability!", ephemeral=True)
                return

            # Get battle data
            if player_id not in self.active_battles:
                await ctx.send("No active battle found.", ephemeral=True)
                return

            battle_data = self.active_battles[player_id]
            enemy = battle_data['enemy']
            enemy_health = battle_data['enemy_health']

            # Calculate ability hit success using the new method
            hit_success, is_critical = await self.calculate_ability_hit(
                player_stats, enemy, ability['ability_type']
            )

            # Check if the enemy blocks - enemies have lower block chance against abilities
            block_chance = enemy.get('block_chance', 0) * 0.5  # 50% less chance to block abilities
            is_blocked = random.uniform(0, 100) <= block_chance

            if is_blocked:
                await ctx.send(f"{enemy['name']} blocked your {ability['name']}!", ephemeral=True)
            elif not hit_success:
                # Get the resistance value for this ability type
                resistance_key = f"{ability['ability_type']}_resistance"
                resistance = enemy.get(resistance_key, 0)
                if resistance > 50:  # High resistance message
                    await ctx.send(f"{enemy['name']} is highly resistant to {ability['ability_type']} damage!", ephemeral=True)
                else:  # Normal miss message
                    await ctx.send(f"Your {ability['name']} missed {enemy['name']}!", ephemeral=True)
            else:
                # Calculate base damage based on ability type
                # Try to get damage from specific damage fields first
                damage_field = f"{ability['ability_type']}_damage"
                base_damage = ability.get(damage_field, ability.get('damage', 5))  # Default to 'damage' field or 5
                
                # Add intelligence bonus for magical abilities
                if ability['ability_type'] in ['fire', 'ice', 'lightning', 'water', 'earth', 'air', 'light', 'dark', 'magic']:
                    int_bonus = player_stats['total_intelligence'] * 0.5
                    base_damage += int_bonus
                
                damage_dealt = await self.calculate_damage(
                    player_stats, enemy,
                    ability['ability_type'], base_damage, is_critical
                )

                # Update enemy health
                enemy_health -= damage_dealt
                battle_data['enemy_health'] = enemy_health

                # Deduct mana cost
                new_mana = current_stats['mana'] - ability['mana_cost']
                await self.db.execute("""
                    UPDATE player_data
                    SET mana = $1
                    WHERE playerid = $2
                """, new_mana, player_id)

                # Send combat message
                message = f"You used {ability['name']} and dealt {damage_dealt} damage"
                if is_critical:
                    message += " (Critical Hit!)"
                message += f". Remaining enemy health: {enemy_health}"
                message += f"\nMana remaining: {new_mana}"
                await ctx.send(message, ephemeral=True)

                # Handle status effects for enemies in memory
                if ability.get('status_effect'):
                    effect = {
                        'type': ability['status_effect'],
                        'duration': ability.get('effect_duration', 3),
                        'value': ability.get('effect_value', 0),
                        'start_time': datetime.now()
                    }
                    battle_data['enemy_effects'].append(effect)
                    await ctx.send(f"{enemy['name']} is affected by {ability['status_effect']}!", ephemeral=True)

            # Enemy's turn
            await self.enemy_attack(ctx, player_id, enemy)

            # Check combat end
            await self.handle_combat_end(ctx, player_id, enemy)

        except Exception as e:
            print(f"[Error] Failed to process ability cast: {e}")
            await ctx.send("Error: Could not process ability cast.", ephemeral=True)

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

    async def apply_status_effect(self, target_id: int, effect_type: str, duration: int, value: int):
        """Apply a status effect to a target (player or enemy)."""
        await self.db.execute("""
            INSERT INTO temporary_effects (player_id, attribute, modifier_value, duration, start_time)
            VALUES ($1, $2, $3, $4, NOW())
        """, target_id, effect_type, value, duration)

    async def get_active_effects(self, target_id: int):
        """Get all active status effects for a target."""
        return await self.db.fetch("""
            SELECT attribute, modifier_value, duration, start_time
            FROM temporary_effects
            WHERE player_id = $1
            AND start_time + (duration * interval '1 second') > NOW()
        """, target_id)

    async def calculate_effective_stats(self, base_stats: dict, target_id: int):
        """Calculate effective stats including status effects."""
        effects = await self.get_active_effects(target_id)
        effective_stats = base_stats.copy()

        for effect in effects:
            attribute = effect['attribute']
            if attribute in effective_stats:
                effective_stats[attribute] += effect['modifier_value']

        return effective_stats

    async def create_fire_ability(self, ctx, player_id, enemy_id):
        # Deal initial damage
        await self.use_selected_ability(ctx, player_id, enemy_id)
        
        # Apply burning effect
        await self.apply_status_effect(
            target_id=enemy_id,
            effect_type='dot_fire',
            duration=3,
            value=3
        )


# Setup function to load this as an extension
def setup(bot):
    BattleSystem(bot)
#do you see this