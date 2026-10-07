# Приватный Telegram-трекер объявлений Sahibinden

Отправьте этому приватному Telegram-боту ссылку на объявление Sahibinden. Бот сохранит текущую цену и будет раз в день проверять только активные ссылки из вашего списка. Он сообщит о любом изменении цены или валюты и прекратит отслеживание объявления после семи подтверждённых проверок недоступности.

## Команды

- Отправьте ссылку на объявление — бот добавит её и пришлёт краткую сводку.
- `/list` — показать активные объявления и их идентификаторы.
- `/remove <ID-или-URL>` — прекратить отслеживание объявления.

## Развёртывание на Oracle Ubuntu 24

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin sahibinden
sudo mkdir -p /opt/sahibinden-watchlist
sudo chown sahibinden:sahibinden /opt/sahibinden-watchlist
# Скопируйте проект в /opt/sahibinden-watchlist, затем выполните:
cd /opt/sahibinden-watchlist
sudo -u sahibinden python3 -m venv .venv
sudo -u sahibinden .venv/bin/pip install -r requirements.txt
sudo apt-get install -y chromium-browser
cp .env.example .env
chmod 600 .env
```

Укажите `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` в `.env`. Управлять ботом сможет только заданный чат.

Установите unit-файлы и запустите постоянный сервис бота и ежедневную проверку:

```bash
sudo cp deploy/*.service deploy/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sahibinden-watchlist-bot.service
sudo systemctl enable --now sahibinden-watchlist-check.timer
systemctl list-timers sahibinden-watchlist-check.timer
journalctl -u sahibinden-watchlist-bot -f
```

Таймер запускается в 09:00 по времени Europe/Istanbul; systemd случайно откладывает каждый запуск на срок до одного часа. Неотправленные уведомления сохраняются в базе данных и повторно отправляются при следующей проверке. Ручной запуск проверки: `sudo systemctl start sahibinden-watchlist-check.service`.

## Локальная разработка

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python main.py bot
```

Команда `bot` запускает long polling Telegram. Команда `python main.py check` выполняет один цикл ежедневной проверки.
