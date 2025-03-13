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
        self.active_battles = {}  # Will be deprecated in favor of database storage

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

        # Create all action buttons
        buttons = [
            Button(
                style=ButtonStyle.PRIMARY,
                label="Attack",
                custom_id=f"attack_{player_id}_{enemy['enemyid']}"
            ),
            Button(
                style=ButtonStyle.SECONDARY,
                label="Use Ability",
                custom_id=f"ability_{player_id}_{enemy['enemyid']}"
            ),
            Button(
                style=ButtonStyle.DANGER,
                label="Flee Battle",
                custom_id=f"flee_{player_id}_{enemy['enemyid']}"
            )
        ]

        await ctx.send(embeds=[embed], components=[buttons], ephemeral=True)

    async def start_hunt_battle(self, ctx: SlashContext, player_id: int, location_id: int):
        """Start a hunt battle, handling both solo and party cases."""
        # Check if player is in a party
        party = await self.db.fetchrow("""
            SELECT p.* FROM parties p
            JOIN party_members pm ON p.party_id = pm.party_id
            WHERE pm.player_id = $1 AND p.is_active = true
        """, player_id)

        # Default to solo battle if no party or if party check fails
        is_solo = True
        if party:
            try:
                # Get party members
                party_members = await self.db.fetch("""
                    SELECT player_id FROM party_members 
                    WHERE party_id = $1
                """, party['party_id'])
                
                if len(party_members) > 1:  # If there are other members in the party
                    is_solo = False
            except Exception as e:
                print(f"[Debug] Party check failed: {e}")
                is_solo = True  # Default to solo if party check fails
        
        # Create a new battle instance
        instance_id = await self.create_battle_instance(
            ctx, 
            location_id, 
            'solo' if is_solo else 'party',
            1 if is_solo else party['max_size']
        )
        
        # Add the player to the instance
        await self.add_player_to_instance(instance_id, player_id, True)

        # If it's a party battle, add other members
        if not is_solo:
            for member in party_members:
                if member['player_id'] != player_id:  # Skip the initiating player
                    await self.add_player_to_instance(instance_id, member['player_id'], False)

        # Fetch and spawn enemies
        enemy_count = 1 if is_solo else len(party_members)
        enemies = await self.db.fetch("""
            SELECT * FROM enemies 
            WHERE locationid = $1 
            ORDER BY RANDOM() 
            LIMIT $2
        """, location_id, enemy_count)
        
        if not enemies:
            await ctx.send("No enemies to hunt here.", ephemeral=True)
            await self.end_battle_instance(instance_id)
            return

        # Spawn enemies in the instance
        for enemy in enemies:
            await self.spawn_enemy_in_instance(instance_id, enemy['enemyid'])

        # Get the complete battle state
        battle_state = await self.get_instance_state(instance_id)
        
        if not battle_state:
            await ctx.send("Error: Could not initialize battle.", ephemeral=True)
            return

        # Store instance ID in active_battles
        self.active_battles[player_id] = {
            'instance_id': instance_id,
            'enemy': enemies[0]  # Store first enemy for reference
        }

        # Create battle status embed
        embed = Embed(
            title="Battle Started!",
            description="A new battle has begun!",
            color=0xFF0000
        )

        # Add player field
        player_data = await self.db.fetchrow("""
            SELECT 
                pd.*,
                psv.total_health,
                psv.total_mana
            FROM player_data pd
            JOIN player_stats_view psv ON pd.playerid = psv.playerid
            WHERE pd.playerid = $1
        """, player_id)
        
        if player_data:
            embed.add_field(
                name="Player",
                value=f"Health: {player_data['health']}\nMana: {player_data['mana']}",
                inline=True
            )

        # Add enemy fields
        for enemy in enemies:
            embed.add_field(
                name=enemy['name'],
                value=f"Health: {enemy['health']}",
                inline=True
            )

        # Send battle status and prompt for action
        await ctx.send(embeds=[embed], ephemeral=True)
        
        # Prompt for player action
        await self.prompt_player_action(
            ctx,
            player_id,
            player_data['health'],
            enemies[0],  # Use first enemy for now
            enemies[0]['health'],
            self.extract_attributes(await self.db.fetchrow("""
                SELECT * FROM player_stats_view WHERE playerid = $1
            """, player_id)),
            self.extract_attributes(enemies[0]),
            {},  # Resistances will be added later
            {}
        )

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
        instance_id = battle_data['instance_id']

        # Get battle state
        battle_state = await self.get_instance_state(instance_id)
        if not battle_state:
            await ctx.send("Error: Could not retrieve battle state.", ephemeral=True)
            return

        # Find the target enemy in the battle
        target_enemy = None
        for battle_enemy in battle_state['enemies']:
            enemy = await self.db.fetchrow("""
                SELECT * FROM enemies WHERE enemyid = $1
            """, battle_enemy['enemy_id'])
            if enemy['enemyid'] == enemy_id:
                target_enemy = enemy
                target_battle_enemy = battle_enemy
                break

        if not target_enemy:
            await ctx.send("Target enemy not found in battle.", ephemeral=True)
            return

        # Calculate attack roll results
        hit_success, is_critical, is_blocked = await self.calculate_attack_roll(
            player_stats, target_enemy
        )

        if is_blocked:
            await ctx.send(f"{target_enemy['name']} blocked your attack!", ephemeral=True)
        elif not hit_success:
            await ctx.send(f"You missed your attack on {target_enemy['name']}!", ephemeral=True)
        else:
            # Calculate damage
            base_damage = player_stats['total_strength']
            damage_dealt = await self.calculate_damage(
                player_stats, target_enemy,
                'physical', base_damage, is_critical
            )

            # Update enemy's health in the battle instance
            new_health = target_battle_enemy['current_health'] - damage_dealt
            await self.update_battle_health(
                instance_id, 'enemy', target_battle_enemy['battle_enemy_id'], new_health
            )

            # Send combat message
            message = f"You dealt {damage_dealt} damage to {target_enemy['name']}"
            if is_critical:
                message += " (Critical Hit!)"
            message += f". Remaining enemy health: {new_health}"
            await ctx.send(message, ephemeral=True)

            # Broadcast attack to other party members
            if battle_state['instance_type'] == 'party':
                for participant in battle_state['participants']:
                    if participant['player_id'] != player_id:
                        user = await self.bot.fetch_user(participant['player_id'])
                        if user:
                            attacker = await self.db.fetchrow("""
                                SELECT username FROM player_data WHERE playerid = $1
                            """, player_id)
                            await user.send(
                                f"{attacker['username']} dealt {damage_dealt} damage to {target_enemy['name']}! " +
                                f"(Remaining health: {new_health})"
                            )

        # Enemy's turn - in party battles, enemies attack random participants
        player_survived = True
        if battle_state['instance_type'] == 'party':
            for battle_enemy in battle_state['enemies']:
                if battle_enemy['current_health'] > 0:
                    # Select random target from participants
                    target_participant = random.choice(battle_state['participants'])
                    survived = await self.enemy_attack(
                        ctx, 
                        target_participant['player_id'], 
                        await self.db.fetchrow("""
                            SELECT * FROM enemies WHERE enemyid = $1
                        """, battle_enemy['enemy_id'])
                    )
                    player_survived = player_survived and survived
        else:
            player_survived = await self.enemy_attack(ctx, player_id, target_enemy)

        if player_survived:
            # Refresh battle status after all enemies have attacked
            battle_state = await self.get_instance_state(instance_id)
            await self.refresh_battle_status(ctx, battle_state, player_id)

        # Check combat end
        await self.handle_combat_end(ctx, player_id, target_enemy)

    async def enemy_attack(self, ctx, player_id, enemy):
        # Fetch player stats from the view
        player_stats = await self.db.fetchrow("""
            SELECT * FROM player_stats_view WHERE playerid = $1
        """, player_id)
        
        if not player_stats:
            await ctx.send("Error: Could not retrieve player stats.", ephemeral=True)
            return False

        player_stats = dict(player_stats)
        
        # Get current health from player_data
        current_stats = await self.db.fetchrow("""
            SELECT health FROM player_data WHERE playerid = $1
        """, player_id)

        if not current_stats:
            await ctx.send("Error: Could not retrieve current stats.", ephemeral=True)
            return False
        
        # Get battle data and process enemy effects
        battle_data = self.active_battles.get(player_id)
        if battle_data and 'enemy_effects' in battle_data:
            current_time = datetime.now()
            active_effects = []
            additional_damage = 0
            
            # Process each effect
            for effect in battle_data['enemy_effects']:
                effect_duration = (current_time - effect['start_time']).total_seconds()
                if effect_duration <= effect['duration']:
                    active_effects.append(effect)
                    # Handle damage over time effects
                    if effect['type'].startswith('dot_'):
                        additional_damage += effect['value']
                        await ctx.send(f"{enemy['name']} takes {effect['value']} damage from {effect['type']}!", ephemeral=True)
            
            # Update active effects list
            battle_data['enemy_effects'] = active_effects
            
            # Apply damage from effects
            if additional_damage > 0:
                battle_data['enemy_health'] -= additional_damage
                await ctx.send(f"{enemy['name']} took {additional_damage} total damage from effects! Remaining health: {battle_data['enemy_health']}", ephemeral=True)
        
        # Calculate attack roll results for enemy
        hit_success, is_critical, is_blocked = await self.calculate_attack_roll(
            enemy, player_stats
        )

        if is_blocked:
            await ctx.send(f"You blocked {enemy['name']}'s attack!", ephemeral=True)
            return True
        elif not hit_success:
            await ctx.send(f"{enemy['name']} missed their attack!", ephemeral=True)
            return True
        else:
            # Calculate damage with status effects
            base_damage = enemy['strength']
            damage_received = await self.calculate_damage(
                enemy, player_stats,
                'physical', base_damage, is_critical
            )
            
            # Apply any damage-over-time effects on player
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

            # Return whether player survived
            return new_health > 0

        # Clean up expired effects
        await self.db.execute("""
            DELETE FROM temporary_effects
            WHERE player_id = $1
            AND start_time + (duration * interval '1 second') <= NOW()
        """, player_id)

        return True

    async def handle_combat_end(self, ctx: SlashContext, player_id: int, enemy):
        """Handles the ending of combat when either the player or enemy reaches zero health."""
        if player_id not in self.active_battles:
            return  # If no active battle, stop further processing

        battle_data = self.active_battles[player_id]
        instance_id = battle_data['instance_id']
        battle_state = await self.get_instance_state(instance_id)

        if not battle_state:
            await ctx.send("Error: Could not retrieve battle state.", ephemeral=True)
            return

        # Check if all enemies are defeated
        all_enemies_defeated = True
        for battle_enemy in battle_state['enemies']:
            if battle_enemy['current_health'] > 0:
                all_enemies_defeated = False
                break

        # Check if all party members are defeated
        all_players_defeated = True
        for participant in battle_state['participants']:
            if participant['current_health'] > 0:
                all_players_defeated = False
                break

        if all_enemies_defeated and all_players_defeated:
            # Draw - both sides defeated
            await ctx.send("Both sides have fallen! The battle ends in a draw!", ephemeral=True)
            await self.end_battle_instance(instance_id)
            
            # Clean up active battles for all participants
            for participant in battle_state['participants']:
                if participant['player_id'] in self.active_battles:
                    del self.active_battles[participant['player_id']]
            return

        if all_enemies_defeated:
            # Victory message
            await ctx.send("All enemies have been defeated!", ephemeral=True)
            
            # Handle rewards for each participant
            for participant in battle_state['participants']:
                if participant['current_health'] > 0:  # Only reward surviving members
                    await self.handle_enemy_defeat(ctx, participant['player_id'], enemy['enemyid'])

            # Clean up
            await self.end_battle_instance(instance_id)
            for participant in battle_state['participants']:
                if participant['player_id'] in self.active_battles:
                    del self.active_battles[participant['player_id']]
            return

        if all_players_defeated:
            # Defeat message
            await ctx.send("All party members have fallen!", ephemeral=True)
            
            # Set health to 0 for all participants
            for participant in battle_state['participants']:
                await self.db.execute("""
                    UPDATE player_data
                    SET health = 0
                    WHERE playerid = $1
                """, participant['player_id'])

            # Clean up
            await self.end_battle_instance(instance_id)
            for participant in battle_state['participants']:
                if participant['player_id'] in self.active_battles:
                    del self.active_battles[participant['player_id']]
            return

        # If battle continues and this is a party battle, check if we need to update the UI for anyone
        if battle_state['instance_type'] == 'party':
            for participant in battle_state['participants']:
                if participant['current_health'] > 0:  # Only prompt active players
                    # Create a new context for each participant
                    member_ctx = await self.bot.get_context(ctx.message)
                    member_ctx.author = await self.bot.fetch_user(participant['player_id'])
                    
                    # Get their stats
                    player_stats = await self.db.fetchrow("""
                        SELECT * FROM player_stats_view WHERE playerid = $1
                    """, participant['player_id'])

                    # Find their target enemy (for now, use the first living enemy)
                    target_enemy = None
                    for battle_enemy in battle_state['enemies']:
                        if battle_enemy['current_health'] > 0:
                            enemy_data = await self.db.fetchrow("""
                                SELECT * FROM enemies WHERE enemyid = $1
                            """, battle_enemy['enemy_id'])
                            target_enemy = enemy_data
                            target_battle_enemy = battle_enemy
                            break

                    if target_enemy:
                        await self.prompt_player_action(
                            member_ctx,
                            participant['player_id'],
                            participant['current_health'],
                            target_enemy,
                            target_battle_enemy['current_health'],
                            self.extract_attributes(player_stats),
                            self.extract_attributes(target_enemy),
                            self.extract_resistances(player_stats),
                            self.extract_resistances(target_enemy)
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

            # Get battle instance data
            if player_id not in self.active_battles:
                await ctx.send("No active battle found.", ephemeral=True)
                return

            battle_data = self.active_battles[player_id]
            instance_id = battle_data['instance_id']
            battle_state = await self.get_instance_state(instance_id)

            # Find the target enemy in the battle
            target_enemy = None
            for battle_enemy in battle_state['enemies']:
                enemy = await self.db.fetchrow("""
                    SELECT * FROM enemies WHERE enemyid = $1
                """, battle_enemy['enemy_id'])
                if enemy['enemyid'] == enemy_id:
                    target_enemy = enemy
                    target_battle_enemy = battle_enemy
                    break

            if not target_enemy:
                await ctx.send("Target enemy not found in battle.", ephemeral=True)
                return

            # Get player stats and check mana
            player_stats = await self.db.fetchrow("""
                SELECT * FROM player_stats_view WHERE playerid = $1
            """, player_id)

            if not player_stats:
                await ctx.send("Error: Could not retrieve player stats.", ephemeral=True)
                return

            player_stats = dict(player_stats)

            # Get current participant data
            participant = None
            for p in battle_state['participants']:
                if p['player_id'] == player_id:
                    participant = p
                    break

            if not participant:
                await ctx.send("Error: Could not find player in battle.", ephemeral=True)
                return

            # Check if player has enough mana
            if participant['current_mana'] < ability['mana_cost']:
                await ctx.send("Not enough mana to use this ability!", ephemeral=True)
                return

            # Calculate ability hit success
            hit_success, is_critical = await self.calculate_ability_hit(
                player_stats, target_enemy, ability['ability_type']
            )

            if not hit_success:
                await ctx.send(f"Your {ability['name']} missed {target_enemy['name']}!", ephemeral=True)
            else:
                # Calculate damage
                base_damage = ability.get(f"{ability['ability_type']}_damage", ability.get('damage', 5))
                if ability['ability_type'] in ['fire', 'ice', 'lightning', 'water', 'earth', 'air', 'light', 'dark', 'magic']:
                    base_damage += player_stats['total_intelligence'] * 0.5

                damage_dealt = await self.calculate_damage(
                    player_stats, target_enemy,
                    ability['ability_type'], base_damage, is_critical
                )

                # Update enemy health
                new_health = target_battle_enemy['current_health'] - damage_dealt
                await self.update_battle_health(
                    instance_id, 'enemy', target_battle_enemy['battle_enemy_id'], new_health
                )

                # Update player's mana
                new_mana = participant['current_mana'] - ability['mana_cost']
                await self.update_battle_health(
                    instance_id, 'player', player_id, participant['current_health'], new_mana
                )

                # Send combat message
                message = f"You used {ability['name']} and dealt {damage_dealt} damage"
                if is_critical:
                    message += " (Critical Hit!)"
                message += f". Remaining enemy health: {new_health}"
                message += f"\nMana remaining: {new_mana}"
                await ctx.send(message, ephemeral=True)

                # Handle status effects
                if ability.get('status_effect'):
                    effect = {
                        'type': ability['status_effect'],
                        'duration': ability.get('effect_duration', 3),
                        'value': ability.get('effect_value', 0),
                        'start_time': datetime.now()
                    }
                    await self.apply_battle_effect(
                        instance_id,
                        'enemy',
                        target_battle_enemy['battle_enemy_id'],
                        effect['type'],
                        effect['value'],
                        effect['duration']
                    )
                    await ctx.send(f"{target_enemy['name']} is affected by {ability['status_effect']}!", ephemeral=True)

            # Enemy's turn - in party battles, enemies attack random participants
            player_survived = True
            if battle_state['instance_type'] == 'party':
                for battle_enemy in battle_state['enemies']:
                    if battle_enemy['current_health'] > 0:
                        # Select random target from participants
                        target_participant = random.choice(battle_state['participants'])
                        survived = await self.enemy_attack(
                            ctx, 
                            target_participant['player_id'], 
                            await self.db.fetchrow("""
                                SELECT * FROM enemies WHERE enemyid = $1
                            """, battle_enemy['enemy_id'])
                        )
                        player_survived = player_survived and survived
            else:
                player_survived = await self.enemy_attack(ctx, player_id, target_enemy)

            if player_survived:
                # Refresh battle status after all enemies have attacked
                battle_state = await self.get_instance_state(instance_id)
                await self.refresh_battle_status(ctx, battle_state, player_id)

            # Check combat end
            await self.handle_combat_end(ctx, player_id, target_enemy)

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

    async def create_battle_instance(self, ctx: SlashContext, location_id: int, instance_type: str = 'solo', max_players: int = 1):
        """Create a new battle instance."""
        instance = await self.db.fetchrow("""
            INSERT INTO battle_instances (instance_type, location_id, max_players)
            VALUES ($1, $2, $3)
            RETURNING instance_id
        """, instance_type, location_id, max_players)
        
        return instance['instance_id']

    async def add_player_to_instance(self, instance_id: int, player_id: int, is_leader: bool = False):
        """Add a player to a battle instance."""
        # Get player's current stats
        player_stats = await self.db.fetchrow("""
            SELECT health, mana FROM player_data WHERE playerid = $1
        """, player_id)

        await self.db.execute("""
            INSERT INTO battle_participants 
            (instance_id, player_id, is_leader, current_health, current_mana)
            VALUES ($1, $2, $3, $4, $5)
        """, instance_id, player_id, is_leader, player_stats['health'], player_stats['mana'])

    async def spawn_enemy_in_instance(self, instance_id: int, enemy_id: int, is_boss: bool = False):
        """Spawn an enemy in a battle instance."""
        enemy = await self.db.fetchrow("""
            SELECT * FROM enemies WHERE enemyid = $1
        """, enemy_id)

        await self.db.execute("""
            INSERT INTO battle_enemies 
            (instance_id, enemy_id, current_health, is_boss)
            VALUES ($1, $2, $3, $4)
        """, instance_id, enemy_id, enemy['health'], is_boss)

    async def apply_battle_effect(self, instance_id: int, target_type: str, target_id: int, 
                                effect_type: str, effect_value: int, duration: int):
        """Apply an effect in a battle instance."""
        await self.db.execute("""
            INSERT INTO battle_effects 
            (instance_id, target_type, target_id, effect_type, effect_value, duration)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, instance_id, target_type, target_id, effect_type, effect_value, duration)

    async def get_active_battle_effects(self, instance_id: int, target_type: str, target_id: int):
        """Get all active effects for a target in a battle."""
        return await self.db.fetch("""
            SELECT * FROM battle_effects 
            WHERE instance_id = $1 
            AND target_type = $2 
            AND target_id = $3 
            AND start_time + (duration * interval '1 second') > NOW()
        """, instance_id, target_type, target_id)

    async def update_battle_health(self, instance_id: int, target_type: str, target_id: int, new_health: int, new_mana: int = None):
        """Update health and optionally mana for a participant in battle."""
        if target_type == 'player':
            if new_mana is not None:
                await self.db.execute("""
                    UPDATE battle_participants 
                    SET current_health = $1, current_mana = $2
                    WHERE instance_id = $3 AND player_id = $4
                """, new_health, new_mana, instance_id, target_id)
            else:
                await self.db.execute("""
                    UPDATE battle_participants 
                    SET current_health = $1
                    WHERE instance_id = $2 AND player_id = $3
                """, new_health, instance_id, target_id)
        else:
            await self.db.execute("""
                UPDATE battle_enemies 
                SET current_health = $1 
                WHERE instance_id = $2 AND battle_enemy_id = $3
            """, new_health, instance_id, target_id)

    async def get_instance_state(self, instance_id: int):
        """Get the complete state of a battle instance."""
        # First get the base instance data
        instance = await self.db.fetchrow("""
            SELECT * FROM battle_instances WHERE instance_id = $1
        """, instance_id)
        
        if not instance:
            return None
            
        # Get participants
        participants = await self.db.fetch("""
            SELECT * FROM battle_participants WHERE instance_id = $1
        """, instance_id)
        
        # Get enemies
        enemies = await self.db.fetch("""
            SELECT * FROM battle_enemies WHERE instance_id = $1
        """, instance_id)
        
        # Get effects
        effects = await self.db.fetch("""
            SELECT * FROM battle_effects WHERE instance_id = $1
        """, instance_id)
        
        # Combine all data
        battle_state = {
            **dict(instance),
            'participants': participants,
            'enemies': enemies,
            'effects': effects
        }
        
        return battle_state

    async def end_battle_instance(self, instance_id: int):
        """End a battle instance and clean up."""
        await self.db.execute("""
            UPDATE battle_instances 
            SET is_active = false 
            WHERE instance_id = $1
        """, instance_id)

    async def refresh_battle_status(self, ctx: SlashContext, battle_state, player_id: int):
        """Refresh the battle status embed with current health/mana values and action buttons."""
        embed = Embed(
            title="Battle Status",
            description="Current battle state:",
            color=0xFF0000
        )

        # Add player field(s)
        for participant in battle_state['participants']:
            if participant['player_id'] == player_id:
                embed.add_field(
                    name="Player",
                    value=f"Health: {participant['current_health']}\nMana: {participant['current_mana']}",
                    inline=True
                )
                break

        # Add enemy fields
        for battle_enemy in battle_state['enemies']:
            enemy = await self.db.fetchrow("""
                SELECT name FROM enemies WHERE enemyid = $1
            """, battle_enemy['enemy_id'])
            if enemy:
                embed.add_field(
                    name=enemy['name'],
                    value=f"Health: {battle_enemy['current_health']}",
                    inline=True
                )

        # Create action buttons
        buttons = [
            Button(
                style=ButtonStyle.PRIMARY,
                label="Attack",
                custom_id=f"attack_{player_id}_{battle_state['enemies'][0]['enemy_id']}"
            ),
            Button(
                style=ButtonStyle.SECONDARY,
                label="Use Ability",
                custom_id=f"ability_{player_id}_{battle_state['enemies'][0]['enemy_id']}"
            ),
            Button(
                style=ButtonStyle.DANGER,
                label="Flee Battle",
                custom_id=f"flee_{player_id}_{battle_state['enemies'][0]['enemy_id']}"
            )
        ]

        # Send embed with all buttons in one row
        await ctx.send(embeds=[embed], components=[buttons], ephemeral=True)

    @component_callback(re.compile(r"^flee_\d+_\d+$"))
    async def flee_button_handler(self, ctx: ComponentContext):
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
        instance_id = battle_data['instance_id']

        # Get battle state
        battle_state = await self.get_instance_state(instance_id)
        if not battle_state:
            await ctx.send("Error: Could not retrieve battle state.", ephemeral=True)
            return

        # Calculate player's agility check (d20 + agility modifier)
        player_agility = player_stats.get('total_agility', player_stats.get('agility', 0))
        player_agility_mod = (player_agility - 10) // 2  # D&D-style ability modifier
        player_roll = self.roll_dice() + max(player_agility_mod, 0)  # Minimum of +0 modifier
        
        await ctx.send(f"You attempt to flee! (Agility Check: {player_roll})", ephemeral=True)

        # Track which enemies beat the player's roll
        successful_enemies = []
        
        # Each enemy makes an opposed agility check
        for battle_enemy in battle_state['enemies']:
            if battle_enemy['current_health'] <= 0:
                continue

            enemy = await self.db.fetchrow("""
                SELECT * FROM enemies WHERE enemyid = $1
            """, battle_enemy['enemy_id'])
            
            if not enemy:
                continue

            enemy_agility_mod = (enemy['agility'] - 10) // 2
            enemy_roll = self.roll_dice() + max(enemy_agility_mod, 0)
            
            await ctx.send(f"{enemy['name']} tries to stop you! (Agility Check: {enemy_roll})", ephemeral=True)
            
            if enemy_roll >= player_roll:  # Enemy succeeds if they match or beat player's roll
                successful_enemies.append(enemy)

        # If no enemies beat the player's roll, escape is successful
        if not successful_enemies:
            await ctx.send("You successfully escaped from battle!", ephemeral=True)
            await self.end_battle_instance(instance_id)
            del self.active_battles[player_id]
            return
        else:
            await ctx.send(f"Failed to escape! {len(successful_enemies)} enemies caught up to you!", ephemeral=True)
            
            # Only enemies that beat the roll get to attack
            player_survived = True
            for enemy in successful_enemies:
                if not player_survived:
                    break
                    
                player_survived = await self.enemy_attack(ctx, player_id, enemy)
                
            if player_survived:
                # Refresh battle status after enemy attacks
                battle_state = await self.get_instance_state(instance_id)
                await self.refresh_battle_status(ctx, battle_state, player_id)

            # Check combat end
            await self.handle_combat_end(ctx, player_id, successful_enemies[0])  # Use first enemy for end check

# Setup function to load this as an extension
def setup(bot):
    BattleSystem(bot)
