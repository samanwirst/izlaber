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
"""


def privacy_policy(_request):
    return _html_response(
        title="Политика конфиденциальности Izlaber",
        body="""
<main>
  <h1>Политика конфиденциальности Izlaber</h1>
  <p class="updated">Last updated: 2026-06-23</p>

  <section lang="uz">
    <h2>Maxfiylik siyosati</h2>
    <p>
      Izlaber mahsulot qidiruvi, bot ishlashi, analitika va reklama takliflarini
      ko'rsatish uchun zarur bo'lgan ma'lumotlarnigina qayta ishlaydi: Telegram ID,
      profil tili, qidiruv so'rovlari, yuborilgan foto yoki ovozli xabarlar,
      kartochka ko'rishlari va havolalarga bosishlar.
    </p>
    <p>Biz quyidagi ma'lumotlarni qayta ishlashimiz mumkin:</p>
    <ul>
      <li>Telegram foydalanuvchi ID raqami va profil tili.</li>
      <li>Botga yuborilgan xabarlar, qidiruv so'rovlari, foto va ovozli xabarlar.</li>
      <li>Ko'rsatilgan mahsulot kartochkalari va ularga bosish haqidagi texnik ma'lumotlar.</li>
      <li>Servis xatolari, xavfsizlik va ishlashni tahlil qilish uchun texnik loglar.</li>
    </ul>
    <p>
      Ma'lumotlar qidiruvni bajarish, natijalarni yaxshilash, servis xavfsizligi,
      analitika va homiylik reklamasini moslashtirish uchun ishlatiladi.
      Rozilikni istalgan vaqtda botdagi <strong>/consent</strong> buyrug'i orqali
      bekor qilish mumkin.
    </p>
  </section>

  <section lang="ru">
    <h2>Политика конфиденциальности</h2>
    <p>
      Izlaber обрабатывает только данные, необходимые для поиска товаров, работы
      бота, аналитики и показа рекламных предложений: Telegram ID, язык профиля,
      поисковые запросы, отправленные фото или голосовые сообщения, показы карточек
      и переходы по ссылкам.
    </p>
    <p>Мы можем обрабатывать следующие данные:</p>
    <ul>
      <li>Telegram ID пользователя и язык профиля.</li>
      <li>Сообщения, поисковые запросы, фото и голосовые сообщения, отправленные боту.</li>
      <li>Технические данные о показах карточек товаров и кликах по ним.</li>
      <li>Технические логи для анализа ошибок, безопасности и стабильности сервиса.</li>
    </ul>
    <p>
      Данные используются для поиска товаров, улучшения результатов, безопасности
      сервиса, аналитики и подбора спонсируемой рекламы. Согласие можно отозвать
      в любой момент командой <strong>/consent</strong> в боте.
    </p>
  </section>

  <section lang="en">
    <h2>Privacy Policy</h2>
    <p>
      Izlaber processes only the data needed for product search, bot operation,
      analytics, and advertising offers: Telegram ID, profile language, search
      queries, submitted photos or voice messages, card impressions, and link clicks.
    </p>
    <p>We may process the following data:</p>
    <ul>
      <li>Telegram user ID and profile language.</li>
      <li>Messages, search queries, photos, and voice messages submitted to the bot.</li>
      <li>Technical data about product card impressions and clicks.</li>
      <li>Technical logs for error analysis, security, and service stability.</li>
    </ul>
    <p>
      Data is used to run product search, improve results, protect the service,
      perform analytics, and personalize sponsored advertising. Consent can be
      revoked anytime with the <strong>/consent</strong> command in the bot.
    </p>
  </section>
</main>
""",
    )


def sponsored_ads_policy(_request):
    return _html_response(
        title="Рекламные предложения в Izlaber",
        body="""
<main>
  <h1>Рекламные предложения в Izlaber</h1>
  <p class="updated">Last updated: 2026-06-23</p>

  <section lang="uz">
    <h2>Homiylik reklamasi</h2>
    <p>
      Izlaber'da hamkorlar yoki sotuvchilardan reklama takliflari ko'rsatilishi
      mumkin. Bunday kartochkalar odatiy natijalardan “Reklama taklifi” belgisi
      bilan ajratilishi kerak. Reklama Izlaber mahsulotni bevosita sotishini yoki
      sotuvchi shartlarini kafolatlashini anglatmaydi.
    </p>
    <p>
      Reklamani moslashtirish uchun qidiruv so'rovlari, til, kartochka ko'rishlari
      va bosishlar haqidagi texnik ma'lumotlardan foydalanishimiz mumkin. Rozilikni
      <strong>/consent</strong> orqali bekor qilish mumkin.
    </p>
  </section>

  <section lang="ru">
    <h2>Спонсируемая реклама</h2>
    <p>
      В Izlaber могут показываться рекламные предложения от партнёров или продавцов.
      Такие карточки должны быть отделены от обычной выдачи пометкой “Рекламное
      предложение”. Реклама не означает, что Izlaber продаёт товар напрямую или
      гарантирует условия продавца.
    </p>
    <p>
      Для подбора рекламы могут использоваться поисковые запросы, язык, показы
      карточек и технические данные о кликах. Согласие можно отозвать командой
      <strong>/consent</strong>.
    </p>
  </section>

  <section lang="en">
    <h2>Sponsored Advertising</h2>
    <p>
      Izlaber may show advertising offers from partners or sellers. These cards
      should be separated from regular results with the “Sponsored offer” label.
      Advertising does not mean that Izlaber sells the product directly or guarantees
      the seller's terms.
    </p>
    <p>
      To make ads relevant, we may use search queries, language, product card
      impressions, and technical click data. Consent can be revoked with the
      <strong>/consent</strong> command.
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
