"""Is the learning machinery actually working? Numbers, not impressions.

Written because the level rework changed the core three times in one day and
nothing could show the effect — every figure behind those decisions was pulled
by hand in a psql session. This reports the same figures on demand.

Five sections:
  users      — who is placed, how much they answer, whether their pool fits it
  mastery    — does anything actually reach "learned", and what blocks it
  catalogue  — coverage of the content a card needs
  guessing   — how often a quiz card can be solved without knowing the word
  trends     — what has MOVED; the others only ever show the present

Read-only. Run inside the bot container:
    docker exec -w /app englshbot-bot-1 python scripts/health_report.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.domain.enums import LearningTrack
from app.domain.pacing import pool_ceiling
from app.domain.quiz_text import strip_latin_hints
from app.infrastructure.repositories.user_words import UserWordRepository, _shape_signature
from app.services.repetition_service import LAPSE_DROP

# Share of pushed cards that repeat an active word (STREAM_WEIGHTS). Used to
# turn pool size into the interval a user actually experiences.
_REPEAT_SHARE = 0.52
GUESS_SAMPLE = 120


def _bar(value: float, width: int = 20) -> str:
    filled = max(0, min(width, round(value * width)))
    return "█" * filled + "·" * (width - filled)


async def users_section(session) -> None:
    print("\n=== ПОЛЬЗОВАТЕЛИ ===")
    rows = (
        await session.execute(
            text(
                """
                with t as (
                  select user_id,
                         percentile_cont(0.75) within group (order by c) as p75
                  from (select user_id, date_trunc('day', reviewed_at) d, count(*) c
                        from word_reviews
                        where reviewed_at >= now() - interval '60 days'
                        group by 1,2) z
                  group by 1)
                select u.id, u.level,
                       (select count(*) from user_words w
                         where w.user_id=u.id and w.status in ('learning','review')
                           and not w.archived) as active,
                       (select count(*) from user_words w
                         where w.user_id=u.id and w.status='mastered') as mastered,
                       coalesce(t.p75, 0) as p75
                from users u left join t on t.user_id=u.id
                order by u.id
                """
            )
        )
    ).all()
    print(f"{'id':>3} {'уровень':>8} {'ответов/день':>13} {'активно':>8} {'потолок':>8} "
          f"{'цикл, дн':>9} {'выучено':>8}")
    for uid, level, active, mastered, p75 in rows:
        ceiling = pool_ceiling(float(p75) if p75 else None)
        cycle = active / (_REPEAT_SHARE * float(p75)) if p75 and active else 0
        flag = "  ⚠ пул больше потолка" if active > ceiling else ""
        print(f"{uid:>3} {level or '—':>8} {float(p75):>13.1f} {active:>8} {ceiling:>8} "
              f"{cycle:>9.1f} {mastered:>8}{flag}")
    unplaced = sum(1 for r in rows if not r[1])
    if unplaced:
        print(f"\n  ⚠ без уровня (заблокированы гейтом): {unplaced} из {len(rows)}")


async def mastery_section(session) -> None:
    print("\n=== ОСВОЕНИЕ ===")
    status = (
        await session.execute(
            text("select status, count(*) from user_words group by 1 order by 2 desc")
        )
    ).all()
    total = sum(c for _, c in status) or 1
    for name, count in status:
        print(f"  {name:<10} {count:>6}  {_bar(count / total)}")

    blocked = (
        await session.execute(
            text(
                """
                select
                  count(*) filter (where production_count = 0) as no_typed,
                  count(*) filter (where production_count between 1 and 2) as few_typed,
                  count(*) filter (where production_count >= 3) as enough_typed,
                  round(avg(learning_score)::numeric, 1) as avg_score
                from user_words
                where status in ('learning','review') and not archived
                """
            )
        )
    ).one()
    no_typed, few_typed, enough_typed, avg_score = blocked
    active_total = (no_typed + few_typed + enough_typed) or 1
    print(f"\n  средний балл активного слова: {avg_score}")
    print("  напечатанных ответов (порог — минимум 3):")
    print(f"    ни одного   {no_typed:>6}  {_bar(no_typed / active_total)}")
    print(f"    1-2         {few_typed:>6}  {_bar(few_typed / active_total)}")
    print(f"    3 и больше  {enough_typed:>6}  {_bar(enough_typed / active_total)}")
    if no_typed / active_total > 0.5:
        print("    ⚠ больше половины активных слов ещё ни разу не печатали —")
        print("      либо лестница до печати не доходит, либо нет примеров")

    leeches = (
        await session.execute(
            text(
                "select count(*) from user_words "
                "where consecutive_wrong >= 3 and status in ('learning','review')"
            )
        )
    ).scalar()
    print(f"\n  слов с 3+ ошибками подряд: {leeches}  (порог отложить — 6)")
    print(f"  штраф за ошибку: -{LAPSE_DROP} к счётчику повторений")


async def catalogue_section(session) -> None:
    print("\n=== КАТАЛОГ ===")
    row = (
        await session.execute(
            text(
                """
                select count(*) total,
                       count(*) filter (where level is null) no_level,
                       count(*) filter (where translation is null) no_translation,
                       count(*) filter (where example_sentence is null or example_sentence='')
                         as no_example,
                       count(*) filter (where abstract_example_en is null) as no_hint
                from words where track='en'
                """
            )
        )
    ).one()
    total, no_level, no_translation, no_example, no_hint = row
    print(f"  всего слов: {total}")
    for label, missing in (
        ("без уровня", no_level),
        ("без перевода", no_translation),
        ("без примера (не дойдут до печати!)", no_example),
        ("без контекстной подсказки", no_hint),
    ):
        share = missing / (total or 1)
        mark = " ⚠" if share > 0.1 else ""
        print(f"    {label:<38} {missing:>5}  {_bar(share)}{mark}")


async def guessing_section(session) -> None:
    """How many quiz cards give the answer away by shape alone.

    A card is counted as guessable when the correct option is the ONLY one
    carrying a visible feature — the only multi-word option, the only one with a
    slash, the only infinitive. Someone who knows no English picks it by
    elimination, and the card then teaches nothing while still counting as a
    correct answer.
    """
    print("\n=== УГАДЫВАЕМОСТЬ КАРТОЧЕК ===")
    repo = UserWordRepository(session)
    rows = (
        await session.execute(
            text(
                """
                select uw.id, uw.user_id, w.translation, w.part_of_speech, w.level
                from user_words uw join words w on w.id = uw.word_id
                where w.translation is not null and uw.track='en'
                order by random() limit :n
                """
            ),
            {"n": GUESS_SAMPLE},
        )
    ).all()

    checked = guessable = 0
    examples: list[str] = []
    for uw_id, user_id, translation, pos, level in rows:
        correct = strip_latin_hints(translation)
        if not correct:
            continue
        distractors = await repo.quiz_distractors(
            user_id,
            track=LearningTrack.ENGLISH,
            exclude_user_word_id=uw_id,
            limit=3,
            exclude_translations=[translation],
            correct_pos=pos,
            correct_level=level,
        )
        if len(distractors) < 3:
            continue
        checked += 1
        options = [correct, *distractors[:3]]
        signatures = [_shape_signature(o) for o in options]
        # A feature the correct option has and no distractor shares.
        giveaway = any(
            signatures[0][i] and not any(s[i] for s in signatures[1:])
            for i in range(len(signatures[0]))
        )
        if giveaway:
            guessable += 1
            if len(examples) < 5:
                examples.append(f"    «{correct}»  против  {', '.join(distractors[:3])}")

    if not checked:
        print("  недостаточно данных")
        return
    share = guessable / checked
    print(f"  проверено карточек: {checked}")
    print(f"  решаемы по форме, без знания слова: {guessable} ({share:.0%})  {_bar(share)}")
    if examples:
        print("\n  примеры:")
        for line in examples:
            print(line)
    if share > 0.15:
        print("\n  ⚠ каждая шестая карточка и чаще — верный вариант выделяется")
        print("    внешне. Это завышает 'выучено' на ровном месте.")


async def trends_section(session) -> None:
    """What has moved, as opposed to where things stand.

    The other sections read the tables, which only ever show the present. These
    read the event log, which is the only way to answer the question that kept
    coming up during the rework and couldn't be: did it help?
    """
    print("\n=== ДВИЖЕНИЕ ЗА 14 ДНЕЙ ===")

    answers = (
        await session.execute(
            text(
                """
                select props->>'kind' as kind, count(*)
                from analytics_events
                where name = 'answer_graded'
                  and created_at >= now() - interval '14 days'
                group by 1 order by 2 desc
                """
            )
        )
    ).all()
    if not answers:
        print("  событий пока нет — они пишутся только с этого деплоя")
        return

    total = sum(c for _, c in answers) or 1
    print("  чем отвечают:")
    for kind, count in answers:
        print(f"    {kind or '—':<16} {count:>5}  {_bar(count / total)}")
    typed = sum(c for k, c in answers if (k or "").startswith("typed_"))
    print(f"\n  доля ответов печатью: {typed / total:.0%}")
    if typed / total < 0.2:
        print("    ⚠ почти всё — выбор из вариантов; до печати доходит мало слов")

    mastered = (
        await session.execute(
            text(
                """
                select date_trunc('day', created_at)::date, count(*)
                from analytics_events
                where name = 'word_mastered'
                  and created_at >= now() - interval '14 days'
                group by 1 order by 1
                """
            )
        )
    ).all()
    print(f"\n  выучено слов за 14 дней: {sum(c for _, c in mastered)}")
    for day, count in mastered[-7:]:
        print(f"    {day}  {count:>3}  {'▪' * min(count, 30)}")

    placements = (
        await session.execute(
            text(
                """
                select props->>'level' as level, props->>'origin' as origin, count(*)
                from analytics_events
                where name = 'placement_completed'
                group by 1, 2 order by 3 desc
                """
            )
        )
    ).all()
    print(f"\n  тестов пройдено: {sum(c for _, _, c in placements)}")
    for level, origin, count in placements:
        print(f"    {level or '—':<4} {origin or '—':<10} {count}")

    changes = (
        await session.execute(
            text(
                "select props->>'old', props->>'new', count(*) from analytics_events "
                "where name = 'level_changed' group by 1, 2 order by 3 desc limit 8"
            )
        )
    ).all()
    if changes:
        print("\n  уровень пересчитан:")
        for old, new, count in changes:
            print(f"    {old or '—'} → {new or '—'}   {count}")


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            await users_section(session)
            await mastery_section(session)
            await catalogue_section(session)
            await guessing_section(session)
            await trends_section(session)
    finally:
        await engine.dispose()
    print()


if __name__ == "__main__":
    asyncio.run(main())
