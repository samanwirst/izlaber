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
        bot_name="Izlaber",
        short_description=(
            "Mahsulot qidiruvi: nom, foto yoki ovoz yuboring, bot 5 ta mos kartochkani "
            "topadi."
        ),
        description=(
            "Kerakli mahsulotni tez toping. Mahsulot nomini, ovozli xabarni yoki "
            "fotosini yuboring - bot katalogdan mos kartochkalarni narx, reyting, rasm "
            "va havola bilan topadi. «Yana» tugmasi keyingi 5 ta natijani ko'rsatadi. "
            "Matnli qidiruv tez ishlaydi, foto va murakkab so'rovlarda qo'shimcha "
            "moslashtirish ishlatiladi."
        ),
        command_descriptions={
            "start": "Botni ishga tushirish va qidiruvni boshlash",
            "help": "Qidiruv bo'yicha yordam va misollar",
            "lang": "Tilni tanlash",
            "consent": "Ma'lumotlar va reklama roziligini boshqarish",
        },
        start_text=(
            "Assalomu alaykum! Sizga kerakli mahsulotni topishga yordam beraman.\n\n"
            "Mahsulot nomini yozing, ovozli xabar yuboring yoki fotosini yuboring - masalan: "
            "<b>oq krossovka 300 minggacha</b> yoki <b>v yoqali sviter</b>.\n\n"
            "Men 5 ta mos kartochka yuboraman. Tilni o'zgartirish uchun /lang yozing."
        ),
        help_text=(
            "<b>Qanday ishlaydi</b>\n"
            "1. Mahsulot nomi yoki belgilarini yozing.\n"
            "2. Yoki ovozli xabar yuboring - bot uni matnga aylantiradi.\n"
            "3. Yoki mahsulot fotosini yuboring - bot uni qidiruv so'roviga aylantiradi.\n"
            "4. Bot 5 ta mos kartochka yuboradi.\n"
            "5. <b>Yana</b> tugmasi keyingi 5 ta natijani ko'rsatadi.\n"
            "6. Tilni almashtirish uchun /lang yozing.\n\n"
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
            "guest_need_query_title": "Nimani qidiramiz?",
            "guest_need_query_text": (
                "Bot nomi yoniga mahsulot yozing, masalan: @bot iphone 15."
            ),
            "guest_catalog_unavailable_title": "Katalog vaqtincha ishlamayapti",
            "guest_catalog_unavailable_text": (
                "Hozir katalogdan mahsulot olib bo'lmadi. Keyinroq urinib ko'ring."
            ),
            "guest_empty_title": "Topilmadi: {query}",
            "guest_top_title": "Top-{count}: {query}",
            "guest_empty_description": "Katalogda mos mahsulot topilmadi.",
            "guest_results_header": "«{query}» bo'yicha {count} ta mahsulot topildi:",
            "guest_no_results": "Katalogda <b>{query}</b> bo'yicha mahsulot topilmadi.",
            "language_prompt": (
                "Tilni tanlang. Choose a language. Выберите язык."
            ),
            "language_changed": "Til yangilandi: <b>{language}</b>.",
            "search_processing": "Eng yaxshi variantlarni tanlayapman...",
            "search_more_processing": "Yana variantlarni qidiryapman...",
            "photo_processing": "Rasmga qarayapman va mos variantlarni qidiryapman...",
            "voice_processing": "Ovozli xabarni tinglayapman...",
            "photo_ai_unavailable": (
                "Foto orqali qidiruv hozir ishlamayapti. Mahsulot nomini matn bilan yozing."
            ),
            "photo_download_failed": (
                "Fotoni yuklab bo'lmadi. Yana urinib ko'ring yoki mahsulot nomini yozing."
            ),
            "photo_too_large": (
                "Bu foto juda katta. Iltimos, kichikroq foto yuboring yoki mahsulot nomini yozing."
            ),
            "photo_understanding_failed": (
                "Fotodagi mahsulotni aniq tushuna olmadim. Nomi yoki muhim belgilarini yozing."
            ),
            "photo_found_intro": (
                "Foto bo'yicha shunday qidiryapman: <b>{query}</b>. Birinchi {count} ta natija:"
            ),
            "photo_no_results": (
                "Foto bo'yicha shunday tushundim: <b>{query}</b>, lekin yetarlicha o'xshash "
                "mahsulot topilmadi. Boshqa burchakdan foto yuboring yoki nomini yozing."
            ),
            "photo_visual_found_intro": (
                "Foto bo'yicha vizual moslik topildi. Birinchi {count} ta natija:"
            ),
            "photo_visual_no_results": (
                "Foto bo'yicha o'xshash mahsulot topilmadi. Boshqa foto yuboring yoki "
                "mahsulot nomini yozing."
            ),
            "photo_visual_unavailable": (
                "Foto orqali qidiruv hozir ishlamayapti. Mahsulot nomini yozing."
            ),
            "voice_ai_unavailable": (
                "Ovozli qidiruv hozir ishlamayapti. Mahsulot nomini matn bilan yozing."
            ),
            "voice_download_failed": (
                "Ovozli xabarni yuklab bo'lmadi. Yana urinib ko'ring yoki matn yuboring."
            ),
            "voice_too_large": (
                "Ovozli xabar juda katta. Qisqaroq xabar yuboring yoki matn yozing."
            ),
            "voice_too_long": (
                "Ovozli xabar juda uzun. Qisqaroq xabar yuboring yoki matn yozing."
            ),
            "voice_transcription_failed": (
                "Ovozli xabarni aniq tushuna olmadim. Qisqaroq ayting yoki matn yuboring."
            ),
            "voice_found_intro": (
                "Ovozli xabarni shunday tushundim: <b>{query}</b>. Birinchi {count} ta natija:"
            ),
            "consent_required": (
                "<b>Rozilik kerak</b>\n\n"
                "Izlaber ishlashi uchun shaxsiy ma'lumotlaringizni qayta ishlashga va "
                "homiylik reklamasini ko'rsatishga rozilik kerak. Biz Telegram ID, profil "
                "tili, xabarlar, qidiruv so'rovlari, yuborilgan foto/ovozli xabarlar va "
                "kartochkalarga bosishlar haqidagi texnik ma'lumotlardan qidiruv, servisni "
                "yaxshilash, analitika va reklama uchun foydalanamiz.\n\n"
                "Rozilikni istalgan vaqtda /consent orqali bekor qilishingiz mumkin. "
                "Rozilik bo'lmasa, bot so'rovlarni qayta ishlamaydi."
            ),
            "consent_accept_button": "Roziman",
            "consent_decline_button": "Rad etaman",
            "consent_revoke_button": "Rozilikni bekor qilish",
            "consent_privacy_button": "Maxfiylik",
            "consent_ads_button": "Reklama",
            "consent_first_alert": "Avval rozilikni tasdiqlang.",
            "consent_accepted": "Rozilik saqlandi.",
            "consent_ready": "Endi mahsulot nomi, fotosi yoki ovozli xabar yuboring.",
            "consent_declined": (
                "Rozilik berilmadi. Bot so'rovlarni qayta ishlamaydi. Davom etish uchun "
                "rozilikni tasdiqlang."
            ),
            "consent_revoked": (
                "Rozilik bekor qilindi. Bot so'rovlarni qayta ishlamaydi. Davom etish "
                "uchun rozilikni qayta tasdiqlang."
            ),
            "consent_status_active": (
                "Rozilik faol. Uni bekor qilsangiz, bot mahsulot qidiruvlarini qayta "
                "ishlashni to'xtatadi."
            ),
            "consent_save_failed": (
                "Rozilikni saqlab bo'lmadi. Server vaqtincha ishlamayapti, keyinroq urinib ko'ring."
            ),
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
        bot_name="Izlaber",
        short_description=(
            "Поиск товаров: напишите товар или отправьте фото, бот найдет 5 карточек."
        ),
        description=(
            "Быстро находите товары. Напишите название или признаки "
            "товара, отправьте голосовое сообщение либо фото - бот покажет карточки с "
            "ценой, рейтингом, "
            "обложкой и ссылкой. Кнопка «Еще» отправляет следующие 5 результатов. "
            "Текстовый поиск быстрый, для фото и сложных запросов подключается "
            "дополнительная обработка."
        ),
        command_descriptions={
            "start": "Запустить бота и начать поиск",
            "help": "Помощь по поиску и примеры запросов",
            "lang": "Выбрать язык",
            "consent": "Управлять согласием на данные и рекламу",
        },
        start_text=(
            "Здравствуйте! Я помогу найти нужный товар.\n\n"
            "Напишите название или признаки товара, отправьте голосовое сообщение "
            "либо фото - например: "
            "<b>белые кроссовки до 300 тысяч</b> или <b>свитер v вырез</b>.\n\n"
            "Я отправлю 5 подходящих карточек. Чтобы сменить язык, напишите /lang."
        ),
        help_text=(
            "<b>Как это работает</b>\n"
            "1. Напишите название товара или важные признаки.\n"
            "2. Или отправьте голосовое сообщение - бот переведет его в текст.\n"
            "3. Или отправьте фото товара - бот превратит его в поисковый запрос.\n"
            "4. Бот отправит 5 подходящих карточек.\n"
            "5. Кнопка <b>Еще</b> покажет следующие 5 результатов по этому же запросу.\n"
            "6. Для смены языка напишите /lang.\n\n"
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
            "guest_need_query_title": "Что искать?",
            "guest_need_query_text": (
                "Напишите товар рядом с упоминанием бота, например: @bot iphone 15."
            ),
            "guest_catalog_unavailable_title": "Каталог временно недоступен",
            "guest_catalog_unavailable_text": (
                "Не смог получить товары из каталога. Попробуйте повторить запрос позже."
            ),
            "guest_empty_title": "Ничего не найдено: {query}",
            "guest_top_title": "Топ-{count}: {query}",
            "guest_empty_description": "В каталоге нет подходящих товаров.",
            "guest_results_header": "Нашел {count} {noun} по запросу <b>{query}</b>:",
            "guest_no_results": "В каталоге пока нет товаров по запросу <b>{query}</b>.",
            "language_prompt": "Выберите язык. Tilni tanlang. Choose a language.",
            "language_changed": "Язык обновлен: <b>{language}</b>.",
            "search_processing": "Выбираю лучшие варианты...",
            "search_more_processing": "Ищу еще варианты...",
            "photo_processing": "Смотрю фото и ищу похожие товары...",
            "voice_processing": "Распознаю голосовое сообщение...",
            "photo_ai_unavailable": (
                "Поиск по фото сейчас недоступен. Напишите название товара текстом."
            ),
            "photo_download_failed": (
                "Не смог загрузить фото. Попробуйте еще раз или напишите название товара."
            ),
            "photo_too_large": (
                "Фото слишком большое. Отправьте фото поменьше или напишите название товара."
            ),
            "photo_understanding_failed": (
                "Не смог уверенно понять товар на фото. Напишите название или важные признаки."
            ),
            "photo_found_intro": (
                "По фото ищу как: <b>{query}</b>. Показываю первые {count}:"
            ),
            "photo_no_results": (
                "По фото понял: <b>{query}</b>, но достаточно похожий товар в каталоге "
                "не нашел. Отправьте фото с другого ракурса или напишите название."
            ),
            "photo_visual_found_intro": (
                "Нашел визуально похожие товары по фото. Показываю первые {count}:"
            ),
            "photo_visual_no_results": (
                "Похожий товар по фото не нашел. Отправьте другое фото или напишите "
                "название товара."
            ),
            "photo_visual_unavailable": (
                "Поиск по фото сейчас недоступен. Напишите название товара текстом."
            ),
            "voice_ai_unavailable": (
                "Поиск по голосу сейчас недоступен. Напишите название товара текстом."
            ),
            "voice_download_failed": (
                "Не смог загрузить голосовое сообщение. Попробуйте еще раз или напишите текстом."
            ),
            "voice_too_large": (
                "Голосовое сообщение слишком большое. Отправьте более короткое "
                "или напишите текстом."
            ),
            "voice_too_long": (
                "Голосовое сообщение слишком длинное. Отправьте более короткое "
                "или напишите текстом."
            ),
            "voice_transcription_failed": (
                "Не смог уверенно распознать голосовое сообщение. Скажите короче "
                "или напишите текстом."
            ),
            "voice_found_intro": (
                "Голосовое распознал как: <b>{query}</b>. Показываю первые {count}:"
            ),
            "consent_required": (
                "<b>Нужно согласие</b>\n\n"
                "Чтобы Izlaber работал, нужно согласие на обработку персональных данных "
                "и на показ спонсируемой рекламы. Мы используем Telegram ID, язык профиля, "
                "сообщения, поисковые запросы, отправленные фото/голосовые сообщения и "
                "технические данные о нажатиях на карточки для поиска, работы сервиса, "
                "аналитики и рекламы.\n\n"
                "Согласие можно отозвать в любой момент через /consent. Без согласия бот "
                "не обрабатывает запросы."
            ),
            "consent_accept_button": "Согласен",
            "consent_decline_button": "Не согласен",
            "consent_revoke_button": "Отозвать согласие",
            "consent_privacy_button": "Конфиденциальность",
            "consent_ads_button": "Реклама",
            "consent_first_alert": "Сначала подтвердите согласие.",
            "consent_accepted": "Согласие сохранено.",
            "consent_ready": "Теперь отправьте название товара, фото или голосовое сообщение.",
            "consent_declined": (
                "Согласие не дано. Бот не будет обрабатывать запросы. Чтобы продолжить, "
                "подтвердите согласие."
            ),
            "consent_revoked": (
                "Согласие отозвано. Бот не будет обрабатывать запросы. Чтобы продолжить, "
                "подтвердите согласие заново."
            ),
            "consent_status_active": (
                "Согласие активно. Если отозвать его, бот перестанет обрабатывать "
                "поисковые запросы."
            ),
            "consent_save_failed": (
                "Не удалось сохранить согласие. Сервер временно недоступен, попробуйте позже."
            ),
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
        bot_name="Izlaber",
        short_description=(
            "Search products by name, voice, or photo and get 5 relevant product cards."
        ),
        description=(
            "Find products faster. Send a product name, a voice message, "
            "details, or a photo, "
            "and the bot returns cards with price, rating, cover image, and link. Tap “More” "
            "to see the next 5 results. Text search is fast; photos and harder queries use "
            "additional matching."
        ),
        command_descriptions={
            "start": "Start the bot and search products",
            "help": "Search help and example queries",
            "lang": "Choose language",
            "consent": "Manage data and sponsored ads consent",
        },
        start_text=(
            "Hi! I can help you find the right product.\n\n"
            "Send a product name, a voice message, details, or a photo - for example: "
            "<b>white sneakers "
            "under 300k</b> or <b>v neck sweater</b>.\n\n"
            "I will send 5 relevant product cards. To switch language, send /lang."
        ),
        help_text=(
            "<b>How it works</b>\n"
            "1. Send a product name or important details.\n"
            "2. Or send a voice message - the bot turns it into text.\n"
            "3. Or send a product photo - the bot turns it into a search query.\n"
            "4. The bot returns 5 relevant product cards.\n"
            "5. The <b>More</b> button shows the next 5 results for the same query.\n"
            "6. To change language, send /lang.\n\n"
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
            "guest_need_query_title": "What should I search?",
            "guest_need_query_text": (
                "Write a product next to the bot mention, for example: @bot iphone 15."
            ),
            "guest_catalog_unavailable_title": "Catalog temporarily unavailable",
            "guest_catalog_unavailable_text": (
                "Could not load products from the catalog. Try again later."
            ),
            "guest_empty_title": "Nothing found: {query}",
            "guest_top_title": "Top-{count}: {query}",
            "guest_empty_description": "No matching products in the catalog.",
            "guest_results_header": "Found {count} {noun} for <b>{query}</b>:",
            "guest_no_results": "No products found in the catalog for <b>{query}</b>.",
            "language_prompt": "Choose a language. Tilni tanlang. Выберите язык.",
            "language_changed": "Language updated: <b>{language}</b>.",
            "search_processing": "Picking the best matches...",
            "search_more_processing": "Looking for more matches...",
            "photo_processing": "Checking the photo and finding similar products...",
            "voice_processing": "Transcribing the voice message...",
            "photo_ai_unavailable": (
                "Photo search is unavailable right now. Type the product name instead."
            ),
            "photo_download_failed": (
                "Could not download the photo. Try again or type the product name."
            ),
            "photo_too_large": (
                "This photo is too large. Send a smaller photo or type the product name."
            ),
            "photo_understanding_failed": (
                "I could not identify the product confidently. Type its name or key details."
            ),
            "photo_found_intro": (
                "From the photo, I am searching for: <b>{query}</b>. Showing the first {count}:"
            ),
            "photo_no_results": (
                "From the photo, I understood: <b>{query}</b>, but did not find a close "
                "visual match. Send another angle or type the product name."
            ),
            "photo_visual_found_intro": (
                "Found visually similar products from the photo. Showing the first {count}:"
            ),
            "photo_visual_no_results": (
                "No similar product found from this photo. Send another photo or type the "
                "product name."
            ),
            "photo_visual_unavailable": (
                "Photo search is unavailable right now. Type the product name instead."
            ),
            "voice_ai_unavailable": (
                "Voice search is unavailable right now. Type the product name instead."
            ),
            "voice_download_failed": (
                "Could not download the voice message. Try again or type the product name."
            ),
            "voice_too_large": (
                "This voice message is too large. Send a shorter one or type the product name."
            ),
            "voice_too_long": (
                "This voice message is too long. Send a shorter one or type the product name."
            ),
            "voice_transcription_failed": (
                "I could not transcribe the voice message confidently. Try a shorter "
                "message or type it."
            ),
            "voice_found_intro": (
                "I transcribed the voice message as: <b>{query}</b>. Showing the first {count}:"
            ),
            "consent_required": (
                "<b>Consent required</b>\n\n"
                "To use Izlaber, you need to consent to personal data processing and "
                "sponsored advertising. We use your Telegram ID, profile language, messages, "
                "search queries, submitted photos/voice messages, and technical card-click "
                "data for search, service operation, analytics, and advertising.\n\n"
                "You can revoke consent anytime with /consent. Without consent, the bot "
                "does not process requests."
            ),
            "consent_accept_button": "I agree",
            "consent_decline_button": "I do not agree",
            "consent_revoke_button": "Revoke consent",
            "consent_privacy_button": "Privacy",
            "consent_ads_button": "Ads",
            "consent_first_alert": "Confirm consent first.",
            "consent_accepted": "Consent saved.",
            "consent_ready": "Now send a product name, photo, or voice message.",
            "consent_declined": (
                "Consent was not given. The bot will not process requests. Confirm consent "
                "to continue."
            ),
            "consent_revoked": (
                "Consent revoked. The bot will not process requests. Confirm consent again "
                "to continue."
            ),
            "consent_status_active": (
                "Consent is active. If you revoke it, the bot will stop processing search "
                "requests."
            ),
            "consent_save_failed": (
                "Could not save consent. The server is temporarily unavailable, try again later."
            ),
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
    user_id = getattr(user, "id", None)
    if user_id is not None:
        from bot.services.language_store import language_preferences

        stored_language = language_preferences.get(user_id)
        if stored_language is not None:
            return stored_language
    return normalize_language_code(getattr(user, "language_code", None))


def locale_for(language_code: str | None) -> LocaleCopy:
    return LOCALES[normalize_language_code(language_code)]


def profile_locale_for(language_code: str | None) -> LocaleCopy:
    if language_code is None:
        return LOCALES[DEFAULT_LANGUAGE]
    return locale_for(language_code)


def more_button_values() -> set[str]:
    return {
        _normalize_more_button_text(locale.more_button)
        for locale in LOCALES.values()
    } | {
        "more",
        "yana",
        "еще",
        "ещё",
    }


def _normalize_more_button_text(text: str) -> str:
    return text.strip().casefold().replace("ё", "е")


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
