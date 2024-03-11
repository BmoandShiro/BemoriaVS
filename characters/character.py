class Character:
    def __init__(self, name, char_class, level=1, health=100, mana=50, strength=10, dexterity=10, intelligence=10, wisdom=10, agility=10, stamina=10, endurance=10, charisma=10, luck=10):
        self.name = name
        self.char_class = char_class
        self.level = level
        self.health = health
        self.mana = mana
        self.strength = strength
        self.dexterity = dexterity
        self.intelligence = intelligence
        self.wisdom = wisdom
        self.agility = agility
        self.stamina = stamina
        self.endurance = endurance
        self.charisma = charisma
        self.luck = luck

    def display_character(self):
        return (f"Name: {self.name}, Class: {self.char_class}, Level: {self.level}, "
                f"Health: {self.health}, Mana: {self.mana}, Strength: {self.strength}, "
                f"Dexterity: {self.dexterity}, Intelligence: {self.intelligence}, "
                f"Wisdom: {self.wisdom}, Agility: {self.agility}, Stamina: {self.stamina}, "
                f"Endurance: {self.endurance}, Charisma: {self.charisma}, Luck: {self.luck}")

