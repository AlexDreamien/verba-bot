/*
 * Daily-word answer pools for the engine, one array per locale.
 *
 * Original, hand-curated lists of common 5-letter **nouns** (lowercase, exactly
 * the locale alphabet — no adjectives, adverbs or verbs). The daily word is
 * picked by date modulo the list length, so a longer list means a longer cycle
 * before words repeat. Extend freely; tests/test_words.py validates that every
 * entry is exactly 5 letters of the locale's alphabet and unique.
 *
 * This file is original work (MIT). The game bundles no third-party word data.
 */
window.VERBA_WORDS = {
  ru: [
    "слово", "книга", "город", "ветер", "песня", "рынок", "банан", "зебра",
    "лимон", "батон", "вагон", "салат", "сахар", "капля", "лампа", "карта",
    "парта", "марка", "банка", "булка", "вилка", "полка", "кошка", "ложка",
    "чашка", "шапка", "сумка", "точка", "дочка", "ветка", "сетка", "маска",
    "доска", "весна", "сосна", "война", "ягода", "осина", "жираф", "панда",
    "метро", "океан", "берег", "туман", "гроза", "трава", "ствол", "дубок",
    "пчела", "комар", "рыбка", "акула", "голос", "слеза", "мечта", "разум",
    "герой", "спина", "живот", "страх", "кефир", "халва", "крупа", "тесто",
    "пирог", "блины", "сырок", "перец", "судак", "сазан", "окунь", "стриж",
    "сокол", "ворон", "индюк", "баран", "хомяк", "сурок", "бизон", "коала",
    "камин", "диван", "комод", "штора", "замок", "свеча", "ведро", "метла",
    "веник", "бокал", "рюмка", "блюдо", "экран", "мышка", "завод", "склад",
    "ангар", "касса", "киоск", "музей", "театр", "арена", "сцена", "балет",
    "опера", "труба", "танец", "грипп", "шприц", "осень", "закат", "скала",
    "тайга", "залив", "ручей",
  ],
  uk: [
    "слово", "місто", "вітер", "пісня", "ринок", "банан", "зебра", "лимон",
    "батон", "вагон", "салат", "цукор", "лампа", "карта", "парта", "марка",
    "банка", "булка", "кішка", "ложка", "чашка", "шапка", "сумка", "дочка",
    "гілка", "сітка", "маска", "дошка", "весна", "сосна", "війна", "ягода",
    "осика", "жираф", "панда", "метро", "океан", "берег", "туман", "гроза",
    "трава", "комар", "рибка", "акула", "голос", "розум", "герой", "спина",
    "живіт", "страх", "зірка", "сонце", "хмара", "річка", "земля", "книга",
    "кефір", "халва", "крупа", "тісто", "пиріг", "судак", "сазан", "окунь",
    "сокіл", "ворон", "індик", "бабак", "бізон", "коала", "камін", "диван",
    "комод", "штора", "замок", "свіча", "відро", "мітла", "віник", "келих",
    "блюдо", "екран", "мишка", "завод", "склад", "ангар", "кіоск", "музей",
    "театр", "арена", "сцена", "балет", "опера", "труба", "шприц", "осінь",
    "захід", "скеля", "тайга", "потік", "пісок", "глина", "скарб", "гроші",
    "товар", "лікар", "ліжко", "стіна", "вікно", "двері", "стеля",
  ],
  en: [
    "alarm", "apple", "beach", "bread", "brick", "chair", "chess", "clock",
    "cloud", "eagle", "earth", "fairy", "field", "flame", "flute", "ghost",
    "grape", "heart", "honey", "house", "juice", "knife", "lemon", "money",
    "mouse", "music", "night", "ocean", "paper", "peace", "piano", "pizza",
    "river", "robot", "salad", "sheep", "shirt", "snake", "stone", "storm",
    "sugar", "table", "tiger", "water", "whale", "wheat", "world", "zebra",
    "horse", "camel", "koala", "panda", "otter", "moose", "shark", "robin",
    "raven", "finch", "snail", "llama", "bison", "hyena", "lemur", "gecko",
    "viper", "sloth", "rhino", "hippo", "puppy", "bunny", "candy", "cocoa",
    "mango", "melon", "olive", "onion", "toast", "donut", "syrup", "cream",
    "dough", "broth", "curry", "lunch", "steak", "bacon", "pasta", "fruit",
    "couch", "bench", "shelf", "spoon", "plate", "glass", "towel", "broom",
    "phone", "radio", "watch", "frame", "chest", "purse", "scarf", "glove",
    "dress", "skirt", "crown", "jewel", "screw", "wheel", "motor", "plane",
    "truck", "wagon", "canoe", "yacht", "ferry", "kayak", "coast", "creek",
  ],
};
