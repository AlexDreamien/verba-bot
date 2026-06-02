"""Entry point: load config, start the bot, the result-collector, and the scheduler.

All three run in one asyncio process: aiogram long-polling, the aiohttp app that
receives Mini App results, and APScheduler for the daily broadcast and day close.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web
from dotenv import load_dotenv

from bot.broadcast import broadcast_daily
from bot.config import Config, load_config
from bot.daily import day_key
from bot.db import VerbaDB
from bot.handlers import setup as setup_handlers
from bot.i18n import DEFAULT_LANG, t
from bot.scheduler import VerbaScheduler
from bot.stats import compute_daily, format_daily
from bot.web import create_app

log = logging.getLogger("verba")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def _run_web(app: web.Application, host: str, port: int) -> web.AppRunner:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    log.info("Result collector listening on %s:%d", host, port)
    return runner


async def _post_summary(bot: Bot, db: VerbaDB, config: Config, day: str) -> None:
    stats = compute_daily(db.daily_rows(day))
    for admin_id in config.admin_ids:
        text = (
            t("summary_title", DEFAULT_LANG, day=day)
            + "\n\n"
            + format_daily(stats, day, DEFAULT_LANG)
        )
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            log.exception("Failed to post summary to admin %d", admin_id)
    if config.summary_to_subscribers:
        for user in db.list_subscribers():
            lang = user.lang or DEFAULT_LANG
            try:
                await bot.send_message(user.user_id, format_daily(stats, day, lang))
            except Exception:
                log.exception("Failed to post summary to %d", user.user_id)


async def main() -> None:
    configure_logging()
    load_dotenv()
    config = load_config()

    db = VerbaDB(config.db_path)
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    setup_handlers(dp, db, config)

    scheduler = VerbaScheduler(config.tz)

    async def broadcast_job() -> None:
        delivered, total = await broadcast_daily(bot, db, config)
        log.info("Scheduled broadcast: %d/%d delivered", delivered, total)

    async def close_day_job() -> None:
        day = day_key(datetime.now(UTC), config.tz)
        db.close_day(day, db.subscriber_ids())
        log.info("Closed day %s", day)
        await _post_summary(bot, db, config, day)

    if config.broadcast_cron:
        scheduler.add_broadcast(config.broadcast_cron, broadcast_job)
    scheduler.add_close_day(config.close_day_at, close_day_job)
    scheduler.start()

    runner = await _run_web(create_app(db, config), config.web_host, config.web_port)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
