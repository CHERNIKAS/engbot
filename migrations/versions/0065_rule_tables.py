"""Give the remaining twenty-nine topics the same grid Present Simple got.

0064 rewrote one rule as a table and called it the pattern; this is the rest of
the syllabus brought to it. Every topic now reads the same way: what the form
means in one line, the grid in a monospace block, and the one mistake a Russian
speaker actually makes underneath.

The grids are laid out vertically because a phone wraps anything wider than
about thirty monospace characters, and a wrapped table is worse than none. The
warning line is not decoration — it is the cell people stand in wrongly: the -s
that moves to `does`, the `did` that takes the past tense back off the verb,
the `if` that never takes a future.

`downgrade` restores each previous text verbatim, so the prose versions are not
lost by being replaced.

Revision ID: 0065
Revises: 0064
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None

NEW_RULES: dict[str, str] = {
    "verb_to_be": """🔹 <b>to be</b> — быть, являться, находиться.

<pre>I        am    I am ready
he/she/it is    He is ready
you/we/they are You are ready

 −   I am not / He isn't
 ?   Are you ready?</pre>

⚠️ У <b>to be</b> нет do/does: отрицание и вопрос делает он сам.""",
    "do_does_questions": """❓ Обычный глагол спрашивает и отрицает через <b>do</b> / <b>does</b>.

<pre>I/you/we/they → do
he/she/it     → does

 −   I don't know
     He doesn't know
 ?   Do you know?
     Does he know?</pre>

⚠️ После <b>does</b> глагол без <b>-s</b>: does he know, не «knows».""",
    "tense_present_continuous": """🔵 <b>Present Continuous</b> — прямо сейчас, в этот момент.

<pre>be + V-ing

 +   I am working
     He is working
     We are working
 −   He isn't working
 ?   Are you working?</pre>

⚠️ Нужен <b>be</b>: «He working» — не предложение.""",
    "tense_past_simple": """🟠 <b>Past Simple</b> — законченное в прошлом.

<pre> +   I worked
     He went        (2-я форма)
 −   I didn't work
 ?   Did you work?</pre>

⚠️ После <b>did</b> глагол в первой форме: did you go, не «did you went».""",
    "irregular_past": """🔁 <b>Неправильные глаголы: 2-я форма</b>

<pre>go    → went
see   → saw
take  → took
make  → made
have  → had</pre>

⚠️ Вторая форма живёт только в утверждении. С <b>did</b> — первая: did he go.""",
    "was_were": """🟤 <b>was / were</b> — прошедшее от <b>to be</b>.

<pre>I/he/she/it   was
you/we/they   were

 −   I wasn't / They weren't
 ?   Were you there?</pre>

⚠️ Здесь тоже без <b>did</b>: «Did you were» — ошибка.""",
    "questions_word_order": """❔ <b>Вопросы в прошлом: did</b>

<pre> ?   Did you see it?
 ?   Where did he go?
 ?   Why didn't she call?

порядок:
(Wh) + did + кто + глагол</pre>

⚠️ <b>did</b> забирает прошедшее себе — глагол остаётся в первой форме.""",
    "plurals_basic": """🔢 <b>Множественное число</b>

<pre>обычно      + s    cats
s/x/ch/sh   + es   boxes
согласная+y → ies  cities

особые:
child → children
foot  → feet
man   → men</pre>

⚠️ После числа существительное во множественном: five books.""",
    "quantifiers_basic": """⚖️ <b>much / many / some / any</b>

<pre>считаем    many books
не считаем much time

 +   some water
 −?  any water</pre>

⚠️ <b>some</b> в утверждении, <b>any</b> в вопросе и отрицании.""",
    "articles_basic": """📘 <b>Артикли a / an / the</b>

<pre>a / an   один из многих,
         впервые
the      тот самый,
         уже известный

a cat → the cat is black</pre>

⚠️ <b>an</b> перед гласным звуком: an apple, an hour.""",
    "prepositions_basic": """📍 <b>Предлоги места и времени</b>

<pre>in   месяц, год, город
     in May, in Paris
on   день, дата, поверхность
     on Monday, on the table
at   время, точка
     at 5, at home</pre>

⚠️ Правило сужения: in → on → at, от большого к точному.""",
    "comparatives": """📊 <b>Степени сравнения</b>

<pre>короткие  + er / + est
  old → older → the oldest
длинные   more / the most
  more useful
  the most useful

good → better → the best
bad  → worse  → the worst</pre>

⚠️ Либо <b>-er</b>, либо <b>more</b> — вместе не бывает.""",
    "tense_future_will": """🔮 <b>Future (will)</b> — решение и предсказание.

<pre> +   I will call
 −   I won't call
 ?   Will you call?</pre>

⚠️ <b>will</b> одинаков для всех лиц, и после него глагол без <b>to</b>.""",
    "future_going_to": """🎯 <b>to be going to</b> — намерение, план.

<pre>be going to + глагол

 +   I am going to work
 −   He isn't going to work
 ?   Are you going to work?</pre>

⚠️ <b>will</b> — решил сейчас, <b>going to</b> — решил заранее.""",
    "modals_basic": """🔑 <b>can / must / should / have to</b>

<pre>can      могу, умею
must     обязан (сам)
should   стоит, советую
have to  обязан (обстоятельства)

 −   can't / shouldn't
 ?   Can you help?</pre>

⚠️ После модального — голый глагол: can swim, не «can to swim».""",
    "past_continuous": """🟣 <b>Past Continuous</b> — длилось в момент в прошлом.

<pre>was/were + V-ing

 +   I was working
     They were working
 −   He wasn't working
 ?   Were you working?</pre>

⚠️ Фон и событие: I was working when he called.""",
    "irregular_participle": """🔁 <b>Неправильные глаголы: 3-я форма</b>

<pre>go    went   gone
see   saw     seen
take  took    taken
do    did     done
be    was     been</pre>

⚠️ Третья форма сама по себе не время — ей нужен <b>have</b> или <b>be</b>.""",
    "present_perfect": """🟩 <b>Present Perfect</b> — прошлое, важное сейчас.

<pre>have/has + 3-я форма

 +   I have seen it
     He has seen it
 −   I haven't seen it
 ?   Have you seen it?</pre>

⚠️ Без точного времени. Есть «yesterday» — нужен Past Simple.""",
    "past_perfect": """🟦 <b>Past Perfect</b> — раньше другого прошлого.

<pre>had + 3-я форма

 +   I had left
 −   I hadn't left
 ?   Had you left?</pre>

⚠️ Нужен второй момент: I had left before he came.""",
    "present_perfect_continuous": """🟨 <b>Present Perfect Continuous</b> — длится до сих пор.

<pre>have/has been + V-ing

 +   I have been working
     He has been working
 ?   How long have you
     been working?</pre>

⚠️ Отвечает на «как долго», а не «сколько раз».""",
    "used_to": """🕰 <b>used to</b> — раньше было, сейчас нет.

<pre> +   I used to smoke
 −   I didn't use to smoke
 ?   Did you use to smoke?</pre>

⚠️ После <b>did</b> — <b>use</b> без <b>-d</b>.""",
    "gerund_infinitive": """🔀 <b>Gerund или Infinitive</b>

<pre>-ing после:
  enjoy, finish, mind,
  keep, avoid

to + глагол после:
  want, decide, hope,
  promise, need</pre>

⚠️ <b>stop smoking</b> — бросил курить; <b>stop to smoke</b> — остановился покурить.""",
    "conditionals_01": """0️⃣1️⃣ <b>Условные: 0 и 1 тип</b>

<pre>0 — всегда так:
  If you heat ice,
  it melts

1 — реально в будущем:
  If it rains,
  I will stay home</pre>

⚠️ После <b>if</b> будущего нет: if it rains, не «if it will rain».""",
    "conditional_second": """2️⃣ <b>Условные: 2 тип</b> — маловероятное, воображаемое.

<pre>If + Past, would + глагол

  If I had money,
  I would travel

  If I were you,
  I would go</pre>

⚠️ <b>were</b> для всех лиц: if I were, if he were.""",
    "conditional_third": """3️⃣ <b>Условные: 3 тип</b> — упущенное в прошлом.

<pre>If + had + 3-я форма,
would have + 3-я форма

  If I had known,
  I would have come</pre>

⚠️ Сожаление: это уже не изменить.""",
    "passive_simple": """🔄 <b>Пассив: Present и Past Simple</b>

<pre>be + 3-я форма

now:   The book is written
       Books are written
past:  The book was written
       Books were written
 ?     Was it written?</pre>

⚠️ Важно действие, а не исполнитель. Кто — через <b>by</b>.""",
    "reported_speech": """💬 <b>Косвенная речь</b> — время уходит на шаг назад.

<pre>«I work»  → he said he worked
«I am»    → he said he was
«I will»  → he said he would
«I can»   → he said he could

today → that day
tomorrow → the next day</pre>

⚠️ В косвенном вопросе прямой порядок: he asked where I lived.""",
    "relative_clauses": """🔗 <b>who / which / that / where</b>

<pre>who    о людях
which  о вещах
that   и о тех, и о тех
where  о месте

the man who called
the book which helped
the city where I live</pre>

⚠️ Одно подлежащее: the man who called, не «who he called».""",
    "tag_questions": """🏷 <b>Разделительные вопросы</b>

<pre>утверждение → хвост «−»
  You are ready, aren't you?
отрицание  → хвост «+»
  You aren't ready, are you?

I work, don't I?
He went, didn't he?</pre>

⚠️ Хвост берёт тот же вспомогательный и противоположный знак.""",
}

OLD_RULES: dict[str, str] = {
    "verb_to_be": """🔹 <b>am</b> — только с I. <b>is</b> — он, она, оно. <b>are</b> — you, we, they.
Отрицание: <b>I'm not</b>, <b>he isn't</b>, <b>they aren't</b>.
Вопрос — глагол вперёд: <b>Are you ready?</b> <b>Is she at home?</b>
У to be нет do/does: «Do you are» — не бывает.""",
    "do_does_questions": """❓ Обычный глагол спрашивает и отрицает через <b>do</b> / <b>does</b>.
<b>do</b> — I, you, we, they. <b>does</b> — he, she, it.
Do you work? · Does he work? · I don't work · She doesn't work.
Главное: после do/does глагол <b>без -s</b> — «Does she works» неверно.""",
    "tense_present_continuous": """🔵 <b>Present Continuous</b> — происходит прямо сейчас. <b>be + V-ing</b>:
• I → <b>am</b> (I am reading)
• he / she / it → <b>is</b> (she is cooking)
• you / we / they → <b>are</b> (they are playing)""",
    "tense_past_simple": """🟠 <b>Past Simple</b> — завершённые действия в прошлом.
• Правильные глаголы: <b>+ed</b> (play → played).
• Неправильные — особые формы (go → went, write → wrote).
• <b>to be</b>: I/he/she/it → <b>was</b>, you/we/they → <b>were</b>.""",
    "irregular_past": """🔁 <b>Неправильные глаголы: вторая форма</b>
Большинство глаголов образуют прошедшее через <b>-ed</b>: work → worked.
Но самые частые глаголы — исключения, и их формы нужно просто помнить:
go → <b>went</b>, see → <b>saw</b>, buy → <b>bought</b>, take → <b>took</b>.
Их около двухсот, но в обычной речи работают примерно пятьдесят.""",
    "was_were": """⏪ Прошедшее от to be: <b>was</b> — I, he, she, it. <b>were</b> — you, we, they.
Отрицание: <b>wasn't</b> / <b>weren't</b>. Вопрос — глагол вперёд: <b>Were you there?</b>
Это не то же, что <b>didn't</b>: didn't — для обычных глаголов (I didn't go), wasn't — для состояния (I wasn't ready).""",
    "questions_word_order": """⏪ Вопрос о прошлом — <b>did</b> перед подлежащим: <b>Did you go?</b> <b>Where did she work?</b>
Отрицание: <b>didn't</b>. Глагол после did/didn't — <b>в первой форме</b>: «Did you went» неверно, правильно <b>Did you go</b>.
did не используется с to be: не «Did you were», а <b>Were you</b>.""",
    "plurals_basic": """🔢 <b>Множественное число</b>: обычно <b>+s</b> (cat→cats); после s/x/ch/sh <b>+es</b> (box→boxes); y→ies (city→cities). Особые: man→men, child→children, foot→feet, tooth→teeth.""",
    "quantifiers_basic": """🥤 <b>many</b> — со счётными (many books), <b>much</b> — с несчётными (much water). <b>some</b> — в утверждениях, <b>any</b> — в вопросах и отрицаниях.""",
    "articles_basic": """🔤 <b>Артикли</b>:
<b>a/an</b> — неопределённый, один из многих (a cat, an apple; an — перед гласным звуком).
<b>the</b> — определённый, конкретный/известный (the sun, the book on the table).
<b>—</b> (без артикля) — с множественным и неисчисляемым в общем смысле (I love music).""",
    "prepositions_basic": """📍 <b>Предлоги места и времени</b>:
<b>at</b> — точка/точное время (at the bus stop, at 7 o'clock).
<b>in</b> — внутри, месяцы/годы (in the box, in May, in 1990).
<b>on</b> — на поверхности, дни (on the table, on Monday).
<b>to</b> — направление (go to school).""",
    "comparatives": """📊 <b>Сравнение</b>: короткие слова <b>+er / the …est</b> (big→bigger→the biggest); длинные — <b>more / the most</b> (more interesting). Особые: good→better→best, bad→worse→worst.""",
    "tense_future_will": """🟣 <b>Future с will</b> — решения, прогнозы и обещания.
Формула: <b>will + базовая форма</b> глагола.
I think it <b>will rain</b>.""",
    "future_going_to": """🗓 <b>to be going to</b> — планы и очевидное будущее. <b>be going to + глагол</b>:
• I → <b>am going to</b>
• he / she / it → <b>is going to</b>
• you / we / they → <b>are going to</b>
Пример: I'm going to travel.""",
    "modals_basic": """🛠 <b>can</b> — умение/возможность, <b>must</b> — обязанность, <b>should</b> — совет, <b>have to</b> — необходимость. После модального — базовая форма (can swim).""",
    "past_continuous": """⏳ <b>Past Continuous</b> — действие шло в момент в прошлом. <b>was/were + V-ing</b>:
• I / he / she / it → <b>was</b> (I was reading)
• you / we / they → <b>were</b> (they were playing)""",
    "irregular_participle": """🔁 <b>Неправильные глаголы: третья форма</b>
Третья форма нужна для Present Perfect и пассива: I have <b>seen</b> it.
У многих глаголов она совпадает со второй: buy → bought → <b>bought</b>.
Но у самых частых — отличается:
go → went → <b>gone</b>, see → saw → <b>seen</b>, give → gave → <b>given</b>.""",
    "present_perfect": """✅ <b>Present Perfect</b> — действие связано с настоящим (опыт, результат, «уже/ещё»). <b>have/has + 3-я форма</b>:
• he / she / it → <b>has</b> (she has finished)
• I / you / we / they → <b>have</b> (I have seen it)""",
    "past_perfect": """⏮ <b>Past Perfect</b> — действие случилось <b>раньше</b> другого момента в прошлом. Для всех лиц одинаково: <b>had + 3-я форма</b>.
• When I arrived, the film <b>had started</b> (началось до моего прихода).
• She was tired because she <b>had worked</b> all night.
Часто с before, after, by the time, already.""",
    "present_perfect_continuous": """🔄 <b>Present Perfect Continuous</b> — началось в прошлом и <b>до сих пор длится</b> (или только что закончилось). <b>have/has been + V-ing</b>:
• I / you / we / they → <b>have been</b>: I <b>have been waiting</b> for an hour.
• he / she / it → <b>has been</b>: She <b>has been working</b> since morning.
Часто с for (как долго) и since (с какого момента).""",
    "used_to": """🕰 <b>used to</b> — то, что было регулярно или долго в прошлом, но не сейчас. <b>used to + базовая форма</b> (I used to smoke). В вопросах/отрицаниях — <b>did/didn't + use to</b>.""",
    "gerund_infinitive": """🔁 После одних глаголов идёт <b>-ing</b> (enjoy, finish, avoid: I enjoy reading), после других — <b>to + глагол</b> (want, decide, hope: I want to go). После предлогов — всегда <b>-ing</b>.""",
    "conditionals_01": """🔀 <b>0-й тип</b> (факты): If + Present, Present (If you heat ice, it melts).
<b>1-й тип</b> (реальное будущее): If + Present, <b>will</b> (If it rains, we will stay).""",
    "conditional_second": """🌈 <b>Условные 2-го типа</b> — нереальная или маловероятная ситуация <b>сейчас/в будущем</b>.
Формула: If + <b>Past Simple</b>, <b>would</b> + глагол.
• If I <b>had</b> a million, I <b>would buy</b> a house.
• С to be — <b>were</b> для всех лиц: If I <b>were</b> you, I would wait.""",
    "conditional_third": """⏪ <b>Условные 3-го типа</b> — нереальное <b>прошлое</b>: уже случилось, не изменить (сожаления, упущенные шансы).
Формула: If + <b>had + V3</b>, <b>would have + V3</b>.
• If you <b>had told</b> me, I <b>would have helped</b>.
• She <b>wouldn't have been</b> late if she <b>had taken</b> a taxi.""",
    "passive_simple": """🏭 <b>Passive</b> — важно само действие, а не кто его совершил. <b>be + 3-я форма</b>:
• Present: ед. ч. → <b>is</b>, мн. ч. → <b>are</b>: English <b>is spoken</b> here. Cars <b>are made</b> in Japan.
• Past: ед. ч. → <b>was</b>, мн. ч. → <b>were</b>: The house <b>was built</b> in 1990.""",
    "reported_speech": """🗣 <b>Косвенная речь</b> — пересказываем чужие слова: He said (that)… Время сдвигается на шаг назад:
• Present → Past: «I work» → He said he <b>worked</b>.
• will → <b>would</b>: «I'll call» → She said she <b>would call</b>.
• can → <b>could</b>, have done → <b>had done</b>.
Важно: say без лица, tell + кому (He told <b>me</b>…).""",
    "relative_clauses": """🔗 <b>Относительные местоимения</b> соединяют части предложения:
• <b>who</b> — люди: the man <b>who</b> called
• <b>which</b> — вещи и животные: the book <b>which</b> I read
• <b>that</b> — универсальное; обычно после everything и превосходной степени: the best film <b>that</b> I've seen
• <b>where</b> — места: the café <b>where</b> we met""",
    "tag_questions": """🏷 <b>Разделительный вопрос</b> — «хвостик» для переспроса. Полярность меняется на противоположную:
• Утверждение → отрицательный хвост: You like tea, <b>don't you?</b>
• Отрицание → положительный: She isn't here, <b>is she?</b>
Хвост повторяет вспомогательный глагол: He can swim, <b>can't he?</b> They went, <b>didn't they?</b>""",
}


def _apply(rules: dict[str, str]) -> None:
    bind = op.get_bind()
    for slug, rule in rules.items():
        bind.execute(
            sa.text("UPDATE grammar_topics SET rule = :rule WHERE slug = :slug"),
            {"rule": rule, "slug": slug},
        )


def upgrade() -> None:
    _apply(NEW_RULES)


def downgrade() -> None:
    _apply(OLD_RULES)
