from interactions import Extension
from dynamic_pricing import DynamicPricing
from Shop_Manager import ShopManager

def setup(bot):
    # Initialize the dynamic pricing system
    bot.dynamic_pricing = DynamicPricing(bot)
    
    # Initialize the shop manager and attach the dynamic pricing system
    shop_manager = ShopManager(bot)
    shop_manager.pricing_system = bot.dynamic_pricing
    bot.shop_manager = shop_manager
    
    # Return both extensions for the bot to register
    return [bot.dynamic_pricing, shop_manager] 