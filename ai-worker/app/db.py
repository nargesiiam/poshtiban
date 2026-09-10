import contextlib

import psycopg
from psycopg.types.json import Json

from . import config


class DuplicateCommand(Exception):
    """این event_id قبلاً پردازش شده — caller نباید دوباره پردازش کند، فقط ack کند."""


def get_connection():
    return psycopg.connect(
        host=config.POSTGRES_HOST,
        dbname=config.POSTGRES_DB,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
    )


@contextlib.contextmanager
def atomic_command_processing(event_id: str):
    """
    یک تراکنش Postgres باز می‌کند و اول تلاش می‌کند در جدول
    events_processedcommand رکوردی برای event_id بسازد.

    - اگر رکورد از قبل بود (duplicate): تراکنش rollback و DuplicateCommand
      raise می‌شود. caller باید پیام را ack کند و کاری نکند — این جواب
      سؤال «اگر همان command دوبار برسد چه می‌شود؟» است.

    - اگر رکورد تازه ساخته شد: conn و cur به caller داده می‌شود تا اثر
      جانبیِ واقعیِ command (مثلاً ذخیره‌ی پاسخ عامل) را در همان تراکنش
      بنویسد. commit فقط در پایان بلوک و بدون استثنا اتفاق می‌افتد.
      اگر worker همین وسط کرش کند، تراکنش هرگز commit نمی‌شود، پس چیزی
      نصفه‌نیمه در دیتابیس نمی‌ماند؛ چون پیام هم ack نشده، RabbitMQ آن را
      به مصرف‌کننده‌ی دیگری (یا همین worker بعد از ری‌استارت) redeliver
      می‌کند — این جواب سؤال «اگر worker پیش از تأیید از کار بیفتد چه
      می‌شود؟» است: بازپردازش کامل و تمیز، نه خرابی داده.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events_processedcommand (event_id, processed_at)
                VALUES (%s, now())
                ON CONFLICT (event_id) DO NOTHING
                """,
                (event_id,),
            )
            if cur.rowcount == 0:
                conn.rollback()
                raise DuplicateCommand(event_id)
            yield conn, cur
        conn.commit()
    except DuplicateCommand:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_event(cur, envelope: dict, retry_count: int = 0):
    cur.execute(
        """
        INSERT INTO events_eventlog
            (event_id, correlation_id, event_type, kind, version, producer, payload, retry_count, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (event_id) DO NOTHING
        """,
        (
            envelope["event_id"],
            envelope["correlation_id"],
            envelope["event_type"],
            envelope["kind"],
            envelope["version"],
            envelope["producer"],
            Json(envelope["payload"]),
            retry_count,
        ),
    )
