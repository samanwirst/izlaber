from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any

DEFAULT_LANGUAGE = "uz"
SUPPORTED_LANGUAGES = ("uz", "ru", "en")
PROFILE_LANGUAGE_CODES: tuple[str | None, ...] = (None, *SUPPORTED_LANGUAGES)


@dataclass(frozen=True, slots=True)
class LocaleCopy:
    code: str
    bot_name: str
    short_description: str
    description: str
    command_descriptions: dict[str, str]
    start_text: str
    help_text: str
    main_buttons: tuple[str, str]
    main_placeholder: str
    more_button: str
    more_placeholder: str
    messages: dict[str, str]
    product_labels: dict[str, str]


LOCALES: dict[str, LocaleCopy] = {
    "uz": LocaleCopy(
        code="uz",
        bot_name="Uzum Finder",
        short_description=(
            "Uzum Market bo'yicha tezkor qidiruv: nom yozing, bot 5 ta mos kartochkani "
            "yuboradi."
        ),
        description=(
            "Uzum Market'dan kerakli mahsulotni tez toping. Mahsulot nomini yoki "
            "tavsifini yozing - bot katalogdan mos kartochkalarni narx, reyting, rasm "
            "va havola bilan yuboradi. «Yana» tugmasi keyingi 5 ta natijani ko'rsatadi. "
            "Qidiruv tez ishlaydi, murakkab so'rovlarda esa AI yordam beradi."
        ),
        command_descriptions={
            "start": "Botni ishga tushirish va qidiruvni boshlash",
            "help": "Qidiruv bo'yicha yordam va misollar",
        },
        start_text=(
            "Assalomu alaykum! Men Uzum Market bo'yicha mahsulot topishga yordam "
            "beraman.\n\n"
            "Mahsulot nomini yozing - masalan: <b>oq krossovka 300 minggacha</b> yoki "
            "<b>v yoqali sviter</b>.\n\n"
            "Men 5 ta mos kartochka yuboraman. Keyingilarini ko'rish uchun "
            "<b>Yana</b> tugmasini bosing."
        ),
        help_text=(
            "<b>Qanday ishlaydi</b>\n"
            "1. Mahsulot nomi yoki belgilarini yozing.\n"
            "2. Bot 5 ta mos kartochka yuboradi.\n"
            "3. <b>Yana</b> tugmasi keyingi 5 ta natijani ko'rsatadi.\n\n"
            "<b>Misollar</b>\n"
            "<code>iphone</code>\n"
            "<code>oq krossovka 300 minggacha</code>\n"
            "<code>v yoqali sviter</code>\n\n"
            "Maslahat: rang, narx, material yoki modelni yozsangiz, natija aniqroq "
            "bo'ladi."
        ),
        main_buttons=("iphone", "noutbuk"),
        main_placeholder="Qidirish uchun mahsulot nomini yozing",
        more_button="Yana",
        more_placeholder="Yana tugmasini bosing yoki yangi mahsulot yozing",
        messages={
            "empty_query": "Mahsulot nomini yozing.",
            "no_session": "Avval mahsulot nomini yozing, keyin «{more}» tugmasini bosing.",
            "no_more": "«{query}» bo'yicha boshqa kartochka topilmadi.",
            "no_results": "Katalogda «{query}» bo'yicha mahsulot topilmadi.",
            "found_intro": (
                "«{query}» bo'yicha kartochkalar topildi. Birinchi {count} ta natija:"
            ),
            "catalog_unavailable": "Katalog hozir ishlamayapti. Keyinroq urinib ko'ring.",
            "guest_need_query_title": "Uzum'da nima qidiramiz?",
            "guest_need_query_text": (
                "Bot nomi yoniga mahsulot yozing, masalan: @bot iphone 15."
            ),
            "guest_catalog_unavailable_title": "Katalog vaqtincha ishlamayapti",
            "guest_catalog_unavailable_text": (
                "Hozir katalogdan mahsulot olib bo'lmadi. Keyinroq urinib ko'ring."
            ),
            "guest_empty_title": "Topilmadi: {query}",
            "guest_top_title": "Top-{count} Uzum'da: {query}",
            "guest_empty_description": "Katalogda mos mahsulot topilmadi.",
            "guest_results_header": "«{query}» bo'yicha {count} ta mahsulot topildi:",
            "guest_no_results": "Katalogda <b>{query}</b> bo'yicha mahsulot topilmadi.",
        },
        product_labels={
            "price": "Narx",
            "old_price": "Avvalgi narx",
            "rating": "reyting",
            "reviews_one": "sharh",
            "reviews_few": "sharh",
            "reviews_many": "sharh",
            "category": "Kategoriya",
            "currency_uzs": "so'm",
        },
    ),
    "ru": LocaleCopy(
        code="ru",
        bot_name="Uzum Finder",
        short_description=(
            "Быстрый поиск по Uzum Market: напишите товар, бот пришлет 5 подходящих "
            "карточек."
        ),
        description=(
            "Быстро находите товары на Uzum Market. Напишите название или признаки "
            "товара - бот покажет подходящие карточки с ценой, рейтингом, обложкой и "
            "ссылкой. Кнопка «Еще» отправляет следующие 5 результатов. Поиск работает "
            "быстро, а для сложных запросов подключается AI."
        ),
        command_descriptions={
            "start": "Запустить бота и начать поиск",
            "help": "Помощь по поиску и примеры запросов",
        },
        start_text=(
            "Здравствуйте! Я помогаю находить товары на Uzum Market.\n\n"
            "Напишите название или признаки товара - например: <b>белые кроссовки до "
            "300 тысяч</b> или <b>свитер v вырез</b>.\n\n"
            "Я отправлю 5 подходящих карточек. Чтобы увидеть следующие, нажмите "
            "<b>Еще</b>."
        ),
        help_text=(
            "<b>Как это работает</b>\n"
            "1. Напишите название товара или важные признаки.\n"
            "2. Бот отправит 5 подходящих карточек.\n"
            "3. Кнопка <b>Еще</b> покажет следующие 5 результатов по этому же запросу.\n\n"
            "<b>Примеры</b>\n"
            "<code>iphone</code>\n"
            "<code>белые кроссовки до 300 тысяч</code>\n"
            "<code>свитер v вырез</code>\n\n"
            "Совет: добавляйте цвет, цену, материал или модель - так результаты будут "
            "точнее."
        ),
        main_buttons=("iphone", "ноутбук"),
        main_placeholder="Введите товар для поиска",
        more_button="Еще",
        more_placeholder="Нажмите Еще или введите новый товар",
        messages={
            "empty_query": "Напишите название товара.",
            "no_session": "Сначала напишите название товара, потом нажимайте «{more}».",
            "no_more": "Больше карточек по запросу «{query}» не нашел.",
            "no_results": "В каталоге пока нет товаров по запросу «{query}».",
            "found_intro": "Нашел карточки по запросу «{query}». Показываю первые {count}:",
            "catalog_unavailable": "Каталог сейчас недоступен. Попробуйте позже.",
            "guest_need_query_title": "Что искать на Uzum?",
            "guest_need_query_text": (
                "Напишите товар рядом с упоминанием бота, например: @bot iphone 15."
            ),
            "guest_catalog_unavailable_title": "Каталог временно недоступен",
            "guest_catalog_unavailable_text": (
                "Не смог получить товары из каталога. Попробуйте повторить запрос позже."
            ),
            "guest_empty_title": "Ничего не найдено: {query}",
            "guest_top_title": "Топ-{count} на Uzum: {query}",
            "guest_empty_description": "В каталоге нет подходящих товаров.",
            "guest_results_header": "Нашел {count} {noun} по запросу <b>{query}</b>:",
            "guest_no_results": "В каталоге пока нет товаров по запросу <b>{query}</b>.",
        },
        product_labels={
            "price": "Цена",
            "old_price": "Старая цена",
            "rating": "рейтинг",
            "reviews_one": "отзыв",
            "reviews_few": "отзыва",
            "reviews_many": "отзывов",
            "category": "Категория",
            "currency_uzs": "сум",
        },
    ),
    "en": LocaleCopy(
        code="en",
        bot_name="Uzum Finder",
        short_description=(
            "Fast Uzum Market search: type a product name and get 5 relevant product "
            "cards."
        ),
        description=(
            "Find products on Uzum Market faster. Send a product name or details, and "
            "the bot returns relevant cards with price, rating, cover image, and link. "
            "Tap “More” to see the next 5 results. Search is fast, with AI used for "
            "harder queries."
        ),
        command_descriptions={
            "start": "Start the bot and search products",
            "help": "Search help and example queries",
        },
        start_text=(
            "Hi! I help you find products on Uzum Market.\n\n"
            "Send a product name or details - for example: <b>white sneakers under "
            "300k</b> or <b>v neck sweater</b>.\n\n"
            "I will send 5 relevant product cards. Tap <b>More</b> to see the next "
            "results."
        ),
        help_text=(
            "<b>How it works</b>\n"
            "1. Send a product name or important details.\n"
            "2. The bot returns 5 relevant product cards.\n"
            "3. The <b>More</b> button shows the next 5 results for the same query.\n\n"
            "<b>Examples</b>\n"
            "<code>iphone</code>\n"
            "<code>white sneakers under 300k</code>\n"
            "<code>v neck sweater</code>\n\n"
            "Tip: add color, price, material, or model to get more precise results."
        ),
        main_buttons=("iphone", "laptop"),
        main_placeholder="Type a product to search",
        more_button="More",
        more_placeholder="Tap More or type a new product",
        messages={
            "empty_query": "Type a product name.",
            "no_session": "Send a product name first, then tap “{more}”.",
            "no_more": "No more product cards found for “{query}”.",
            "no_results": "No products found in the catalog for “{query}”.",
            "found_intro": "Found product cards for “{query}”. Showing the first {count}:",
            "catalog_unavailable": "The catalog is unavailable right now. Try again later.",
            "guest_need_query_title": "What should I search on Uzum?",
            "guest_need_query_text": (
                "Write a product next to the bot mention, for example: @bot iphone 15."
            ),
            "guest_catalog_unavailable_title": "Catalog temporarily unavailable",
            "guest_catalog_unavailable_text": (
                "Could not load products from the catalog. Try again later."
            ),
            "guest_empty_title": "Nothing found: {query}",
            "guest_top_title": "Top-{count} on Uzum: {query}",
            "guest_empty_description": "No matching products in the catalog.",
            "guest_results_header": "Found {count} {noun} for <b>{query}</b>:",
            "guest_no_results": "No products found in the catalog for <b>{query}</b>.",
        },
        product_labels={
            "price": "Price",
            "old_price": "Old price",
            "rating": "rating",
            "reviews_one": "review",
            "reviews_few": "reviews",
            "reviews_many": "reviews",
            "category": "Category",
            "currency_uzs": "UZS",
        },
    ),
}


def normalize_language_code(language_code: str | None) -> str:
    if not language_code:
        return DEFAULT_LANGUAGE
    base_code = language_code.casefold().replace("_", "-").split("-", maxsplit=1)[0]
    if base_code in LOCALES:
        return base_code
    return DEFAULT_LANGUAGE


def language_from_message(message: Any) -> str:
    user = getattr(message, "from_user", None)
    return normalize_language_code(getattr(user, "language_code", None))


def locale_for(language_code: str | None) -> LocaleCopy:
    return LOCALES[normalize_language_code(language_code)]


def profile_locale_for(language_code: str | None) -> LocaleCopy:
    if language_code is None:
        return LOCALES[DEFAULT_LANGUAGE]
    return locale_for(language_code)


def more_button_values() -> set[str]:
    return {locale.more_button.casefold() for locale in LOCALES.values()}


def format_message(
    key: str,
    language_code: str | None,
    *,
    html: bool = True,
    **values: object,
) -> str:
    locale = locale_for(language_code)
    template = locale.messages[key]
    prepared: dict[str, object] = {"more": locale.more_button}
    for name, value in values.items():
        if html and isinstance(value, str):
            prepared[name] = escape(value)
        else:
            prepared[name] = value
    return template.format(**prepared)


def product_label(key: str, language_code: str | None) -> str:
    return locale_for(language_code).product_labels[key]


def review_text(count: int, language_code: str | None) -> str:
    language = normalize_language_code(language_code)
    locale = LOCALES[language]
    if language == "ru":
        if count % 10 == 1 and count % 100 != 11:
            label = locale.product_labels["reviews_one"]
        elif count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
            label = locale.product_labels["reviews_few"]
        else:
            label = locale.product_labels["reviews_many"]
    elif language == "en":
        label = locale.product_labels["reviews_one" if count == 1 else "reviews_many"]
    else:
        label = locale.product_labels["reviews_many"]
    return f"{count} {label}"


def product_noun(count: int, language_code: str | None) -> str:
    language = normalize_language_code(language_code)
    if language == "ru":
        if count % 10 == 1 and count % 100 != 11:
            return "товар"
        if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
            return "товара"
        return "товаров"
    if language == "en":
        return "product" if count == 1 else "products"
    return "mahsulot"
