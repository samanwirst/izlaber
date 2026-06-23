import {
  requestLoginCodeAction,
  resetLoginAction,
  verifyLoginCodeAction,
} from "../auth-actions";

type LoginGateProps = {
  hasChallenge: boolean;
  adminsConfigured: boolean;
  message?: string;
};

const MESSAGES: Record<string, string> = {
  "bad-code": "Код неверный или истек. Проверьте Telegram и попробуйте еще раз.",
  "code-sent": "Код отправлен администраторам в Telegram.",
  invalid: "Неверный логин или пароль, либо не настроены Telegram ID администраторов.",
  "logged-out": "Вы вышли из аналитики.",
  "session-required": "Для доступа к аналитике нужно войти.",
  "telegram-failed": "Не удалось отправить код в Telegram. Проверьте токен бота и ID админов.",
};

export function LoginGate({ hasChallenge, adminsConfigured, message }: LoginGateProps) {
  const statusText = message ? MESSAGES[message] : "";

  return (
    <main className="login-shell">
      <section className="login-panel">
        <p className="eyebrow">Restricted analytics</p>
        <h1>Izlaber Analytics</h1>
        <p className="muted">
          Доступ только для администраторов. После логина нужно ввести одноразовый
          8-символьный код из Telegram.
        </p>

        {statusText ? <p className="login-status">{statusText}</p> : null}
        {!adminsConfigured ? (
          <p className="login-status login-error">
            SITE_ADMIN_TELEGRAM_IDS не настроен, код отправить некуда.
          </p>
        ) : null}

        {hasChallenge ? (
          <div className="login-forms">
            <form action={verifyLoginCodeAction} className="login-form">
              <label>
                Telegram code
                <input
                  autoComplete="one-time-code"
                  inputMode="text"
                  maxLength={8}
                  minLength={8}
                  name="code"
                  pattern="[0-9A-Za-z]{8}"
                  placeholder="8 symbols"
                  required
                />
              </label>
              <button className="primary-button" type="submit">
                Войти
              </button>
            </form>
            <form action={resetLoginAction}>
              <button className="ghost-button" type="submit">
                Ввести логин заново
              </button>
            </form>
          </div>
        ) : (
          <form action={requestLoginCodeAction} className="login-form">
            <label>
              Login
              <input autoComplete="username" name="username" required />
            </label>
            <label>
              Password
              <input autoComplete="current-password" name="password" required type="password" />
            </label>
            <button className="primary-button" disabled={!adminsConfigured} type="submit">
              Получить Telegram-код
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
