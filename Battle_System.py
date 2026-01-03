from interactions import SlashContext, Extension, Button, ButtonStyle, ComponentContext, component_callback, Embed, StringSelectOption, StringSelectMenu, ActionRow
import random
import asyncio
import re
import logging
from datetime import datetime

class BattleSystem(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    def parse_dice(self, dice_string):
        """
        Parse dice notation like "1d6", "2d4+2", "1d8-1"
        Returns: (num_dice, sides, modifier)
        """
        if not dice_string:
            return (0, 0, 0)
        
        # Remove whitespace
        dice_string = dice_string.strip()
        
        # Handle modifiers
        modifier = 0
        if '+' in dice_string:
            parts = dice_string.split('+')
            dice_string = parts[0]
            modifier = int(parts[1])
        elif '-' in dice_string:
            parts = dice_string.split('-')
            dice_string = parts[0]
            modifier = -int(parts[1])
        
        # Parse dice part (e.g., "1d6")
        if 'd' in dice_string:
            num_dice, sides = map(int, dice_string.split('d'))
        else:
            # Just a number (e.g., "5" = 5 damage, no roll)
            return (0, 0, int(dice_string))
        
        return (num_dice, sides, modifier)
    
    def roll_dice_notation(self, dice_string):
        """
        Roll dice based on notation.
        Returns total rolled value (0-X for damage dice).
        """
        num_dice, sides, modifier = self.parse_dice(dice_string)
        
        if num_dice == 0 and sides == 0:
            # Just a flat modifier
            return modifier
        
        total = 0
        for _ in range(num_dice):
            total += self.roll_dice(sides, start=0)  # 0-X for damage
        
        return total + modifier
    
    def format_damage_message(self, damage_by_type, total_damage):
        """
        Format damage breakdown for display.
        Returns string like "15 damage (8 slashing, 4 crushing, 3 piercing)"
        """
        if not damage_by_type or len(damage_by_type) == 1:
            # Single damage type or old system
            return f"{total_damage} damage"
        
        # Multiple damage types - show breakdown
        damage_parts = []
        for damage_type, amount in damage_by_type.items():
            if amount > 0:
                damage_parts.append(f"{amount} {damage_type}")
        
        if damage_parts:
            return f"{total_damage} damage ({', '.join(damage_parts)})"
        else:
            return f"{total_damage} damage"
    
    def get_damage_type_multiplier(self, damage_type, attacker_stats):
        """
        Get multiplier for a specific damage type based on attacker stats.
        Formula: 1.0 + (stat / 100) - scales per stat point
        At 100 stat = 2.0x, at 50 stat = 1.5x, at -10 stat = 0.9x
        """
        if damage_type == 'piercing':
            dex = attacker_stats.get('total_dexterity', attacker_stats.get('dexterity', 0))
            return 1.0 + (dex / 100.0)
        
        elif damage_type == 'crushing':
            str_stat = attacker_stats.get('total_strength', attacker_stats.get('strength', 0))
            return 1.0 + (str_stat / 100.0)
        
        elif damage_type == 'slashing':
            str_stat = attacker_stats.get('total_strength', attacker_stats.get('strength', 0))
            dex = attacker_stats.get('total_dexterity', attacker_stats.get('dexterity', 0))
            avg_stat = (str_stat + dex) / 2.0
            return 1.0 + (avg_stat / 100.0)
        
        elif damage_type in ['fire', 'ice', 'lightning', 'water', 'earth', 'air', 'light', 'dark', 'magic', 'poison']:
            # All magic/elemental damage types scale with Intelligence
            int_stat = attacker_stats.get('total_intelligence', attacker_stats.get('intelligence', 0))
            return 1.0 + (int_stat / 100.0)
        
        else:
            return 1.0  # No multiplier for unknown types
    
    async def get_equipped_weapon_dice(self, player_id):
        """
        Get dice notation for all equipped weapons (excluding tools in tool belt).
        Only counts weapons in combat slots (1H_weapon, 2H_weapon, left_hand), not tool belt slots.
        Returns a dict of {damage_type: dice_string} for all damage types present.
        """
        weapons = await self.db.fetch("""
            SELECT 
                COALESCE(i.piercing_damage, '') as piercing_damage,
                COALESCE(i.crushing_damage, '') as crushing_damage,
                COALESCE(i.slashing_damage, '') as slashing_damage,
                COALESCE(i.fire_damage, '') as fire_damage,
                COALESCE(i.ice_damage, '') as ice_damage,
                COALESCE(i.lightning_damage, '') as lightning_damage,
                COALESCE(i.water_damage, '') as water_damage,
                COALESCE(i.earth_damage, '') as earth_damage,
                COALESCE(i.air_damage, '') as air_damage,
                COALESCE(i.light_damage, '') as light_damage,
                COALESCE(i.dark_damage, '') as dark_damage,
                COALESCE(i.magic_damage, '') as magic_damage,
                COALESCE(i.poison_damage, '') as poison_damage
            FROM inventory inv
            JOIN items i ON inv.itemid = i.itemid
            WHERE inv.playerid = $1 
            AND inv.isequipped = true
            AND inv.slot IN ('1H_weapon', '2H_weapon', 'left_hand')
            AND i.type = 'Weapon'
        """, player_id)
        
        # Combine dice from all weapons (now stored in _damage columns)
        combined_dice = {}
        damage_types = ['piercing', 'crushing', 'slashing', 'fire', 'ice', 'lightning', 
                       'water', 'earth', 'air', 'light', 'dark', 'magic', 'poison']
        
        for weapon in weapons:
            for damage_type in damage_types:
                dice = weapon.get(f'{damage_type}_damage', '')
                if dice and dice.strip():
                    # If multiple weapons have same type, we'll combine them
                    # For now, just take the first one (can enhance later to combine)
                    if damage_type not in combined_dice:
                        combined_dice[damage_type] = dice
        
        return combined_dice
    
    async def get_equipped_weapon_damage(self, player_id):
        """
        DEPRECATED: Use get_equipped_weapon_dice and calculate_damage_with_dice instead.
        Kept for backwards compatibility during migration.
        """
        weapons = await self.db.fetch("""
            SELECT 
                COALESCE(i.slashing_damage, 0) as slashing_damage,
                COALESCE(i.piercing_damage, 0) as piercing_damage,
                COALESCE(i.crushing_damage, 0) as crushing_damage,
                COALESCE(i.dark_damage, 0) as dark_damage
            FROM inventory inv
            JOIN items i ON inv.itemid = i.itemid
            WHERE inv.playerid = $1 
            AND inv.isequipped = true
            AND inv.slot IN ('1H_weapon', '2H_weapon', 'left_hand')
            AND i.type = 'Weapon'
        """, player_id)
        
        total_damage = {
            'slashing': 0,
            'piercing': 0,
            'crushing': 0,
            'dark': 0
        }
        
        for weapon in weapons:
            total_damage['slashing'] += weapon['slashing_damage'] or 0
            total_damage['piercing'] += weapon['piercing_damage'] or 0
            total_damage['crushing'] += weapon['crushing_damage'] or 0
            total_damage['dark'] += weapon['dark_damage'] or 0
        
        return total_damage

    @staticmethod
    def roll_dice(sides=20, start=0):
        """
        Simulates a dice roll with given sides.
        Default: d20 (1-20) for attack rolls
        For damage: start=0 for 0-X rolls
        """
        if start == 0:
            return random.randint(0, sides)  # 0-X inclusive
        else:
            return random.randint(start, sides)  # start-X inclusive

    @component_callback(re.compile(r"^hunt_\d+$"))
    async def hunt_button_handler(self, ctx: ComponentContext):
        # Extract player ID from the custom ID
        original_user_id = int(ctx.custom_id.split("_")[1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        # For party battles, we need to send to channel, so don't defer ephemerally
        # Check if player is in a party first
        player_id = await self.db.get_or_create_player(ctx.author.id)
        party = await self.db.fetchrow("""
            SELECT p.* FROM parties p
            JOIN party_members pm ON p.party_id = pm.party_id
            WHERE pm.player_id = $1 AND p.is_active = true
        """, player_id)
        
        # Defer - ephemeral for solo, not ephemeral for party (so channel message works)
        is_party = party is not None
        await ctx.defer(ephemeral=not is_party)

        # Get player data and proceed with hunting logic
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
            title=f"⚔️ Battle with {enemy['name']}",
            description=f"**Your Turn!**\nYour health: {player_health}\n{enemy['name']}'s health: {enemy_health}",
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
                custom_id=f"flee_{player_id}"
            )
        ]

        if ctx:
            await ctx.send(embeds=[embed], components=[buttons], ephemeral=True)
        else:
            # No context - send as DM
            try:
                discord_id = await self.db.fetchval("""
                    SELECT discord_id FROM players WHERE playerid = $1
                """, player_id)
                if discord_id:
                    user = await self.bot.fetch_user(discord_id)
                    if user:
                        await user.send(embeds=[embed], components=[buttons])
            except Exception as e:
                logging.error(f"Error sending battle prompt: {e}")

    async def start_hunt_battle(self, ctx, player_id: int, location_id: int):
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

        # Initialize turn order for party battles
        if not is_solo:
            first_turn_player = await self.initialize_turn_order(instance_id)
        else:
            first_turn_player = player_id
            await self.db.execute("""
                UPDATE battle_instances
                SET current_turn_player_id = $1, turn_order = ARRAY[$1::INTEGER]
                WHERE instance_id = $2
            """, player_id, instance_id)

        # Instance ID is stored in database, no need for active_battles

        # Create battle announcement embed for channel
        if not is_solo:
            # Party battle
            battle_embed = Embed(
                title="⚔️ Battle Started!",
                description="A new battle has begun!",
                color=0xFF0000
            )
            
            # Get usernames for display
            participant_info = []
            for p in battle_state['participants']:
                try:
                    discord_id = await self.db.fetchval("""
                        SELECT discord_id FROM players WHERE playerid = $1
                    """, p['player_id'])
                    if discord_id:
                        user = await self.bot.fetch_user(discord_id)
                        username = user.display_name if user else f"Player {p['player_id']}"
                    else:
                        username = f"Player {p['player_id']}"
                except:
                    username = f"Player {p['player_id']}"
                
                p_data = await self.db.fetchrow("""
                    SELECT health, mana FROM player_data WHERE playerid = $1
                """, p['player_id'])
                
                if p_data:
                    is_current_turn = " 👈 Your Turn" if p['player_id'] == first_turn_player else ""
                    battle_embed.add_field(
                        name=f"{username}{is_current_turn}",
                        value=f"Health: {p_data['health']}\nMana: {p_data['mana']}",
                        inline=True
                    )
                    participant_info.append({
                        'player_id': p['player_id'],
                        'username': username,
                        'discord_id': discord_id if 'discord_id' in locals() else None
                    })
            
            # Add enemy fields
            for enemy in enemies:
                battle_embed.add_field(
                    name=enemy['name'],
                    value=f"Health: {enemy['health']}",
                    inline=True
                )
            
            # Show turn order
            if len(party_members) > 1:
                turn_order_list = await self.db.fetchval("""
                    SELECT turn_order FROM battle_instances WHERE instance_id = $1
                """, instance_id)
                if turn_order_list:
                    # Get usernames for turn order
                    turn_order_names = []
                    for pid in turn_order_list:
                        info = next((p for p in participant_info if p['player_id'] == pid), None)
                        turn_order_names.append(info['username'] if info else f"Player {pid}")
                    battle_embed.set_footer(text=f"Turn Order: {' → '.join(turn_order_names)}")
            
            # Get channel - ComponentContext might need different access
            channel = None
            channel_id = None
            if hasattr(ctx, 'channel') and ctx.channel:
                channel = ctx.channel
                channel_id = ctx.channel.id
            elif hasattr(ctx, 'guild') and ctx.guild:
                # Try to get channel from message if available
                if hasattr(ctx, 'message') and ctx.message and hasattr(ctx.message, 'channel'):
                    channel = ctx.message.channel
                    channel_id = ctx.message.channel.id
            
            # Send battle announcement to channel (not ephemeral so all can see)
            if channel:
                battle_message = await channel.send(embeds=[battle_embed])
            else:
                # Fallback - try ctx.send
                battle_message = await ctx.send(embeds=[battle_embed])
                channel_id = battle_message.channel.id if hasattr(battle_message, 'channel') else None
            
            # Store channel and message ID in battle instance for later interactions
            await self.db.execute("""
                UPDATE battle_instances
                SET channel_id = $1, message_id = $2
                WHERE instance_id = $3
            """, channel_id, battle_message.id, instance_id)
            
            # Also send DMs to party members as backup notification
            for member in party_members:
                try:
                    member_discord_id = await self.db.fetchval("""
                        SELECT discord_id FROM players WHERE playerid = $1
                    """, member['player_id'])
                    
                    if member_discord_id:
                        member_user = await self.bot.fetch_user(member_discord_id)
                        if member_user:
                            channel_mention = f"<#{channel_id}>" if channel_id else "the channel"
                            dm_embed = Embed(
                                title="⚔️ Battle Started!",
                                description=f"A battle has started in {channel_mention}!",
                                color=0xFF0000
                            )
                            dm_embed.add_field(
                                name="Location",
                                value=f"Check {channel_mention} to take your turn!",
                                inline=False
                            )
                            try:
                                await member_user.send(embeds=[dm_embed])
                            except:
                                pass  # Silently fail if DMs disabled
                except Exception as e:
                    logging.error(f"Error sending DM to party member {member['player_id']}: {e}")
            
            # Get channel for turn prompts (outside the loop!)
            channel_for_turns = channel if channel else (ctx.channel if hasattr(ctx, 'channel') and ctx.channel else None)
            
            # Prompt the first player whose turn it is (in the channel) - only once!
            await self.prompt_next_player_turn(instance_id, first_turn_player, channel_for_turns)
        else:
            # Solo battle - simple notification
            embed = Embed(
                title="⚔️ Battle Started!",
                description="A new battle has begun!",
                color=0xFF0000
            )
            
            player_data = await self.db.fetchrow("""
                SELECT health, mana FROM player_data WHERE playerid = $1
            """, player_id)
            
            if player_data:
                embed.add_field(
                    name="You",
                    value=f"Health: {player_data['health']}\nMana: {player_data['mana']}",
                    inline=True
                )
            
            for enemy in enemies:
                embed.add_field(
                    name=enemy['name'],
                    value=f"Health: {enemy['health']}",
                    inline=True
                )
            
            # Get channel for solo battles too
            channel = None
            channel_id = None
            if hasattr(ctx, 'channel') and ctx.channel:
                channel = ctx.channel
                channel_id = ctx.channel.id
            elif hasattr(ctx, 'guild') and ctx.guild:
                if hasattr(ctx, 'message') and ctx.message and hasattr(ctx.message, 'channel'):
                    channel = ctx.message.channel
                    channel_id = ctx.message.channel.id
            
            if channel:
                battle_message = await channel.send(embeds=[embed])
            else:
                battle_message = await ctx.send(embeds=[embed])
                channel_id = battle_message.channel.id if hasattr(battle_message, 'channel') else None
            
            # Store channel and message ID
            await self.db.execute("""
                UPDATE battle_instances
                SET channel_id = $1, message_id = $2
                WHERE instance_id = $3
            """, channel_id, battle_message.id, instance_id)
            
            await self.prompt_next_player_turn(instance_id, player_id, channel)

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

    async def calculate_damage_with_dice(self, attacker_stats: dict, defender_stats: dict,
                                        weapon_dice: dict, is_critical: bool) -> dict:
        """
        Calculate damage with dice rolls and stat multipliers (new hybrid system).
        
        Args:
            weapon_dice: Dict of {damage_type: dice_string}
            Example: {'piercing': '1d1', 'crushing': '1d5', 'slashing': '1d6'}
        
        Returns:
            Dict of {damage_type: final_damage} - damage after all modifiers including resistances
        """
        damage_by_type = {}
        
        # Step 1: Roll dice for each damage type
        for damage_type, dice_string in weapon_dice.items():
            if not dice_string or not dice_string.strip():
                continue
            
            # Roll the dice (0-X for damage)
            base_roll = self.roll_dice_notation(dice_string)
            
            # Step 2: Apply stat multiplier
            multiplier = self.get_damage_type_multiplier(damage_type, attacker_stats)
            damage = base_roll * multiplier
            
            # Step 3: Apply critical hit multiplier (if critical)
            if is_critical:
                attacker_luck = attacker_stats.get('total_luck', attacker_stats.get('luck', 0))
                critical_multiplier = 1.5 + (attacker_luck * 0.01)
                damage *= critical_multiplier
            
            # Step 4: Apply resistance
            resistance_key = f"{damage_type}_resistance"
            total_resistance_key = f"total_{resistance_key}"
            resistance = defender_stats.get(total_resistance_key, defender_stats.get(resistance_key, 0))
            resistance_modifier = 1 - (resistance / 100)
            damage *= resistance_modifier
            
            # Step 5: Apply status effects
            if 'playerid' in attacker_stats:
                status_effects = await self.get_active_effects(attacker_stats['playerid'])
                for effect in status_effects:
                    if effect['attribute'].startswith('damage_bonus_'):
                        damage *= (1 + effect['modifier_value'] / 100)
                    elif effect['attribute'].startswith('damage_reduction_'):
                        damage *= (1 - effect['modifier_value'] / 100)
            
            # Store damage by type (round down, minimum 0)
            damage_by_type[damage_type] = max(0, int(damage)) if resistance < 100 else 0
        
        return damage_by_type
    
    async def calculate_damage(self, attacker_stats: dict, defender_stats: dict, 
                             damage_type: str, base_damage: int, is_critical: bool) -> int:
        """
        DEPRECATED: Legacy damage calculation. Use calculate_damage_with_dice for new system.
        Kept for backwards compatibility during migration.
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

    @component_callback(re.compile(r"^attack_select_\d+$"))
    async def attack_select_handler(self, ctx: ComponentContext):
        """Handle attack button click - show enemy selection if multiple enemies."""
        # Extract player ID from the custom ID
        _, _, player_id = ctx.custom_id.split("_")
        player_id = int(player_id)
        
        # Verify player
        player_data = await self.db.fetchrow("""
            SELECT playerid FROM players WHERE discord_id = $1
        """, ctx.author.id)
        
        if not player_data or player_data['playerid'] != player_id:
            await ctx.send("You are not authorized to use this button.", ephemeral=True)
            return
        
        await ctx.defer(ephemeral=True)
        
        # Get battle instance
        instance_id = await self.get_player_battle_instance(player_id)
        if not instance_id:
            await ctx.send("No active battle found.", ephemeral=True)
            return
        
        # Check if it's this player's turn
        current_turn_player = await self.get_current_turn_player(instance_id)
        if current_turn_player and current_turn_player != player_id:
            await ctx.send("⏳ It's not your turn! Please wait for your turn.", ephemeral=True)
            return
        
        # Get battle state
        battle_state = await self.get_instance_state(instance_id)
        if not battle_state:
            await ctx.send("Error: Could not retrieve battle state.", ephemeral=True)
            return
        
        # Get living enemies
        living_enemies = []
        for battle_enemy in battle_state['enemies']:
            if battle_enemy['current_health'] > 0:
                enemy_data = await self.db.fetchrow("""
                    SELECT * FROM enemies WHERE enemyid = $1
                """, battle_enemy['enemy_id'])
                if enemy_data:
                    living_enemies.append({
                        'battle_enemy': battle_enemy,
                        'enemy_data': enemy_data
                    })
        
        if not living_enemies:
            await ctx.send("No enemies to attack.", ephemeral=True)
            return
        
        # If only one enemy, proceed directly
        if len(living_enemies) == 1:
            enemy_id = living_enemies[0]['enemy_data']['enemyid']
            # Call the actual attack handler
            await self.execute_attack(ctx, player_id, enemy_id, instance_id)
            return
        
        # Multiple enemies - show selection
        embed = Embed(
            title="Select Target",
            description="Choose which enemy to attack:",
            color=0xFF0000
        )
        
        enemy_buttons = []
        for i, enemy_info in enumerate(living_enemies):
            enemy = enemy_info['enemy_data']
            battle_enemy = enemy_info['battle_enemy']
            enemy_buttons.append(
                Button(
                    style=ButtonStyle.DANGER,
                    label=f"{enemy['name']} (HP: {battle_enemy['current_health']})",
                    custom_id=f"attack_{player_id}_{enemy['enemyid']}"
                )
            )
        
        # Group buttons into rows
        button_rows = []
        for i in range(0, len(enemy_buttons), 5):
            button_rows.append(ActionRow(*enemy_buttons[i:i+5]))
        
        await ctx.send(embeds=[embed], components=button_rows, ephemeral=True)
    
    @component_callback(re.compile(r"^attack_\d+_\d+$"))
    async def attack_button_handler(self, ctx: ComponentContext):
        # Extract player ID and enemy ID from the custom ID
        _, player_id, enemy_id = ctx.custom_id.split("_")
        player_id, enemy_id = int(player_id), int(enemy_id)
        
        await ctx.defer(ephemeral=True)
        
        # Get battle instance
        instance_id = await self.get_player_battle_instance(player_id)
        if not instance_id:
            await ctx.send("No active battle found.", ephemeral=True)
            return
        
        # Execute the attack
        await self.execute_attack(ctx, player_id, enemy_id, instance_id)
    
    async def execute_attack(self, ctx: ComponentContext, player_id: int, enemy_id: int, instance_id: int):
        """Execute an attack on a specific enemy."""
        # Verify player
        player_data = await self.db.fetchrow("""
            SELECT playerid FROM players WHERE discord_id = $1
        """, ctx.author.id)
        
        if not player_data or player_data['playerid'] != player_id:
            await ctx.send("You are not authorized to use this button.", ephemeral=True)
            return
        
        # Check if it's this player's turn (for party battles)
        current_turn_player = await self.get_current_turn_player(instance_id)
        if current_turn_player and current_turn_player != player_id:
            await ctx.send("⏳ It's not your turn! Please wait for your turn.", ephemeral=True)
            return

        # Fetch player stats from the view
        player_stats = await self.db.fetchrow("""
            SELECT * FROM player_stats_view WHERE playerid = $1
        """, player_id)

        if not player_stats:
            await ctx.send("Error: Could not retrieve player stats.", ephemeral=True)
            return

        player_stats = dict(player_stats)

        # Get battle state
        battle_state = await self.get_instance_state(instance_id)
        if not battle_state:
            await ctx.send("Error: Could not retrieve battle state.", ephemeral=True)
            return

        # Find the target enemy in the battle
        target_enemy = None
        target_battle_enemy = None
        for battle_enemy in battle_state['enemies']:
            enemy = await self.db.fetchrow("""
                SELECT * FROM enemies WHERE enemyid = $1
            """, battle_enemy['enemy_id'])
            if enemy and enemy['enemyid'] == enemy_id:
                target_enemy = enemy
                target_battle_enemy = battle_enemy
                break

        if not target_enemy:
            await ctx.send("Target enemy not found in battle.", ephemeral=True)
            return

        # Get battle instance for this player
        instance_id = await self.get_player_battle_instance(player_id)
        if not instance_id:
            await ctx.send("No active battle found.", ephemeral=True)
            return
        
        # Check if it's this player's turn (for party battles)
        current_turn_player = await self.get_current_turn_player(instance_id)
        if current_turn_player and current_turn_player != player_id:
            await ctx.send("⏳ It's not your turn! Please wait for your turn.", ephemeral=True)
            return

        # Fetch player stats from the view
        player_stats = await self.db.fetchrow("""
            SELECT * FROM player_stats_view WHERE playerid = $1
        """, player_id)

        if not player_stats:
            await ctx.send("Error: Could not retrieve player stats.", ephemeral=True)
            return

        player_stats = dict(player_stats)

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

        # Get player username for messages
        player_discord_id = await self.db.fetchval("""
            SELECT discord_id FROM players WHERE playerid = $1
        """, player_id)
        player_user = await self.bot.fetch_user(player_discord_id) if player_discord_id else None
        player_name = player_user.display_name if player_user else f"Player {player_id}"
        
        damage_dealt = 0
        new_enemy_health = target_battle_enemy['current_health']
        
        if is_blocked:
            message = f"🛡️ {player_name}'s attack on {target_enemy['name']} was blocked!"
            if battle_state['instance_type'] == 'party':
                await self.send_battle_message(instance_id, message)
            await ctx.send(f"{target_enemy['name']} blocked your attack!", ephemeral=True)
        elif not hit_success:
            message = f"❌ {player_name} missed their attack on {target_enemy['name']}!"
            if battle_state['instance_type'] == 'party':
                await self.send_battle_message(instance_id, message)
            await ctx.send(f"You missed your attack on {target_enemy['name']}!", ephemeral=True)
        else:
            # Calculate damage using new dice system
            weapon_dice = await self.get_equipped_weapon_dice(player_id)
            
            # If weapon has dice, use new system; otherwise fall back to old system
            if weapon_dice:
                damage_by_type = await self.calculate_damage_with_dice(
                    player_stats, target_enemy, weapon_dice, is_critical
                )
                # Sum all damage types
                damage_dealt = sum(damage_by_type.values())
            else:
                # Fallback to old system for weapons without dice
                weapon_damage = await self.get_equipped_weapon_damage(player_id)
                total_weapon_damage = (
                    weapon_damage['slashing'] + 
                    weapon_damage['piercing'] + 
                    weapon_damage['crushing'] + 
                    weapon_damage['dark']
                )
                base_damage = player_stats['total_strength'] + total_weapon_damage
                damage_dealt = await self.calculate_damage(
                    player_stats, target_enemy,
                    'physical', base_damage, is_critical
                )
                damage_by_type = {'physical': damage_dealt}

            # Update enemy's health in the battle instance
            new_health = target_battle_enemy['current_health'] - damage_dealt
            new_enemy_health = new_health
            await self.update_battle_health(
                instance_id, 'enemy', target_battle_enemy['battle_enemy_id'], new_health
            )

            # Format damage message with breakdown
            damage_breakdown = self.format_damage_message(damage_by_type, damage_dealt)
            
            # Send combat message to channel for party visibility
            message = f"⚔️ **{player_name}** dealt {damage_breakdown} to {target_enemy['name']}"
            if is_critical:
                message += " 💥 **Critical Hit!**"
            message += f"\n{target_enemy['name']} health: {new_health}"
            
            if battle_state['instance_type'] == 'party':
                await self.send_battle_message(instance_id, message)
            await ctx.send(f"You dealt {damage_breakdown} to {target_enemy['name']}" + 
                          (" (Critical Hit!)" if is_critical else "") + 
                          f". Remaining enemy health: {new_health}", ephemeral=True)

            # Broadcast attack to other party members (deprecated - now using channel messages)
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

        # Check if enemy is dead
        enemy_dead = new_enemy_health <= 0
        
        # Enemy's turn - in party battles, enemies attack random participants
        player_survived = True
        if not enemy_dead:  # Only have enemies attack if they're still alive
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
                            """, battle_enemy['enemy_id']),
                            instance_id
                        )
                        player_survived = player_survived and survived
            else:
                # Solo battle - enemy attacks player
                player_survived = await self.enemy_attack(ctx, player_id, target_enemy, instance_id)

        # Advance turn for party battles
        if battle_state['instance_type'] == 'party':
            next_player = await self.advance_turn(instance_id)
            if next_player:
                # Get channel from battle instance
                channel_id = await self.db.fetchval("""
                    SELECT channel_id FROM battle_instances WHERE instance_id = $1
                """, instance_id)
                channel = None
                if channel_id:
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except:
                        pass
                # Prompt next player
                await self.prompt_next_player_turn(instance_id, next_player, channel)
        else:
            # Solo battle - prompt player again after enemy turn
            if player_survived:
                # Check if battle is still active (enemy might be dead)
                battle_state = await self.get_instance_state(instance_id)
                if battle_state:
                    # Check if any enemies are still alive
                    living_enemies = [be for be in battle_state['enemies'] if be['current_health'] > 0]
                    if living_enemies:
                        # Get channel from battle instance
                        channel_id = await self.db.fetchval("""
                            SELECT channel_id FROM battle_instances WHERE instance_id = $1
                        """, instance_id)
                        channel = None
                        if channel_id:
                            try:
                                channel = await self.bot.fetch_channel(channel_id)
                            except:
                                pass
                        # Prompt player for next turn
                        await self.prompt_next_player_turn(instance_id, player_id, channel)

        # Check combat end
        await self.handle_combat_end(ctx, player_id, target_enemy)

    async def enemy_attack(self, ctx, player_id, enemy, instance_id=None):
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
        
        # Get battle instance for enemy effects (if needed in the future)
        # For now, enemy effects are handled through the battle_effects table
        # This section can be expanded later if needed
        
        # Calculate attack roll results for enemy
        hit_success, is_critical, is_blocked = await self.calculate_attack_roll(
            enemy, player_stats
        )

        # Get player username for messages
        player_discord_id = await self.db.fetchval("""
            SELECT discord_id FROM players WHERE playerid = $1
        """, player_id)
        player_user = await self.bot.fetch_user(player_discord_id) if player_discord_id else None
        player_name = player_user.display_name if player_user else f"Player {player_id}"
        
        # Check if this is a party battle
        is_party = False
        if instance_id:
            battle_state = await self.get_instance_state(instance_id)
            is_party = battle_state and battle_state.get('instance_type') == 'party'
        
        if is_blocked:
            message = f"🛡️ {player_name} blocked {enemy['name']}'s attack!"
            if is_party:
                await self.send_battle_message(instance_id, message)
            await ctx.send(f"You blocked {enemy['name']}'s attack!", ephemeral=True)
            return True
        elif not hit_success:
            message = f"❌ {enemy['name']} missed their attack on {player_name}!"
            if is_party:
                await self.send_battle_message(instance_id, message)
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
            
            # Update health in battle instance (for both party and solo battles)
            if instance_id:
                await self.update_battle_health(instance_id, 'player', player_id, new_health)
            
            # Also update player_data for solo battles
            if not is_party:
                await self.db.execute("""
                    UPDATE player_data
                    SET health = $1
                    WHERE playerid = $2
                """, new_health, player_id)
            
            # Send combat message to channel for party visibility
            message = f"💥 **{enemy['name']}** attacked **{player_name}** for {damage_received} damage"
            if is_critical:
                message += " 💥 **Critical Hit!**"
            message += f"\n{player_name}'s health: {new_health}"
            
            if is_party:
                await self.send_battle_message(instance_id, message)
            
            # Send personal message to the attacked player
            personal_message = f"{enemy['name']} dealt {damage_received} damage to you"
            if is_critical:
                personal_message += " (Critical Hit!)"
            personal_message += f". Your health: {new_health}"
            await ctx.send(personal_message, ephemeral=True)

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
        # Get battle instance from database
        instance_id = await self.get_player_battle_instance(player_id)
        if not instance_id:
            return  # If no active battle, stop further processing

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
            
            # Battle ended - cleanup handled by end_battle_instance
            return

        if all_enemies_defeated:
            # Victory message
            # Send victory message to channel for party visibility
            if battle_state['instance_type'] == 'party':
                await self.send_battle_message(instance_id, "🎉 **Victory!** All enemies have been defeated!")
            await ctx.send("🎉 All enemies have been defeated!", ephemeral=True)
            
            # Collect all loot from all defeated enemies
            all_loot = []
            for battle_enemy in battle_state['enemies']:
                enemy_loot = await self.handle_enemy_defeat(ctx, instance_id, battle_enemy['enemy_id'])
                all_loot.extend(enemy_loot)
            
            # Distribute loot to party members
            if all_loot:
                await self.distribute_party_loot(instance_id, all_loot)
            
            # Notify all party members of victory
            for participant in battle_state['participants']:
                if participant['current_health'] > 0:
                    try:
                        discord_id = await self.db.fetchval("""
                            SELECT discord_id FROM players WHERE playerid = $1
                        """, participant['player_id'])
                        if discord_id and participant['player_id'] != player_id:
                            user = await self.bot.fetch_user(discord_id)
                            if user:
                                await user.send("🎉 Victory! All enemies have been defeated!")
                    except:
                        pass

            # Clean up
            await self.end_battle_instance(instance_id)
            return

        if all_players_defeated:
            # Defeat message
            if battle_state['instance_type'] == 'party':
                await self.send_battle_message(instance_id, "💀 **Defeat!** All party members have fallen!")
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
            return

        # Turn system now handles prompting next player automatically
        # This old code is no longer needed

    async def handle_enemy_defeat(self, ctx: SlashContext, instance_id: int, enemy_id: int):
        """Handle enemy defeat and distribute loot to party members."""
        # Fetch drop chances for this enemy
        drop_list = await self.db.fetch("""
            SELECT itemid, droprate, quantity
            FROM enemyloot
            WHERE enemyid = $1
        """, enemy_id)

        if not drop_list:
            return []  # Return empty list if no loot

        # Roll for all loot
        all_drops = []
        for drop in drop_list:
            if random.uniform(0, 100) <= drop['droprate']:
                all_drops.append({
                    'itemid': int(drop['itemid']),
                    'quantity': drop['quantity']
                })
        
        return all_drops
    
    async def distribute_party_loot(self, instance_id: int, all_loot: list):
        """Distribute loot equally among party members."""
        # Get all surviving party members
        participants = await self.db.fetch("""
            SELECT bp.player_id, bp.is_leader
            FROM battle_participants bp
            WHERE bp.instance_id = $1 AND bp.current_health > 0
        """, instance_id)
        
        if not participants or not all_loot:
            return
        
        party_size = len(participants)
        # Find leader (or use first participant if no leader marked)
        leader_id = None
        for p in participants:
            if p.get('is_leader'):
                leader_id = p['player_id']
                break
        if not leader_id and participants:
            leader_id = participants[0]['player_id']  # Default to first if no leader
        
        # Distribute each item
        for loot_item in all_loot:
            itemid = loot_item['itemid']
            total_quantity = loot_item['quantity']
            
            # Get item name
            item_name = await self.db.fetchval("SELECT name FROM items WHERE itemid = $1", itemid)
            if not item_name:
                continue
            
            # Split quantity equally
            per_person = total_quantity // party_size
            remainder = total_quantity % party_size
            
            # Distribute to each member
            for participant in participants:
                quantity_to_give = per_person
                if participant['player_id'] == leader_id:
                    quantity_to_give += remainder  # Leader gets remainder
                
                if quantity_to_give > 0:
                    # Check inventory space
                    has_space = await self.db.can_add_to_inventory(participant['player_id'], 1)
                    if has_space:
                        await self.db.execute("""
                            INSERT INTO inventory (playerid, itemid, quantity, isequipped)
                            VALUES ($1, $2, $3, false)
                            ON CONFLICT (playerid, itemid) DO UPDATE 
                            SET quantity = inventory.quantity + $3
                        """, participant['player_id'], itemid, quantity_to_give)
                        
                        # Notify player
                        try:
                            discord_id = await self.db.fetchval("""
                                SELECT discord_id FROM players WHERE playerid = $1
                            """, participant['player_id'])
                            if discord_id:
                                user = await self.bot.fetch_user(discord_id)
                                if user:
                                    await user.send(f"🎁 You received **{quantity_to_give}x {item_name}** from the battle!")
                        except:
                            pass

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

    @component_callback(re.compile(r"^ability_select_\d+$"))
    async def ability_select_handler(self, ctx: ComponentContext):
        """Handle ability button click - show enemy selection if multiple enemies."""
        # Extract player ID from the custom ID
        _, _, player_id = ctx.custom_id.split("_")
        player_id = int(player_id)
        
        # Verify player
        player_data = await self.db.fetchrow("""
            SELECT playerid FROM players WHERE discord_id = $1
        """, ctx.author.id)
        
        if not player_data or player_data['playerid'] != player_id:
            await ctx.send("You are not authorized to use this button.", ephemeral=True)
            return
        
        await ctx.defer(ephemeral=True)
        
        # Get battle instance
        instance_id = await self.get_player_battle_instance(player_id)
        if not instance_id:
            await ctx.send("No active battle found.", ephemeral=True)
            return
        
        # Check if it's this player's turn
        current_turn_player = await self.get_current_turn_player(instance_id)
        if current_turn_player and current_turn_player != player_id:
            await ctx.send("⏳ It's not your turn! Please wait for your turn.", ephemeral=True)
            return
        
        # Get battle state
        battle_state = await self.get_instance_state(instance_id)
        if not battle_state:
            await ctx.send("Error: Could not retrieve battle state.", ephemeral=True)
            return
        
        # Get living enemies
        living_enemies = []
        for battle_enemy in battle_state['enemies']:
            if battle_enemy['current_health'] > 0:
                enemy_data = await self.db.fetchrow("""
                    SELECT * FROM enemies WHERE enemyid = $1
                """, battle_enemy['enemy_id'])
                if enemy_data:
                    living_enemies.append({
                        'battle_enemy': battle_enemy,
                        'enemy_data': enemy_data
                    })
        
        if not living_enemies:
            await ctx.send("No enemies to target.", ephemeral=True)
            return
        
        # If only one enemy, proceed directly to ability selection
        if len(living_enemies) == 1:
            enemy_id = living_enemies[0]['enemy_data']['enemyid']
            # Call the original ability handler with enemy_id
            await self.show_ability_selection(ctx, player_id, enemy_id, instance_id)
            return
        
        # Multiple enemies - show selection
        embed = Embed(
            title="Select Target",
            description="Choose which enemy to target with your ability:",
            color=0xFF0000
        )
        
        enemy_buttons = []
        for i, enemy_info in enumerate(living_enemies):
            enemy = enemy_info['enemy_data']
            battle_enemy = enemy_info['battle_enemy']
            enemy_buttons.append(
                Button(
                    style=ButtonStyle.DANGER,
                    label=f"{enemy['name']} (HP: {battle_enemy['current_health']})",
                    custom_id=f"ability_{player_id}_{enemy['enemyid']}"
                )
            )
        
        # Group buttons into rows
        button_rows = []
        for i in range(0, len(enemy_buttons), 5):
            button_rows.append(ActionRow(*enemy_buttons[i:i+5]))
        
        await ctx.send(embeds=[embed], components=button_rows, ephemeral=True)
    
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
            
            # Get battle instance
            instance_id = await self.get_player_battle_instance(actual_player_id)
            if not instance_id:
                await ctx.send("No active battle found.", ephemeral=True)
                return

            # Show ability selection
            await self.show_ability_selection(ctx, actual_player_id, enemy_id, instance_id)
        
        except Exception as e:
            logging.error(f"Error in ability_button_handler: {e}")
            import traceback
            traceback.print_exc()
            await ctx.send("Error: Could not process ability selection.", ephemeral=True)
    
    async def show_ability_selection(self, ctx: ComponentContext, player_id: int, enemy_id: int, instance_id: int):
        """Show ability selection menu for a specific enemy."""
        # Fetch the player's equipped abilities
        abilities = await self.db.fetch("""
            SELECT pa.*, a.*
            FROM player_abilities pa
            JOIN abilities a ON pa.ability_id = a.ability_id
            WHERE pa.playerid = $1 AND pa.is_equipped = TRUE
            ORDER BY a.ability_type, a.name
        """, player_id)

        if not abilities:
            await ctx.send("You have no equipped abilities to use.", ephemeral=True)
            return

        # Create buttons for each equipped ability
        ability_buttons = [
            Button(
                style=ButtonStyle.SECONDARY,
                label=ability['name'],
                custom_id=f"cast_ability_{player_id}_{enemy_id}_{ability['ability_id']}"
            ) for ability in abilities
        ]

        # Group buttons into rows of up to 5 buttons each
        button_rows = []
        for i in range(0, len(ability_buttons), 5):
            button_rows.append(ActionRow(*ability_buttons[i:i+5]))

        # Send the prompt for the player to choose an ability
        await ctx.send(
            content="Choose an ability to use:",
            components=button_rows,
            ephemeral=True
        )

    def calculate_ability_hit(self, attacker_stats: dict, defender_stats: dict, ability_type: str) -> tuple[bool, bool]:
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

            # Verify player identity
            player_data = await self.db.fetchrow("""
                SELECT playerid FROM players WHERE discord_id = $1
            """, ctx.author.id)
            
            if not player_data or player_data['playerid'] != player_id:
                await ctx.send("You are not authorized to use this ability.", ephemeral=True)
                return
            
            # Get battle instance data
            instance_id = await self.get_player_battle_instance(player_id)
            if not instance_id:
                await ctx.send("No active battle found.", ephemeral=True)
                return
            
            # Check if it's this player's turn (for party battles)
            current_turn_player = await self.get_current_turn_player(instance_id)
            if current_turn_player and current_turn_player != player_id:
                await ctx.send("⏳ It's not your turn! Please wait for your turn.", ephemeral=True)
                return
            
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

            # Get player username for messages
            player_discord_id = await self.db.fetchval("""
                SELECT discord_id FROM players WHERE playerid = $1
            """, player_id)
            player_user = await self.bot.fetch_user(player_discord_id) if player_discord_id else None
            player_name = player_user.display_name if player_user else f"Player {player_id}"
            
            # Get enemy stats for hit calculation
            enemy_stats = self.extract_attributes(target_enemy)
            
            # Calculate ability hit success
            hit_success, is_critical = self.calculate_ability_hit(
                player_stats, enemy_stats, ability['ability_type']
            )

            if not hit_success:
                message = f"❌ **{player_name}**'s {ability['name']} missed {target_enemy['name']}!"
                if battle_state['instance_type'] == 'party':
                    await self.send_battle_message(instance_id, message)
                await ctx.send(f"Your {ability['name']} missed {target_enemy['name']}!", ephemeral=True)
            else:
                # Calculate damage using new dice system
                ability_dice = {}
                damage_types = ['fire', 'ice', 'lightning', 'water', 'earth', 'air', 'light', 'dark', 'magic', 'poison',
                               'piercing', 'crushing', 'slashing']
                
                # Get dice for each damage type the ability has (stored in _damage columns)
                for damage_type in damage_types:
                    dice = ability.get(f'{damage_type}_damage', '')
                    if dice and dice.strip():
                        ability_dice[damage_type] = dice
                
                # If ability has dice, use new system; otherwise fall back to old system
                if ability_dice:
                    damage_by_type = await self.calculate_damage_with_dice(
                        player_stats, target_enemy, ability_dice, is_critical
                    )
                    damage_dealt = sum(damage_by_type.values())
                else:
                    # Fallback to old system
                    base_damage = ability.get(f"{ability['ability_type']}_damage", ability.get('damage', 5))
                    if ability['ability_type'] in ['fire', 'ice', 'lightning', 'water', 'earth', 'air', 'light', 'dark', 'magic']:
                        base_damage += player_stats['total_intelligence'] * 0.5

                    damage_dealt = await self.calculate_damage(
                        player_stats, target_enemy,
                        ability['ability_type'], base_damage, is_critical
                    )
                    damage_by_type = {ability['ability_type']: damage_dealt}

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

                # Format damage message with breakdown
                damage_breakdown = self.format_damage_message(damage_by_type, damage_dealt)
                
                # Send combat message to channel for party visibility
                message = f"✨ **{player_name}** used **{ability['name']}** and dealt {damage_breakdown} to {target_enemy['name']}"
                if is_critical:
                    message += " 💥 **Critical Hit!**"
                message += f"\n{target_enemy['name']} health: {new_health} | {player_name}'s mana: {new_mana}"
                
                if battle_state['instance_type'] == 'party':
                    await self.send_battle_message(instance_id, message)
                
                # Also send personal message
                personal_message = f"You used {ability['name']} and dealt {damage_breakdown}"
                if is_critical:
                    personal_message += " (Critical Hit!)"
                personal_message += f". Remaining enemy health: {new_health}\nMana remaining: {new_mana}"
                await ctx.send(personal_message, ephemeral=True)

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
                            """, battle_enemy['enemy_id']),
                            instance_id
                        )
                        player_survived = player_survived and survived
            else:
                player_survived = await self.enemy_attack(ctx, player_id, target_enemy, instance_id)

            # Advance turn for party battles
            if battle_state['instance_type'] == 'party':
                next_player = await self.advance_turn(instance_id)
                if next_player:
                    # Get channel from battle instance
                    channel_id = await self.db.fetchval("""
                        SELECT channel_id FROM battle_instances WHERE instance_id = $1
                    """, instance_id)
                    channel = None
                    if channel_id:
                        try:
                            channel = await self.bot.fetch_channel(channel_id)
                        except:
                            pass
                    # Prompt next player
                    await self.prompt_next_player_turn(instance_id, next_player, channel)
            else:
                # Solo battle - refresh status
                if player_survived:
                    battle_state = await self.get_instance_state(instance_id)
                    await self.refresh_battle_status(ctx, battle_state, player_id)

            # Check combat end
            await self.handle_combat_end(ctx, player_id, target_enemy)

        except Exception as e:
            logging.error(f"Error in cast_ability_handler: {e}")
            import traceback
            traceback.print_exc()
            await ctx.send(f"Error: Could not process ability cast. {str(e)}", ephemeral=True)

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
            INSERT INTO battle_instances (instance_type, location_id, max_players, phase)
            VALUES ($1, $2, $3, 'player_turn')
            RETURNING instance_id
        """, instance_type, location_id, max_players)
        
        return instance['instance_id']
    
    async def initialize_turn_order(self, instance_id: int):
        """Initialize turn order for party battles based on agility (highest first)."""
        # Get all participants with their agility
        participants = await self.db.fetch("""
            SELECT bp.player_id, COALESCE(psv.total_agility, pd.agility, 10) as agility
            FROM battle_participants bp
            JOIN player_data pd ON bp.player_id = pd.playerid
            LEFT JOIN player_stats_view psv ON bp.player_id = psv.playerid
            WHERE bp.instance_id = $1 AND bp.current_health > 0
            ORDER BY agility DESC, bp.player_id
        """, instance_id)
        
        if not participants:
            return None
        
        # Create turn order array
        turn_order = [p['player_id'] for p in participants]
        
        # Set first player as current turn
        current_turn_player = turn_order[0] if turn_order else None
        
        # Update battle instance with turn order
        await self.db.execute("""
            UPDATE battle_instances
            SET turn_order = $1, current_turn_player_id = $2, turn_number = 0
            WHERE instance_id = $3
        """, turn_order, current_turn_player, instance_id)
        
        return current_turn_player
    
    async def get_current_turn_player(self, instance_id: int):
        """Get the player whose turn it is."""
        return await self.db.fetchval("""
            SELECT current_turn_player_id FROM battle_instances
            WHERE instance_id = $1 AND is_active = true
        """, instance_id)
    
    async def advance_turn(self, instance_id: int):
        """Advance to the next player's turn. Returns next player_id or None if round complete."""
        battle = await self.db.fetchrow("""
            SELECT turn_order, current_turn_player_id, turn_number
            FROM battle_instances
            WHERE instance_id = $1
        """, instance_id)
        
        if not battle or not battle['turn_order']:
            return None
        
        turn_order = battle['turn_order']
        current_player = battle['current_turn_player_id']
        turn_number = battle['turn_number'] or 0
        
        # Find current player index
        try:
            current_index = turn_order.index(current_player)
        except ValueError:
            current_index = 0
        
        # Get next player (skip dead players)
        next_index = (current_index + 1) % len(turn_order)
        next_player = turn_order[next_index]
        
        # Check if we've completed a full round
        if next_index == 0:
            turn_number += 1
        
        # Skip dead players
        attempts = 0
        while attempts < len(turn_order):
            # Check if next player is alive
            participant = await self.db.fetchrow("""
                SELECT current_health FROM battle_participants
                WHERE instance_id = $1 AND player_id = $2
            """, instance_id, next_player)
            
            if participant and participant['current_health'] > 0:
                break
            
            # Player is dead, move to next
            next_index = (next_index + 1) % len(turn_order)
            next_player = turn_order[next_index]
            attempts += 1
        
        # Update battle instance
        await self.db.execute("""
            UPDATE battle_instances
            SET current_turn_player_id = $1, turn_number = $2
            WHERE instance_id = $3
        """, next_player, turn_number, instance_id)
        
        return next_player

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

    async def get_player_battle_instance(self, player_id: int):
        """Get active battle instance for a player from database."""
        return await self.db.fetchval("""
            SELECT bi.instance_id FROM battle_instances bi
            JOIN battle_participants bp ON bi.instance_id = bp.instance_id
            WHERE bp.player_id = $1 AND bi.is_active = true
            ORDER BY bi.created_at DESC
            LIMIT 1
        """, player_id)
    
    async def send_battle_message(self, instance_id: int, message: str, embed: Embed = None):
        """Send a message to the battle channel for party visibility."""
        try:
            channel_id = await self.db.fetchval("""
                SELECT channel_id FROM battle_instances WHERE instance_id = $1
            """, instance_id)
            
            if channel_id:
                channel = await self.bot.fetch_channel(channel_id)
                if channel:
                    if embed:
                        await channel.send(content=message, embeds=[embed])
                    else:
                        await channel.send(message)
                    return True
        except Exception as e:
            logging.error(f"Error sending battle message: {e}")
        return False
    
    async def prompt_next_player_turn(self, instance_id: int, player_id: int, channel=None):
        """Prompt the next player whose turn it is. Sends to channel if provided, otherwise DM."""
        try:
            battle_state = await self.get_instance_state(instance_id)
            if not battle_state:
                logging.error(f"No battle state found for instance {instance_id}")
                return
            
            # Get player stats
            player_stats = await self.db.fetchrow("""
                SELECT * FROM player_stats_view WHERE playerid = $1
            """, player_id)
            
            if not player_stats:
                logging.error(f"No player stats found for player {player_id}")
                return
            
            # Find first living enemy
            target_enemy = None
            target_battle_enemy = None
            for battle_enemy in battle_state['enemies']:
                if battle_enemy['current_health'] > 0:
                    enemy_data = await self.db.fetchrow("""
                        SELECT * FROM enemies WHERE enemyid = $1
                    """, battle_enemy['enemy_id'])
                    if enemy_data:
                        target_enemy = enemy_data
                        target_battle_enemy = battle_enemy
                        break
            
            if not target_enemy:
                logging.error(f"No living enemies found in battle {instance_id}")
                return
            
            # Get fresh participant data from database to ensure current health/mana
            participant = await self.db.fetchrow("""
                SELECT * FROM battle_participants 
                WHERE instance_id = $1 AND player_id = $2
            """, instance_id, player_id)
            
            if not participant:
                logging.error(f"Player {player_id} not found in battle participants")
                return
            
            # Also refresh battle_state participants for display
            battle_state['participants'] = await self.db.fetch("""
                SELECT * FROM battle_participants WHERE instance_id = $1
            """, instance_id)
            
            # Refresh enemies too
            battle_state['enemies'] = await self.db.fetch("""
                SELECT * FROM battle_enemies WHERE instance_id = $1
            """, instance_id)
            
            # Get player's Discord ID and username
            discord_id = await self.db.fetchval("""
                SELECT discord_id FROM players WHERE playerid = $1
            """, player_id)
            
            if not discord_id:
                logging.error(f"No Discord ID found for player {player_id}")
                return
            
            user = await self.bot.fetch_user(discord_id)
            if not user:
                logging.error(f"Could not fetch Discord user for ID {discord_id}")
                return
            
            # If channel is provided, send to channel and mention the player
            if channel:
                try:
                    # Create embed showing all party members and enemies
                    embed = Embed(
                        title=f"⚔️ {user.display_name}'s Turn!",
                        description=f"It's **{user.mention}**'s turn to act!",
                        color=0xFF0000
                    )
                    
                    # Add all party members' status
                    for p in battle_state['participants']:
                        try:
                            p_discord_id = await self.db.fetchval("""
                                SELECT discord_id FROM players WHERE playerid = $1
                            """, p['player_id'])
                            if p_discord_id:
                                p_user = await self.bot.fetch_user(p_discord_id)
                                p_name = p_user.display_name if p_user else f"Player {p['player_id']}"
                            else:
                                p_name = f"Player {p['player_id']}"
                        except:
                            p_name = f"Player {p['player_id']}"
                        
                        is_current_turn = " 👈" if p['player_id'] == player_id else ""
                        status_icon = "💀" if p['current_health'] <= 0 else "❤️"
                        embed.add_field(
                            name=f"{p_name}{is_current_turn}",
                            value=f"{status_icon} Health: {p['current_health']}\n✨ Mana: {p['current_mana']}",
                            inline=True
                        )
                    
                    # Add all enemies' status
                    for battle_enemy in battle_state['enemies']:
                        if battle_enemy['current_health'] > 0:
                            enemy_data = await self.db.fetchrow("""
                                SELECT * FROM enemies WHERE enemyid = $1
                            """, battle_enemy['enemy_id'])
                            if enemy_data:
                                status_icon = "💀" if battle_enemy['current_health'] <= 0 else "👹"
                                embed.add_field(
                                    name=f"{enemy_data['name']}",
                                    value=f"{status_icon} Health: {battle_enemy['current_health']}",
                                    inline=True
                                )
                    
                    # Count living enemies
                    living_enemies = [be for be in battle_state['enemies'] if be['current_health'] > 0]
                    
                    # Create action buttons - if multiple enemies, buttons will trigger selection
                    buttons = ActionRow(
                        Button(
                            style=ButtonStyle.PRIMARY,
                            label="Attack",
                            custom_id=f"attack_select_{player_id}"
                        ),
                        Button(
                            style=ButtonStyle.SECONDARY,
                            label="Use Ability",
                            custom_id=f"ability_select_{player_id}"
                        ),
                        Button(
                            style=ButtonStyle.DANGER,
                            label="Flee Battle",
                            custom_id=f"flee_{player_id}"
                        )
                    )
                    
                    # Send buttons to channel
                    turn_message = await channel.send(content=user.mention, embeds=[embed], components=[buttons])
                    logging.info(f"Sent turn prompt to channel {channel.id} for player {player_id} (message ID: {turn_message.id})")
                    
                    # Update battle instance with turn message ID for reference
                    await self.db.execute("""
                        UPDATE battle_instances
                        SET message_id = $1
                        WHERE instance_id = $2
                    """, turn_message.id, instance_id)
                except Exception as e:
                    logging.error(f"Error sending turn prompt to channel: {e}")
                    import traceback
                    traceback.print_exc()
                    # Fallback to DM
                    await self.prompt_player_action(
                        None,
                        player_id,
                        participant['current_health'],
                        target_enemy,
                        target_battle_enemy['current_health'],
                        self.extract_attributes(player_stats),
                        self.extract_attributes(target_enemy),
                        self.extract_resistances(player_stats),
                        self.extract_resistances(target_enemy)
                    )
            else:
                # Fallback to DM if no channel
                logging.info(f"No channel provided, sending DM to player {player_id}")
                await self.prompt_player_action(
                    None,
                    player_id,
                    participant['current_health'],
                    target_enemy,
                    target_battle_enemy['current_health'],
                    self.extract_attributes(player_stats),
                    self.extract_attributes(target_enemy),
                    self.extract_resistances(player_stats),
                    self.extract_resistances(target_enemy)
                )
        except Exception as e:
            logging.error(f"Error in prompt_next_player_turn: {e}")
            import traceback
            traceback.print_exc()
    
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

    @component_callback(re.compile(r"^flee_\d+$"))
    async def flee_button_handler(self, ctx: ComponentContext):
        # Extract player ID from the custom ID
        _, player_id = ctx.custom_id.split("_")
        player_id = int(player_id)

        # Verify player authorization - only the button owner can use it
        player_data = await self.db.fetchrow("""
            SELECT playerid FROM players WHERE discord_id = $1
        """, ctx.author.id)
        
        if not player_data or player_data['playerid'] != player_id:
            await ctx.send("You are not authorized to use this button.", ephemeral=True)
            return

        # Get battle instance from database
        instance_id = await self.get_player_battle_instance(player_id)
        if not instance_id:
            await ctx.send("No active battle found.", ephemeral=True)
            return
        
        # Check if it's this player's turn (for party battles) - but allow fleeing anytime
        current_turn_player = await self.get_current_turn_player(instance_id)
        is_their_turn = (current_turn_player == player_id) if current_turn_player else False

        # Fetch player stats from the view
        player_stats = await self.db.fetchrow("""
            SELECT * FROM player_stats_view WHERE playerid = $1
        """, player_id)

        if not player_stats:
            await ctx.send("Error: Could not retrieve player stats.", ephemeral=True)
            return

        player_stats = dict(player_stats)

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
            # Get player username for messages
            player_discord_id = await self.db.fetchval("""
                SELECT discord_id FROM players WHERE playerid = $1
            """, player_id)
            player_user = await self.bot.fetch_user(player_discord_id) if player_discord_id else None
            player_name = player_user.display_name if player_user else f"Player {player_id}"
            
            # Check if this is a party battle
            is_party = battle_state.get('instance_type') == 'party'
            
            if is_party:
                # Use the turn check we did earlier (before any changes)
                was_their_turn = is_their_turn
                
                # Get current turn order to find next player
                turn_order = await self.db.fetchval("""
                    SELECT turn_order FROM battle_instances WHERE instance_id = $1
                """, instance_id)
                
                # Find the next player in the original turn order (before removing fleeing player)
                next_player = None
                if was_their_turn and turn_order and player_id in turn_order:
                    try:
                        current_index = turn_order.index(player_id)
                        # Find next alive player after the fleeing player
                        for i in range(1, len(turn_order)):
                            next_index = (current_index + i) % len(turn_order)
                            candidate_id = turn_order[next_index]
                            
                            # Skip the fleeing player if we wrap around
                            if candidate_id == player_id:
                                continue
                            
                            # Check if this player is still in battle and alive
                            participant = await self.db.fetchrow("""
                                SELECT current_health FROM battle_participants
                                WHERE instance_id = $1 AND player_id = $2
                            """, instance_id, candidate_id)
                            
                            if participant and participant['current_health'] > 0:
                                next_player = candidate_id
                                break
                    except ValueError:
                        pass
                
                # Remove player from battle participants
                await self.db.execute("""
                    DELETE FROM battle_participants
                    WHERE instance_id = $1 AND player_id = $2
                """, instance_id, player_id)
                
                # Remove player from turn order
                if turn_order and player_id in turn_order:
                    new_turn_order = [p for p in turn_order if p != player_id]
                    await self.db.execute("""
                        UPDATE battle_instances
                        SET turn_order = $1
                        WHERE instance_id = $2
                    """, new_turn_order, instance_id)
                    
                    # If it was this player's turn, set the next player
                    if was_their_turn:
                        if next_player:
                            # Set the next player we found as current turn
                            await self.db.execute("""
                                UPDATE battle_instances
                                SET current_turn_player_id = $1
                                WHERE instance_id = $2
                            """, next_player, instance_id)
                            
                            # Get channel and prompt next player
                            channel_id = await self.db.fetchval("""
                                SELECT channel_id FROM battle_instances WHERE instance_id = $1
                            """, instance_id)
                            channel = None
                            if channel_id:
                                try:
                                    channel = await self.bot.fetch_channel(channel_id)
                                except:
                                    pass
                            if channel:
                                await self.prompt_next_player_turn(instance_id, next_player, channel)
                        else:
                            # No next player found, try to get first alive player from new turn order
                            for p_id in new_turn_order:
                                participant = await self.db.fetchrow("""
                                    SELECT current_health FROM battle_participants
                                    WHERE instance_id = $1 AND player_id = $2
                                """, instance_id, p_id)
                                if participant and participant['current_health'] > 0:
                                    await self.db.execute("""
                                        UPDATE battle_instances
                                        SET current_turn_player_id = $1
                                        WHERE instance_id = $2
                                    """, p_id, instance_id)
                                    
                                    # Get channel and prompt next player
                                    channel_id = await self.db.fetchval("""
                                        SELECT channel_id FROM battle_instances WHERE instance_id = $1
                                    """, instance_id)
                                    channel = None
                                    if channel_id:
                                        try:
                                            channel = await self.bot.fetch_channel(channel_id)
                                        except:
                                            pass
                                    if channel:
                                        await self.prompt_next_player_turn(instance_id, p_id, channel)
                                    break
                
                # Remove player from party
                party = await self.db.fetchrow("""
                    SELECT p.* FROM parties p
                    JOIN party_members pm ON p.party_id = pm.party_id
                    WHERE pm.player_id = $1 AND p.is_active = true
                """, player_id)
                
                if party:
                    # If leader, disband party
                    if party['leader_id'] == player_id:
                        await self.db.execute("""
                            UPDATE parties SET is_active = false
                            WHERE party_id = $1
                        """, party['party_id'])
                        await self.db.execute("""
                            DELETE FROM party_members
                            WHERE party_id = $1
                        """, party['party_id'])
                        
                        # Notify remaining party members
                        remaining_members = await self.db.fetch("""
                            SELECT pm.player_id, players.discord_id
                            FROM party_members pm
                            JOIN players ON pm.player_id = players.playerid
                            WHERE pm.party_id = $1
                        """, party['party_id'])
                        
                        for member in remaining_members:
                            try:
                                member_user = await self.bot.fetch_user(member['discord_id'])
                                if member_user:
                                    await member_user.send("⚠️ Your party leader has fled and the party has been disbanded!")
                            except:
                                pass
                    else:
                        # Just remove from party
                        await self.db.execute("""
                            DELETE FROM party_members
                            WHERE party_id = $1 AND player_id = $2
                        """, party['party_id'], player_id)
                        
                        # Notify party leader
                        leader_discord_id = await self.db.fetchval("""
                            SELECT discord_id FROM players WHERE playerid = $1
                        """, party['leader_id'])
                        if leader_discord_id:
                            try:
                                leader_user = await self.bot.fetch_user(leader_discord_id)
                                if leader_user:
                                    await leader_user.send(f"⚠️ {player_name} has fled from battle and left the party!")
                            except:
                                pass
                
                # Send message to battle channel
                await self.send_battle_message(instance_id, f"🏃 **{player_name}** has successfully fled from battle!")
                
                # Check if any participants remain
                remaining_participants = await self.db.fetch("""
                    SELECT * FROM battle_participants
                    WHERE instance_id = $1 AND current_health > 0
                """, instance_id)
                
                if not remaining_participants:
                    # No one left in battle - end it
                    await self.send_battle_message(instance_id, "💀 All party members have fled or been defeated! Battle ended.")
                    await self.end_battle_instance(instance_id)
                
                await ctx.send("You successfully escaped from battle and have been removed from the party!", ephemeral=True)
            else:
                # Solo battle - remove player from participants and end the instance
                await self.db.execute("""
                    DELETE FROM battle_participants
                    WHERE instance_id = $1 AND player_id = $2
                """, instance_id, player_id)
                await self.end_battle_instance(instance_id)
                await ctx.send("You successfully escaped from battle!", ephemeral=True)
            return
        else:
            await ctx.send(f"Failed to escape! {len(successful_enemies)} enemies caught up to you!", ephemeral=True)
            
            # Only enemies that beat the roll get to attack
            player_survived = True
            for enemy in successful_enemies:
                if not player_survived:
                    break
                    
                player_survived = await self.enemy_attack(ctx, player_id, enemy, instance_id)
            
            # Get battle state to check if it's a party battle
            battle_state = await self.get_instance_state(instance_id)
            if not battle_state:
                return
            
            # Advance turn for party battles only if it was this player's turn (since flee attempt uses up the turn)
            if battle_state['instance_type'] == 'party' and is_their_turn:
                next_player = await self.advance_turn(instance_id)
                if next_player:
                    # Get channel from battle instance
                    channel_id = await self.db.fetchval("""
                        SELECT channel_id FROM battle_instances WHERE instance_id = $1
                    """, instance_id)
                    channel = None
                    if channel_id:
                        try:
                            channel = await self.bot.fetch_channel(channel_id)
                        except:
                            pass
                    if channel:
                        # Prompt next player
                        await self.prompt_next_player_turn(instance_id, next_player, channel)
            else:
                # Solo battle - prompt player again after enemy attacks (if they survived)
                if player_survived:
                    # Check if battle is still active (enemy might be dead)
                    battle_state = await self.get_instance_state(instance_id)
                    if battle_state:
                        # Get channel from battle instance
                        channel_id = await self.db.fetchval("""
                            SELECT channel_id FROM battle_instances WHERE instance_id = $1
                        """, instance_id)
                        channel = None
                        if channel_id:
                            try:
                                channel = await self.bot.fetch_channel(channel_id)
                            except:
                                pass
                        if channel:
                            # Prompt player for next turn
                            await self.prompt_next_player_turn(instance_id, player_id, channel)
                        else:
                            # Fallback to refresh battle status
                            await self.refresh_battle_status(ctx, battle_state, player_id)
                else:
                    # Player died, refresh status to show death
                    battle_state = await self.get_instance_state(instance_id)
                    if battle_state:
                        await self.refresh_battle_status(ctx, battle_state, player_id)

            # Check combat end
            await self.handle_combat_end(ctx, player_id, successful_enemies[0])  # Use first enemy for end check

# Setup function to load this as an extension
def setup(bot):
    BattleSystem(bot)
