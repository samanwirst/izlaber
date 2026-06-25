from __future__ import annotations

from django.http import HttpResponse

BASE_STYLE = """
body {
  color: #17211a;
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  margin: 0;
  background: #f6f3ec;
}
main {
  box-sizing: border-box;
  margin: 0 auto;
  max-width: 840px;
  padding: 42px 20px 64px;
}
h1, h2 {
  line-height: 1.2;
}
h1 {
  font-size: 34px;
  margin: 0 0 8px;
}
h2 {
  font-size: 22px;
  margin-top: 36px;
}
.updated {
  color: #657061;
  margin-bottom: 28px;
}
section {
  background: #fffdf8;
  border: 1px solid #dfd7c8;
  border-radius: 8px;
  margin-top: 18px;
  padding: 20px;
}
ul {
  padding-left: 22px;
}
.note {
  background: #eef5ee;
  border-color: #cad9ca;
}
.muted {
  color: #657061;
}
"""


def privacy_policy(_request):
    return _html_response(
        title="Политика конфиденциальности Izlaber",
        body="""
<main>
  <h1>Политика конфиденциальности Izlaber</h1>
  <p class="updated">Last updated: 2026-06-25</p>

  <section class="note" lang="ru">
    <p>
      Izlaber — агрегатор поиска товаров в Telegram. Мы не продаем товары напрямую:
      карточки и ссылки ведут на маркетплейсы, продавцов или партнерские страницы,
      у которых могут быть собственные правила, цены, доставка, возвраты и политика
      обработки данных.
    </p>
  </section>

  <section lang="uz">
    <h2>Maxfiylik siyosati</h2>
    <p>
      Izlaber Telegram orqali mahsulotlarni topishga yordam beradi. Xizmatdan
      foydalanish uchun biz faqat qidiruv, bot ishlashi, xavfsizlik, analitika va
      reklama takliflarini ko'rsatish uchun zarur bo'lgan ma'lumotlarni qayta
      ishlaymiz.
    </p>
    <p>Qayta ishlanishi mumkin bo'lgan ma'lumotlar:</p>
    <ul>
      <li>Telegram foydalanuvchi ID raqami, profil tili va tanlangan bot tili.</li>
      <li>Botga yuborilgan matnlar, qidiruv so'rovlari, foto sarlavhalari.</li>
      <li>Foto va ovozli xabarlar: mahsulotni aniqlash yoki matnga aylantirish uchun.</li>
      <li>Ko'rsatilgan mahsulot kartochkalari, reklama kartochkalari va bosishlar.</li>
      <li>Rozilik holati, rozilik versiyasi, bekor qilish yoki rad etish vaqti.</li>
      <li>Xatolar, xavfsizlik va servis barqarorligi uchun texnik loglar.</li>
    </ul>
    <p>
      Maqsadlar: qidiruvni bajarish, foto yoki ovozni tushunish, natijalarni
      tartiblash, spam va suiiste'molni cheklash, havolalar ishlashini ta'minlash,
      katalog sifati va qidiruv natijalarini yaxshilash, umumiy analitika yuritish,
      reklama takliflarini ko'rsatish va qonuniy so'rovlarni bajarish.
    </p>
    <p>
      Agar AI funksiyalari yoqilgan bo'lsa, qidiruv matni, mahsulot nomlari, foto
      yoki ovozli xabar tashqi AI provayderiga, hozirgi konfiguratsiyada OpenAI
      xizmatlariga, faqat mahsulotni tushunish, ovozni matnga aylantirish yoki
      natijalarni saralash uchun yuborilishi mumkin.
    </p>
    <p>
      Ma'lumotlar Telegram, hosting va ma'lumotlar bazasi provayderlari, AI
      provayderi, analitika paneli, reklama kampaniyalari boshqaruvchilari hamda
      qonun talab qilgan hollarda vakolatli organlar bilan zarur miqdorda
      almashilishi mumkin. Reklama beruvchilarga Telegram ID yoki shaxsiy
      yozishmalar sotilmaydi.
    </p>
    <p>
      Foto va audio fayllar qidiruvni bajarish vaqtida qayta ishlanadi; analitika
      voqealarida ularning asl baytlari saqlanmasligi kerak. Qidiruv va klik
      voqealari maqsadlar bajarilishi, xavfsizlik, servisni yaxshilash yoki qonun
      talab qilgan muddat davomida saqlanishi mumkin. Brauzer cookie orqali klik
      atributsiyasi odatda o'chirilgan; yoqilsa, u faqat mahsulot havolasi ochilganda
      ishlaydi.
    </p>
    <p>
      Foydalanuvchi o'z ma'lumotlari haqida ma'lumot so'rashi, noto'g'ri ma'lumotni
      tuzatishni, qayta ishlashni cheklashni yoki qonun doirasida yo'q qilishni
      so'rashi mumkin. Rozilikni istalgan vaqtda botdagi
      <strong>/consent revoke</strong> buyrug'i orqali bekor qilish mumkin; shundan
      keyin yangi qidiruvlar qayta ishlanmaydi, lekin avvalgi voqealar qonuniy
      asoslar mavjud bo'lsa saqlanishi mumkin.
    </p>
    <p>
      Izlaber ushbu siyosatni yangilashi mumkin. O'zgarishlar e'lon qilingandan
      keyin kelajakdagi foydalanishga tatbiq etiladi. Agar ma'lumotlar tarkibi,
      qayta ishlash maqsadi, reklama roziligi yoki qonun bo'yicha alohida rozilik
      kerak bo'lgan boshqa shartlar jiddiy o'zgarsa, yangi rozilik so'raladi.
    </p>
  </section>

  <section lang="ru">
    <h2>Политика конфиденциальности</h2>
    <p>
      Izlaber помогает искать товары через Telegram. Для работы сервиса мы
      обрабатываем только данные, которые нужны для поиска, работы бота,
      безопасности, аналитики и показа рекламных предложений.
    </p>
    <p>Мы можем обрабатывать следующие категории данных:</p>
    <ul>
      <li>Telegram ID пользователя, язык профиля и выбранный язык бота.</li>
      <li>Сообщения, поисковые запросы, подписи к фото и команды, отправленные боту.</li>
      <li>Фото и голосовые сообщения для распознавания товара или преобразования речи.</li>
      <li>Показы обычных и рекламных карточек, клики по ссылкам, тип ввода и время события.</li>
      <li>Статус согласия, версия согласия, время принятия, отказа или отзыва.</li>
      <li>Технические логи ошибок, безопасности, лимитов и стабильности сервиса.</li>
    </ul>
    <p>
      Цели обработки: выполнить поиск, понять фото или голосовой запрос,
      отсортировать результаты, ограничить спам и злоупотребления, обеспечить
      переходы по ссылкам, улучшать каталог и качество поиска, вести агрегированную
      аналитику, показывать рекламные предложения и отвечать на законные запросы.
    </p>
    <p>
      Если AI-функции включены, текст запроса, данные о кандидатах товаров, фото
      или голосовое сообщение могут передаваться внешнему AI-провайдеру, в текущей
      конфигурации OpenAI, только для понимания запроса, распознавания фото,
      транскрибации голосового сообщения или ранжирования результатов.
    </p>
    <p>
      Данные могут передаваться в необходимом объеме Telegram, поставщикам хостинга
      и баз данных, AI-провайдеру, внутренней аналитической панели, администраторам
      рекламных кампаний, а также государственным органам при наличии законного
      требования. Мы не продаем Telegram ID, личные сообщения или исходные фото и
      аудио рекламодателям.
    </p>
    <p>
      Фото и аудио обрабатываются для выполнения поиска; в аналитических событиях
      не должны сохраняться исходные байты фото или аудио. События поиска, показов
      и кликов могут храниться столько, сколько необходимо для целей сервиса,
      безопасности, улучшения качества, защиты прав или соблюдения закона.
      Cookie-атрибуция кликов по умолчанию отключена; если она включена, она
      применяется только после открытия пользователем отслеживаемой ссылки.
    </p>
    <p>
      Пользователь может запросить сведения об обработке своих данных, исправление,
      ограничение обработки или удаление данных в пределах закона. Согласие можно
      отозвать командой <strong>/consent revoke</strong> в боте. После отзыва новые
      поисковые запросы не обрабатываются, но ранее созданные события могут
      сохраняться при наличии законного основания.
    </p>
    <p>
      Izlaber может обновлять эту Политику. Изменения применяются к будущему
      использованию после публикации. Если существенно меняются состав данных, цели
      обработки, рекламное согласие или иные условия, по которым закон требует
      отдельного согласия, Izlaber запросит новое согласие.
    </p>
  </section>

  <section lang="en">
    <h2>Privacy Policy</h2>
    <p>
      Izlaber helps users search for products through Telegram. We process only the
      data needed to provide search, operate the bot, protect the service, run
      analytics, and show advertising offers.
    </p>
    <p>We may process these categories of data:</p>
    <ul>
      <li>Telegram user ID, profile language, and selected bot language.</li>
      <li>Messages, search queries, photo captions, and commands submitted to the bot.</li>
      <li>Photos and voice messages for product recognition or speech transcription.</li>
      <li>Organic and sponsored card impressions, link clicks, input type, and event time.</li>
      <li>Consent status, consent version, acceptance, decline, and revocation timestamps.</li>
      <li>Technical logs for errors, security, limits, and service stability.</li>
    </ul>
    <p>
      We use this data to run searches, understand photo or voice requests, rank
      results, limit spam and abuse, operate redirects, improve catalog/search
      quality, produce aggregate analytics, show sponsored offers, and respond to
      lawful requests.
    </p>
    <p>
      If AI features are enabled, a query, candidate product data, a photo, or a
      voice message may be sent to an external AI provider, currently OpenAI in the
      configured implementation, only to understand the request, identify a product,
      transcribe speech, or rank results.
    </p>
    <p>
      Data may be shared as needed with Telegram, hosting and database providers, an
      AI provider, the internal analytics dashboard, sponsored campaign
      administrators, and public authorities where legally required. We do not sell
      Telegram IDs, private messages, or original photo/audio files to advertisers.
    </p>
    <p>
      Photo and audio files are processed to perform search; raw photo or audio bytes
      should not be stored in analytics events. Search, impression, and click events
      may be kept as long as needed for service operation, security, quality
      improvement, legal defense, or legal compliance. Cookie-level click attribution
      is disabled by default; if enabled, it applies only after a tracked product link
      is opened.
    </p>
    <p>
      Users may request information about their data, correction, restriction of
      processing, or deletion where the law allows it. Consent can be revoked with
      <strong>/consent revoke</strong> in the bot. After revocation, new search
      requests are not processed, while previous events may be retained where a legal
      basis remains.
    </p>
    <p>
      Izlaber may update this Policy. Updates apply to future use after publication.
      If the data scope, processing purposes, advertising consent, or other terms
      materially change in a way that legally requires separate consent, Izlaber will
      request a new consent.
    </p>
  </section>
  <p class="muted">
    For privacy requests, use the Telegram bot consent command or the public contact
    channels published by Izlaber.
  </p>
</main>
""",
    )


def sponsored_ads_policy(_request):
    return _html_response(
        title="Рекламные предложения в Izlaber",
        body="""
<main>
  <h1>Рекламные предложения в Izlaber</h1>
  <p class="updated">Last updated: 2026-06-25</p>

  <section class="note" lang="ru">
    <p>
      Этот документ описывает, как Izlaber показывает рекламные карточки и рекламные
      сообщения в Telegram. Рекламные предложения не меняют того, что Izlaber остается
      агрегатором и не является продавцом товаров.
    </p>
  </section>

  <section lang="uz">
    <h2>Homiylik reklamasi</h2>
    <p>
      Izlaber botida hamkorlar, sotuvchilar yoki kampaniya egalari tomonidan
      homiylik qilingan mahsulot kartochkalari va xabarlar ko'rsatilishi mumkin.
      Bunday materiallar odatiy natijalardan <strong>“Reklama taklifi”</strong>
      belgisi bilan ajratiladi.
    </p>
    <p>
      Reklama faqat foydalanuvchi oldindan rozilik berganidan keyin ko'rsatiladi.
      Rozilikni <strong>/consent revoke</strong> orqali bekor qilish mumkin. Bekor
      qilingandan so'ng yangi qidiruvlar va reklama ko'rsatish to'xtatiladi, qonuniy
      asoslar mavjud bo'lgan avvalgi voqealar bundan mustasno.
    </p>
    <p>Reklamani tanlash va hisoblash uchun quyidagilar ishlatilishi mumkin:</p>
    <ul>
      <li>qidiruv so'rovi, tanlangan til va umumiy mahsulot toifasi;</li>
      <li>qaysi reklama kartochkasi ko'rsatilgani, kampaniya ID raqami va vaqt;</li>
      <li>reklama havolasiga bosish, limitlar va takroriy ko'rsatishlardan himoya.</li>
    </ul>
    <p>
      Reklama beruvchilarga kampaniya bo'yicha umumiy statistika berilishi mumkin:
      ko'rsatishlar, bosishlar, taxminiy CTR va kampaniya holati. Telegram ID, shaxsiy
      yozishmalar, foto yoki audio reklamachilarga sotilmaydi.
    </p>
    <p>
      Reklama Izlaber mahsulotni sotishini, narx, mavjudlik, yetkazib berish, sifat,
      kafolat yoki qaytarish shartlarini kafolatlashini anglatmaydi. Xarid, to'lov,
      yetkazib berish va qaytarish bo'yicha talablar tegishli marketplace yoki
      sotuvchiga yuboriladi.
    </p>
    <p>
      Izlaber qonun bilan taqiqlangan, foydalanuvchini chalg'itadigan yoki servis
      qoidalariga mos kelmaydigan reklamani rad etishi yoki to'xtatishi mumkin.
      Qoidalar yangilansa, ular kelajakdagi foydalanishga tatbiq etiladi; qonun
      alohida rozilik talab qilsa, yangi rozilik so'raladi.
    </p>
  </section>

  <section lang="ru">
    <h2>Спонсируемая реклама</h2>
    <p>
      В боте Izlaber могут показываться спонсируемые карточки товаров и рекламные
      сообщения от партнеров, продавцов или владельцев кампаний. Такие материалы
      отделяются от обычной выдачи пометкой
      <strong>“Рекламное предложение”</strong>.
    </p>
    <p>
      Реклама показывается только после предварительного согласия пользователя.
      Согласие можно отозвать командой <strong>/consent revoke</strong>. После
      отзыва новые поисковые запросы и рекламные показы прекращаются, кроме
      сохранения ранее созданных событий при наличии законного основания.
    </p>
    <p>Для подбора и учета рекламы могут использоваться:</p>
    <ul>
      <li>поисковый запрос, выбранный язык и общая товарная категория;</li>
      <li>факт показа рекламной карточки, ID кампании и время показа;</li>
      <li>клик по рекламной ссылке, лимиты показов и защита от повторов.</li>
    </ul>
    <p>
      Рекламодателям может предоставляться статистика кампании: показы, клики,
      примерный CTR и статус кампании. Telegram ID, личные сообщения, исходные фото
      и аудио рекламодателям не продаются.
    </p>
    <p>
      Реклама не означает, что Izlaber продает товар, гарантирует цену, наличие,
      доставку, качество, гарантию или условия возврата. Вопросы покупки, оплаты,
      доставки и возврата относятся к соответствующему маркетплейсу или продавцу.
    </p>
    <p>
      Izlaber может отклонить или остановить рекламу, если она запрещена законом,
      вводит в заблуждение, нарушает права третьих лиц или не соответствует правилам
      сервиса. Обновления этих правил применяются к будущему использованию; если
      закон требует отдельного согласия, Izlaber запросит новое согласие.
    </p>
  </section>

  <section lang="en">
    <h2>Sponsored Advertising</h2>
    <p>
      The Izlaber bot may show sponsored product cards and advertising messages from
      partners, sellers, or campaign owners. These materials are separated from
      regular results with the <strong>“Sponsored offer”</strong> label.
    </p>
    <p>
      Advertising is shown only after the user's prior consent. Consent can be
      revoked with <strong>/consent revoke</strong>. After revocation, new searches
      and advertising displays stop, except that previous events may be retained
      where a legal basis remains.
    </p>
    <p>To select and measure ads, we may use:</p>
    <ul>
      <li>the search query, selected language, and broad product category;</li>
      <li>the sponsored card impression, campaign ID, and impression time;</li>
      <li>the sponsored link click, impression caps, and duplicate-display controls.</li>
    </ul>
    <p>
      Advertisers may receive campaign statistics such as impressions, clicks,
      approximate CTR, and campaign status. Telegram IDs, private messages, original
      photos, and audio files are not sold to advertisers.
    </p>
    <p>
      Advertising does not mean that Izlaber sells the product or guarantees price,
      availability, delivery, quality, warranty, or return terms. Purchase, payment,
      delivery, and return claims belong to the relevant marketplace or seller.
    </p>
    <p>
      Izlaber may reject or stop advertising that is unlawful, misleading, infringes
      third-party rights, or does not match service rules. Updates to these rules
      apply to future use; if separate consent is legally required, Izlaber will ask
      for a new consent.
    </p>
  </section>
</main>
""",
    )


def _html_response(*, title: str, body: str) -> HttpResponse:
    response = HttpResponse(
        f"""<!doctype html>
<html lang="uz">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>{BASE_STYLE}</style>
</head>
<body>
{body}
</body>
</html>
""",
        content_type="text/html; charset=utf-8",
    )
    response["X-Robots-Tag"] = "noindex"
    return response
