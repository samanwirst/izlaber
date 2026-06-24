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
            "O'zbekiston marketplace'laridan tovar qidirish: matn, foto yoki ovoz. "
            "Narx, reyting va havolalar bir joyda."
        ),
        description=(
            "Izlaber turli ilovalarda uzoq qidirmasdan kerakli mahsulotni topishga "
            "yordam beradi. Nomini yozing, foto yoki ovoz yuboring - bot O'zbekiston "
            "marketplace'laridagi kartochkalarni narx, reyting va havolalar bilan "
            "ko'rsatadi. Variantlarni solishtiring, mos mahsulotni oching va xaridni "
            "sotuvchi platformasida yakunlang. Tez, qulay va Telegram ichida."
        ),
        command_descriptions={
            "start": "Tovar qidiruvini boshlash",
            "help": "Izlaber'dan qanday foydalanish",
            "lang": "Bot tilini o'zgartirish",
            "consent": "Ma'lumotlar va reklama roziligini boshqarish",
        },
        start_text=(
            "Izlaber'ga xush kelibsiz. Men O'zbekiston marketplace'laridan tovarlarni "
            "Telegram ichida tez topishga yordam beraman. Mahsulot nomini yozing, foto "
            "yoki ovozli xabar yuboring - narx, reyting va havolalari bor mos "
            "variantlarni ko'rsataman. Qulay variantni tanlang va xaridni sotuvchi "
            "platformasida davom ettiring."
        ),
        help_text=(
            "<b>Izlaber'dan qanday foydalanish:</b>\n\n"
            "1. Qidirayotgan narsangizni yozing: masalan, “krossovka”, “changyutgich”, "
            "“iPhone chexoli”.\n"
            "2. Yoki mahsulot fotosini yuboring - o'xshash variantlarni topishga harakat "
            "qilaman.\n"
            "3. Yoki ovozli xabar yuboring - so'rovni tanib, qidiruvni boshlayman.\n"
            "4. Mahsulot kartochkasini oching, narx, reyting va havolani solishtiring.\n"
            "5. Xarid marketplace sayti yoki ilovasida amalga oshiriladi.\n\n"
            "Izlaber mahsulotlarni bevosita sotmaydi. Bot variantlarni tezroq topish va "
            "solishtirishga yordam beradi."
        ),
        main_buttons=("🔎 Mahsulot qidirish", "📷 Foto orqali qidirish"),
        main_placeholder="Mahsulot yozing, foto yoki ovoz yuboring",
        more_button="Yana ko'rsatish",
        more_placeholder="Mahsulot yozing, foto yoki ovoz yuboring",
        messages={
            "empty_query": "Mahsulot nomini yozing.",
            "no_session": "Avval mahsulot nomini yozing, keyin «{more}» tugmasini bosing.",
            "no_more": "«{query}» bo'yicha boshqa kartochka topilmadi.",
            "no_results": (
                "Aniq mos keladigan mahsulot topilmadi. So'rovni soddaroq yozing, boshqa "
                "foto yuboring yoki brend, rang, o'lcham yoxud kategoriyani ko'rsating."
            ),
            "found_intro": ("«{query}» bo'yicha kartochkalar topildi. Birinchi {count} ta natija:"),
            "sponsored_found_intro": "Reklama taklifi. U odatiy natijalardan alohida ko'rsatiladi:",
            "catalog_unavailable": "Katalog hozir ishlamayapti. Keyinroq urinib ko'ring.",
            "rate_limited": (
                "Juda ko'p so'rov yubordingiz. Iltimos, {retry_after}dan keyin urinib ko'ring."
            ),
            "ai_rate_limited": (
                "Aqlli qidiruv limiti tugadi. {retry_after}dan keyin urinib ko'ring."
            ),
            "search_in_progress": (
                "Oldingi qidiruv hali tugamadi. Iltimos, natijani kuting."
            ),
            "guest_need_query_title": "Nimani qidiramiz?",
            "guest_need_query_text": ("Bot nomi yoniga mahsulot yozing, masalan: @bot iphone 15."),
            "guest_catalog_unavailable_title": "Katalog vaqtincha ishlamayapti",
            "guest_catalog_unavailable_text": (
                "Hozir katalogdan mahsulot olib bo'lmadi. Keyinroq urinib ko'ring."
            ),
            "guest_empty_title": "Topilmadi: {query}",
            "guest_top_title": "Top-{count}: {query}",
            "guest_empty_description": "Katalogda mos mahsulot topilmadi.",
            "guest_results_header": "«{query}» bo'yicha {count} ta mahsulot topildi:",
            "guest_no_results": "Katalogda <b>{query}</b> bo'yicha mahsulot topilmadi.",
            "language_prompt": "Botdan foydalanish uchun qulay tilni tanlang.",
            "language_changed": "Til yangilandi: <b>{language}</b>.",
            "search_processing": "Eng yaxshi variantlarni tanlayapman...",
            "search_more_processing": "Yana variantlarni qidiryapman...",
            "photo_processing": "Rasmga qarayapman va mos variantlarni qidiryapman...",
            "voice_processing": "Ovozli xabarni tinglayapman...",
            "menu_button": "🔎 Mahsulot topish",
            "search_cta_button": "🔎 Mahsulot qidirish",
            "photo_search_prompt": (
                "Mahsulot fotosini yuboring - marketplace kartochkalari ichidan o'xshash "
                "variantlarni topishga harakat qilaman."
            ),
            "voice_search_prompt": (
                "Mahsulot nomini ovozli xabar qilib yuboring - so'rovni tanib, qidiruvni "
                "boshlayman."
            ),
            "description_picture_text": (
                "Mahsulotni foto, ovoz yoki nom orqali toping - Izlaber variantlarni bir "
                "joyda ko'rsatadi."
            ),
            "share_text": (
                "Izlaber'ni sinab ko'ring - bot O'zbekiston marketplace'laridan "
                "mahsulotlarni Telegram ichida topadi. Matn, foto yoki ovoz bilan "
                "qidirish mumkin."
            ),
            "referral_invite_text": (
                "Telegramda qulay mahsulot qidiruvini topdim: nom, foto yoki ovoz "
                "yuborasiz - bot narx va havolalari bor variantlarni ko'rsatadi."
            ),
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
            "photo_text_fallback_intro": (
                "Aniq vizual moslik topilmadi. <b>{query}</b> bo'yicha eng yaqin "
                "{count} ta variantni ko'rsataman:"
            ),
            "photo_substitute_intro": (
                "Foto bo'yicha aniq brend/tovar katalogda topilmadi. <b>{query}</b> "
                "turiga yaqin {count} ta o'rinbosar variantni ko'rsataman; bu aniq moslik emas:"
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
            "voice_too_long": ("Ovozli xabar juda uzun. Qisqaroq xabar yuboring yoki matn yozing."),
            "voice_transcription_failed": (
                "Ovozli xabarni aniq tushuna olmadim. Qisqaroq ayting yoki matn yuboring."
            ),
            "voice_found_intro": (
                "Ovozli xabarni shunday tushundim: <b>{query}</b>. Birinchi {count} ta natija:"
            ),
            "consent_required": (
                "Tovar qidirish uchun Izlaber xabarlaringiz, qidiruv so'rovlaringiz, foto "
                "yoki ovozli xabarlaringizni qayta ishlaydi, mahsulot kartochkalarini "
                "ko'rsatadi va havolalarga bosishlarni hisobga olishi mumkin. Botda "
                "reklama takliflari ham bo'lishi mumkin. “Roziman” tugmasini bosib, ushbu "
                "ma'lumotlarni qayta ishlash va reklama ko'rsatishga rozilik berasiz. "
                "Rozilikni /consent buyrug'i orqali bekor qilish mumkin."
            ),
            "consent_accept_button": "✅ Roziman, qidirishni boshlash",
            "consent_privacy_button": "Ma'lumotlar haqida",
            "consent_ads_button": "Reklama haqida",
            "consent_first_alert": "Avval rozilikni tasdiqlang.",
            "consent_accepted": "Rozilik saqlandi.",
            "consent_ready": "Endi mahsulot nomi, fotosi yoki ovozli xabar yuboring.",
            "consent_revoked": (
                "Rozilik bekor qilindi. Ma'lumotlarni qayta ishlashga yana ruxsat "
                "bermaguningizcha yangi qidiruvlar ishlamaydi. Oldin qayta ishlangan "
                "hodisalar siyosat va qonun talablari doirasida saqlanadi."
            ),
            "consent_status_active": (
                "Rozilik faol. Uni bekor qilish uchun <code>/consent revoke</code> "
                "buyrug'ini yuboring. Shundan keyin bot yangi qidiruv so'rovlarini "
                "qayta ishlashni to'xtatadi."
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
            "marketplace": "Marketplace",
            "currency_uzs": "so'm",
            "open_product": "Mahsulotni ochish",
            "sponsored": "Reklama taklifi",
            "footer": (
                "Narx, reyting va mavjudlik marketplace tomonida o'zgarishi mumkin. "
                "Xarid qilishdan oldin ma'lumotlarni tekshiring."
            ),
        },
    ),
    "ru": LocaleCopy(
        code="ru",
        bot_name="Izlaber",
        short_description=(
            "Поиск товаров по маркетплейсам Узбекистана: текстом, фото или голосом. "
            "Цены, рейтинги и ссылки в одном месте."
        ),
        description=(
            "Izlaber помогает найти нужный товар без долгих поисков по разным "
            "приложениям. Напишите название, отправьте фото или голос - бот покажет "
            "карточки товаров из маркетплейсов Узбекистана с ценами, рейтингами и "
            "ссылками. Сравнивайте варианты, открывайте подходящий товар и покупайте "
            "уже на площадке продавца. Быстро, удобно и прямо в Telegram."
        ),
        command_descriptions={
            "start": "Запустить поиск товаров",
            "help": "Как пользоваться Izlaber",
            "lang": "Изменить язык бота",
            "consent": "Управлять согласием на данные и рекламу",
        },
        start_text=(
            "Добро пожаловать в Izlaber. Я помогаю быстро искать товары по "
            "маркетплейсам Узбекистана прямо в Telegram. Напишите название товара, "
            "отправьте фото или голосовое сообщение - я покажу подходящие варианты с "
            "ценами, рейтингами и ссылками. Выбирайте удобный вариант и переходите к "
            "покупке на площадке продавца."
        ),
        help_text=(
            "<b>Как пользоваться Izlaber:</b>\n\n"
            "1. Напишите, что ищете: например, “кроссовки”, “пылесос”, “чехол iPhone”.\n"
            "2. Или отправьте фото товара - я попробую найти похожие варианты.\n"
            "3. Или отправьте голосовое сообщение - я распознаю запрос и запущу поиск.\n"
            "4. Откройте карточку товара, сравните цену, рейтинг и ссылку.\n"
            "5. Покупка проходит на сайте или в приложении маркетплейса.\n\n"
            "Izlaber не продаёт товары напрямую. Бот помогает быстрее найти и сравнить "
            "варианты."
        ),
        main_buttons=("🔎 Искать товар", "📷 Поиск по фото"),
        main_placeholder="Напишите товар, отправьте фото или голос",
        more_button="Показать ещё",
        more_placeholder="Напишите товар, отправьте фото или голос",
        messages={
            "empty_query": "Напишите название товара.",
            "no_session": "Сначала напишите название товара, потом нажимайте «{more}».",
            "no_more": "Больше карточек по запросу «{query}» не нашёл.",
            "no_results": (
                "Я не нашёл точных совпадений. Попробуйте написать запрос проще, "
                "отправить другое фото или указать бренд, цвет, размер либо категорию "
                "товара."
            ),
            "found_intro": "Нашел карточки по запросу «{query}». Показываю первые {count}:",
            "sponsored_found_intro": (
                "Рекламное предложение. Оно показывается отдельно от обычной выдачи:"
            ),
            "catalog_unavailable": "Каталог сейчас недоступен. Попробуйте позже.",
            "rate_limited": ("Слишком много запросов. Попробуйте снова через {retry_after}."),
            "ai_rate_limited": (
                "Лимит умного поиска исчерпан. Попробуйте снова через {retry_after}."
            ),
            "search_in_progress": (
                "Предыдущий поиск еще выполняется. Дождитесь результата, "
                "затем отправьте новый запрос."
            ),
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
            "language_prompt": "Выберите язык, на котором вам удобнее пользоваться ботом.",
            "language_changed": "Язык обновлен: <b>{language}</b>.",
            "search_processing": "Выбираю лучшие варианты...",
            "search_more_processing": "Ищу еще варианты...",
            "photo_processing": "Смотрю фото и ищу похожие товары...",
            "voice_processing": "Распознаю голосовое сообщение...",
            "menu_button": "🔎 Найти товар",
            "search_cta_button": "🔎 Искать товар",
            "photo_search_prompt": (
                "Отправьте фото товара - я попробую найти похожие варианты по карточкам "
                "маркетплейсов."
            ),
            "voice_search_prompt": (
                "Отправьте голосовое сообщение с названием товара - я распознаю запрос и "
                "запущу поиск."
            ),
            "description_picture_text": (
                "Найдите товар по фото, голосу или названию - Izlaber покажет варианты в "
                "одном месте."
            ),
            "share_text": (
                "Попробуй Izlaber - бот ищет товары по маркетплейсам Узбекистана прямо "
                "в Telegram. Можно искать текстом, фото или голосом."
            ),
            "referral_invite_text": (
                "Нашёл удобный поиск товаров в Telegram: отправляешь название, фото или "
                "голос - бот показывает варианты с ценами и ссылками."
            ),
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
            "photo_found_intro": ("По фото ищу как: <b>{query}</b>. Показываю первые {count}:"),
            "photo_text_fallback_intro": (
                "Точного визуального совпадения не нашел. Показываю ближайшие "
                "{count} вариантов по описанию <b>{query}</b>:"
            ),
            "photo_substitute_intro": (
                "Точный товар или бренд по фото в каталоге не нашел. Показываю "
                "{count} похожих заменителей по типу <b>{query}</b>; это не точное совпадение:"
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
                "Чтобы искать товары, Izlaber обрабатывает ваши сообщения, поисковые "
                "запросы, фото или голосовые сообщения, а также показывает карточки "
                "товаров и может учитывать клики по ссылкам. В боте также могут быть "
                "рекламные предложения. Нажимая “Согласен”, вы разрешаете обработку "
                "этих данных и показ рекламы. Согласие можно отозвать командой /consent."
            ),
            "consent_accept_button": "✅ Согласен, начать поиск",
            "consent_privacy_button": "Подробнее о данных",
            "consent_ads_button": "Подробнее о рекламе",
            "consent_first_alert": "Сначала подтвердите согласие.",
            "consent_accepted": "Согласие сохранено.",
            "consent_ready": "Теперь отправьте название товара, фото или голосовое сообщение.",
            "consent_revoked": (
                "Согласие отозвано. Новые поисковые запросы будут недоступны, пока вы "
                "снова не разрешите обработку данных. Уже обработанные события "
                "сохраняются в пределах политики и требований закона."
            ),
            "consent_status_active": (
                "Согласие активно. Чтобы отозвать его, отправьте команду "
                "<code>/consent revoke</code>. После этого бот перестанет обрабатывать "
                "новые поисковые запросы."
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
            "marketplace": "Маркетплейс",
            "currency_uzs": "сум",
            "open_product": "Открыть товар",
            "sponsored": "Рекламное предложение",
            "footer": (
                "Цена, рейтинг и наличие могут измениться на стороне маркетплейса. "
                "Проверьте данные перед покупкой."
            ),
        },
    ),
    "en": LocaleCopy(
        code="en",
        bot_name="Izlaber",
        short_description=(
            "Search Uzbekistan marketplace products by text, photo, or voice. Prices, "
            "ratings, and links in one place."
        ),
        description=(
            "Izlaber helps you find the right product without searching through multiple "
            "apps. Type a name, send a photo, or use voice - the bot shows product cards "
            "from Uzbekistan marketplaces with prices, ratings, and links. Compare "
            "options, open the right product, and complete the purchase on the seller's "
            "platform. Fast, convenient, and right in Telegram."
        ),
        command_descriptions={
            "start": "Start product search",
            "help": "How to use Izlaber",
            "lang": "Change bot language",
            "consent": "Manage data and ads consent",
        },
        start_text=(
            "Welcome to Izlaber. I help you quickly search Uzbekistan marketplace "
            "products right in Telegram. Type a product name, send a photo, or send a "
            "voice message - I will show matching options with prices, ratings, and "
            "links. Choose the best option and continue the purchase on the seller's "
            "platform."
        ),
        help_text=(
            "<b>How to use Izlaber:</b>\n\n"
            "1. Type what you are looking for: for example, “sneakers”, “vacuum cleaner”, "
            "or “iPhone case”.\n"
            "2. Or send a product photo - I will try to find similar options.\n"
            "3. Or send a voice message - I will recognize the request and start the "
            "search.\n"
            "4. Open a product card and compare the price, rating, and link.\n"
            "5. Purchase happens on the marketplace website or app.\n\n"
            "Izlaber does not sell products directly. The bot helps you find and compare "
            "options faster."
        ),
        main_buttons=("🔎 Search product", "📷 Search by photo"),
        main_placeholder="Type a product, send a photo or voice",
        more_button="Show more",
        more_placeholder="Type a product, send a photo or voice",
        messages={
            "empty_query": "Type a product name.",
            "no_session": "Send a product name first, then tap “{more}”.",
            "no_more": "No more product cards found for “{query}”.",
            "no_results": (
                "I did not find exact matches. Try a simpler query, send another photo, "
                "or specify the brand, color, size, or product category."
            ),
            "found_intro": "Found product cards for “{query}”. Showing the first {count}:",
            "sponsored_found_intro": (
                "Sponsored offer. It is shown separately from regular results:"
            ),
            "catalog_unavailable": "The catalog is unavailable right now. Try again later.",
            "rate_limited": "Too many requests. Try again in {retry_after}.",
            "ai_rate_limited": (
                "Smart search limit reached. Try again in {retry_after}."
            ),
            "search_in_progress": (
                "The previous search is still running. Wait for the result before sending "
                "a new query."
            ),
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
            "language_prompt": "Choose the language you prefer for using the bot.",
            "language_changed": "Language updated: <b>{language}</b>.",
            "search_processing": "Picking the best matches...",
            "search_more_processing": "Looking for more matches...",
            "photo_processing": "Checking the photo and finding similar products...",
            "voice_processing": "Transcribing the voice message...",
            "menu_button": "🔎 Find product",
            "search_cta_button": "🔎 Search product",
            "photo_search_prompt": (
                "Send a product photo - I will try to find similar options in marketplace cards."
            ),
            "voice_search_prompt": (
                "Send a voice message with the product name - I will recognize the request "
                "and start searching."
            ),
            "description_picture_text": (
                "Find a product by photo, voice, or name - Izlaber shows options in one place."
            ),
            "share_text": (
                "Try Izlaber - the bot searches Uzbekistan marketplaces right in Telegram. "
                "You can search by text, photo, or voice."
            ),
            "referral_invite_text": (
                "I found a convenient product search in Telegram: send a name, photo, or "
                "voice - the bot shows options with prices and links."
            ),
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
            "photo_text_fallback_intro": (
                "I did not find an exact visual match. Showing the closest {count} "
                "options by description <b>{query}</b>:"
            ),
            "photo_substitute_intro": (
                "I did not find the exact product or brand from the photo in the catalog. "
                "Showing {count} similar substitutes by type <b>{query}</b>; "
                "this is not an exact match:"
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
                "To search for products, Izlaber processes your messages, search queries, "
                "photos or voice messages, shows product cards, and may count link clicks. "
                "The bot may also show advertising offers. By tapping “I agree”, you allow "
                "this data processing and ad display. You can revoke consent with /consent."
            ),
            "consent_accept_button": "✅ I agree, start search",
            "consent_privacy_button": "Data details",
            "consent_ads_button": "Ads details",
            "consent_first_alert": "Confirm consent first.",
            "consent_accepted": "Consent saved.",
            "consent_ready": "Now send a product name, photo, or voice message.",
            "consent_revoked": (
                "Consent revoked. New search requests are unavailable until you allow "
                "data processing again. Events already processed are retained within "
                "the policy and legal requirements."
            ),
            "consent_status_active": (
                "Consent is active. To revoke it, send <code>/consent revoke</code>. "
                "After that, the bot will stop processing new search requests."
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
            "marketplace": "Marketplace",
            "currency_uzs": "UZS",
            "open_product": "Open product",
            "sponsored": "Sponsored offer",
            "footer": (
                "Price, rating, and availability may change on the marketplace side. "
                "Check details before buying."
            ),
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
    return {_normalize_more_button_text(locale.more_button) for locale in LOCALES.values()} | {
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


CONSENT_PROMPT_LANGUAGE_ORDER = ("uz", "ru", "en")
CONSENT_MULTILINGUAL_BUTTONS = {
    "consent_accept_button": "✅ Roziman / Согласен / I agree",
    "consent_privacy_button": "Ma'lumotlar / Данные / Data",
    "consent_ads_button": "Reklama / Реклама / Ads",
    "consent_first_alert": "Rozilik kerak / Нужно согласие / Consent required",
}


def format_multilingual_consent_message(key: str) -> str:
    return "\n\n".join(
        format_message(key, language_code) for language_code in CONSENT_PROMPT_LANGUAGE_ORDER
    )


def consent_multilingual_button(key: str) -> str:
    return CONSENT_MULTILINGUAL_BUTTONS[key]


def format_consent_prompt(
    language_code: str | None,
    *,
    privacy_policy_url: str = "",
    sponsored_ads_policy_url: str = "",
    multilingual: bool = False,
) -> str:
    if multilingual:
        text = format_multilingual_consent_message("consent_required")
    else:
        text = format_message("consent_required", language_code)

    policy_links = format_consent_policy_links(
        language_code,
        privacy_policy_url=privacy_policy_url,
        sponsored_ads_policy_url=sponsored_ads_policy_url,
        multilingual=multilingual,
    )
    if not policy_links:
        return text
    return f"{text}\n\n{policy_links}"


def format_consent_policy_links(
    language_code: str | None,
    *,
    privacy_policy_url: str = "",
    sponsored_ads_policy_url: str = "",
    multilingual: bool = False,
) -> str:
    links = []
    if privacy_policy_url:
        links.append(
            _format_policy_link(
                "consent_privacy_button",
                language_code,
                privacy_policy_url,
                multilingual=multilingual,
            )
        )
    if sponsored_ads_policy_url:
        links.append(
            _format_policy_link(
                "consent_ads_button",
                language_code,
                sponsored_ads_policy_url,
                multilingual=multilingual,
            )
        )
    return "\n".join(links)


def _format_policy_link(
    label_key: str,
    language_code: str | None,
    url: str,
    *,
    multilingual: bool,
) -> str:
    if multilingual:
        label = consent_multilingual_button(label_key)
    else:
        label = format_message(label_key, language_code, html=False)
    return f"{label}: {escape(url)}"


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
