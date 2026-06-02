/*
 * Daily-word answer pools for the engine, one array per locale.
 *
 * Original, hand-curated lists of common 5-letter words (lowercase, exactly the
 * locale alphabet). They are intentionally modest seed sets — the daily word is
 * picked by date modulo the list length, so a longer list simply means a longer
 * cycle before words repeat. Extend freely; tests/test_words.py validates that
 * every entry is exactly 5 letters of the locale's alphabet and unique.
 *
 * This file is original work (MIT). The game no longer vendors any third-party
 * code or word data.
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
    "герой", "спина", "живот", "страх",
  ],
  uk: [
    "слово", "місто", "вітер", "пісня", "ринок", "банан", "зебра", "лимон",
    "батон", "вагон", "салат", "цукор", "лампа", "карта", "парта", "марка",
    "банка", "булка", "кішка", "ложка", "чашка", "шапка", "сумка", "дочка",
    "гілка", "сітка", "маска", "дошка", "весна", "сосна", "війна", "ягода",
    "осика", "жираф", "панда", "метро", "океан", "берег", "туман", "гроза",
    "трава", "комар", "рибка", "акула", "голос", "розум", "герой", "спина",
    "живіт", "страх", "зірка", "сонце", "хмара", "річка", "земля", "книга",
  ],
  en: [
    "about", "above", "alarm", "apple", "beach", "bread", "brick", "brush",
    "chair", "chess", "clock", "cloud", "dance", "dream", "eagle", "earth",
    "fairy", "field", "flame", "flute", "ghost", "grape", "green", "heart",
    "honey", "house", "juice", "knife", "lemon", "light", "money", "mouse",
    "music", "night", "ocean", "paper", "peace", "piano", "pizza", "plant",
    "river", "robot", "salad", "sheep", "shirt", "smile", "snake", "stone",
    "storm", "sugar", "sunny", "table", "tiger", "train", "water", "whale",
    "wheat", "world", "zebra",
  ],
};
