"""What each grammar topic's construction phrases must drill.

Kept in the repository rather than in shell history because the spec is the
part that decides whether a set teaches anything. The Present Simple run —
the one that produced the hundred phrases now in production — showed what a
spec has to carry:

  1. the forms spelled out with examples, or the set collapses into statements
     alone, and the statement is the half a Russian speaker already guesses;
  2. a quota on the hard form («at least a third in the third person»), because
     the error people actually make is the one worth drilling;
  3. a list of verbs, or the model wanders into rare vocabulary.

Usage:
    python scripts/gen_constructor.py --topic <slug> --count 100 --batch 12 \\
        --out /tmp/<slug>.json --spec "$(python -c 'import scripts.constructor_specs as s; print(s.SPECS["<slug>"])')"

or drive the whole list with scripts/run_constructor.py.
"""

from __future__ import annotations

_VERBS = (
    "Глаголы простые и частотные: work, live, go, like, know, want, see, read, "
    "speak, play, eat, drink, study, help, need, start, finish, buy, come, make."
)

# Topics whose sentences cannot fit the default nine-word ceiling. The third
# conditional spends ten words before it says anything: «If she had studied,
# she would have passed the exam». Generated at nine, it produced six usable
# phrases out of a hundred and rejected 186 — the ceiling was rejecting the
# grammar, not bad output.
MAX_WORDS: dict[str, int] = {
    "conditional_third": 13,
}

SPECS: dict[str, str] = {
    "verb_to_be": (
        "Глагол to be в настоящем. Равномерно покрой три формы: утверждение "
        "(I am tired / He is at home / They are ready), отрицание (I'm not tired / "
        "She isn't here / We aren't late), вопрос (Are you ready? / Is he at home?). "
        "Не меньше трети заданий — где решает выбор между am, is и are по подлежащему. "
        "Обязательно включи все три лица: I, he/she/it, you/we/they. "
        "Никаких do/does — у to be их не бывает. "
        "Лексика: ready, tired, late, hungry, happy, busy, at home, at work, at school, "
        "here, there, teacher, student, doctor, cold, warm, new, old."
    ),
    "do_does_questions": (
        "Отрицания и вопросы с do/does в Present Simple. Равномерно покрой четыре формы: "
        "вопрос с do (Do you work?), вопрос с does (Does she work?), отрицание с don't "
        "(I don't work), отрицание с doesn't (She doesn't work). "
        "Не меньше половины заданий — третье лицо единственного числа, где решает "
        "выбор does/doesn't. Главная ошибка, которую надо гонять: после do/does/don't/doesn't "
        "глагол стоит БЕЗ -s (Does she work, не Does she works). "
        "Включи вопросы с вопросительным словом: What do you want? Where does he live? "
        + _VERBS
    ),
    "tense_present_continuous": (
        "Present Continuous. Равномерно покрой три формы: утверждение (I am working / "
        "She is reading), отрицание (I'm not working / He isn't sleeping), вопрос "
        "(Are you working? / Is she reading?). Не меньше трети — третье лицо, где решает is. "
        "Обязательно включи 8-10 заданий на контраст с Present Simple: русское «сейчас», "
        "«в данный момент», «смотри» требует Continuous. "
        "Глаголы, которые бывают в Continuous: work, read, sleep, eat, drink, play, watch, "
        "write, wait, cook, run, listen, talk, study."
    ),
    "tense_past_simple": (
        "Past Simple с ПРАВИЛЬНЫМИ глаголами. Равномерно покрой три формы: утверждение "
        "(I worked / She played), отрицание (I didn't work / He didn't call), вопрос "
        "(Did you work? / Did she call?). Не меньше трети — отрицания и вопросы, где "
        "главная ошибка: после didn't глагол в первой форме (I didn't work, не I didn't worked). "
        "Добавляй маркеры прошлого: yesterday, last week, two days ago, in 2020. "
        "Глаголы правильные: work, play, watch, call, open, close, help, want, live, study, "
        "cook, clean, wait, ask, answer, start, finish."
    ),
    "irregular_past": (
        "Вторая форма неправильных глаголов в Past Simple. Равномерно покрой три формы: "
        "утверждение со второй формой (I went / She bought), отрицание, где глагол "
        "возвращается в первую (I didn't go, НЕ I didn't went), вопрос (Did you go?). "
        "Не меньше трети заданий — отрицание или вопрос, потому что там и происходит ошибка. "
        "Глаголы: go/went, see/saw, buy/bought, take/took, give/gave, come/came, make/made, "
        "eat/ate, drink/drank, write/wrote, read/read, know/knew, say/said, tell/told, "
        "find/found, get/got, think/thought, speak/spoke."
    ),
    "was_were": (
        "was / were. Равномерно покрой три формы: утверждение (I was tired / They were late), "
        "отрицание (I wasn't ready / We weren't at home), вопрос (Were you there? / Was she happy?). "
        "Не меньше половины заданий — где решает выбор was или were по подлежащему. "
        "Обязательно включи 8-10 заданий на контраст с didn't: состояние — wasn't "
        "(I wasn't ready), действие — didn't (I didn't go). "
        "Лексика: ready, tired, late, at home, at work, happy, busy, cold, hot, open, closed, "
        "yesterday, last night, this morning."
    ),
    "questions_word_order": (
        "Вопросы и отрицания в прошедшем через did. Равномерно покрой три формы: общий вопрос "
        "(Did you go?), вопрос с вопросительным словом (Where did she go? What did he say?), "
        "отрицание (I didn't go / She didn't call). "
        "ЖЕЛЕЗНОЕ требование: после did и didn't глагол в первой форме — Did you go, не Did you went. "
        "Не меньше трети заданий — с неправильными глаголами, где соблазн поставить вторую "
        "форму сильнее всего: go, see, buy, take, eat, write, know, say, come, give. "
        "Включи 6-8 заданий, где нужно Were you / Was she, а не Did — did с to be не работает."
    ),
    "plurals_basic": (
        "Множественное число существительных. Равномерно покрой: обычное -s (books, cars), "
        "окончания -es (boxes, watches, dishes), смену y→ies (cities, countries), "
        "и неправильные (children, people, men, women, feet, teeth). "
        "Не меньше трети заданий — неправильные формы и -ies, где и ошибаются. "
        "Обязательно согласуй с глаголом: There are five children / These books are new. "
        "Существительные: book, car, city, country, box, watch, dish, child, man, woman, "
        "person, foot, tooth, friend, house, apple, week, day."
    ),
    "quantifiers_basic": (
        "much / many / some / any. Равномерно покрой четыре слова: many с исчисляемыми "
        "(many books), much с неисчисляемыми (much water, чаще в вопросе и отрицании), "
        "some в утверждении (I have some money), any в вопросе и отрицании "
        "(Do you have any money? / I don't have any). "
        "Не меньше трети заданий — выбор some или any, где решает тип предложения. "
        "Исчисляемые: books, friends, apples, people, days. "
        "Неисчисляемые: water, money, time, milk, bread, work, coffee, sugar."
    ),
    "articles_basic": (
        "Артикли a / an / the и их отсутствие. Равномерно покрой: a перед согласным "
        "(a book), an перед гласным (an apple, an hour), the при повторном или "
        "единственном в своём роде (the sun, the book I bought), и отсутствие артикля "
        "с множественным и неисчисляемым (I like music, Cats are nice). "
        "Не меньше трети заданий — контраст a и the во втором упоминании: "
        "«Я купил книгу. Книга интересная» → I bought a book. The book is interesting. "
        "Лексика: book, apple, hour, car, house, dog, cat, sun, moon, school, water, music, film."
    ),
    "prepositions_basic": (
        "Предлоги времени и места. Равномерно покрой: in (in the room, in May, in 2020), "
        "on (on the table, on Monday), at (at home, at 5 o'clock, at school), "
        "плюс to / from для направления. "
        "Не меньше трети заданий — предлоги времени, где русский даёт один предлог, "
        "а английский три разных: в мае — in May, в понедельник — on Monday, в пять — at five. "
        "Лексика: room, table, home, school, work, box, bus, car, Monday, May, morning, "
        "night, weekend, five o'clock."
    ),
    "comparatives": (
        "Степени сравнения прилагательных. Равномерно покрой: короткие с -er/-est "
        "(bigger, the biggest), длинные с more/most (more interesting, the most beautiful), "
        "и неправильные (good/better/the best, bad/worse/the worst). "
        "Не меньше трети заданий — сравнительная степень с than (He is taller than me). "
        "Обязательно включи 6-8 заданий на неправильные формы — better и worse ошибаются чаще всего. "
        "Прилагательные: big, small, old, new, tall, fast, cheap, good, bad, interesting, "
        "beautiful, expensive, difficult, happy."
    ),
    "tense_future_will": (
        "Future Simple с will. Равномерно покрой три формы: утверждение (I will call you / "
        "She'll come), отрицание (I won't go / He won't help), вопрос (Will you come? / "
        "Will she call?). Не меньше трети — отрицания с won't. "
        "ЖЕЛЕЗНОЕ: после will глагол всегда в первой форме, без to и без -s — "
        "She will come, не She will comes. "
        "Включи 6-8 заданий на решение, принятое сейчас, и обещание — это то, где will уместен. "
        + _VERBS
    ),
    "future_going_to": (
        "Конструкция to be going to. Равномерно покрой три формы: утверждение "
        "(I am going to buy a car / She is going to study), отрицание (I'm not going to go), "
        "вопрос (Are you going to work?). Не меньше трети — третье лицо, где решает is. "
        "Обязательно включи 8-10 заданий на контраст с will: план, решённый заранее, — "
        "going to; решение в момент речи — will. "
        "Глаголы: buy, study, travel, move, start, call, visit, help, cook, watch, rain."
    ),
    "modals_basic": (
        "Модальные глаголы can, must, should, have to. Равномерно покрой: can/can't "
        "(умение и разрешение), must/mustn't (обязанность и запрет), should/shouldn't (совет), "
        "have to / has to / don't have to (внешняя необходимость). "
        "Не меньше трети заданий — отрицания, где mustn't (нельзя) и don't have to (не обязан) "
        "означают разное. "
        "ЖЕЛЕЗНОЕ: после модального глагол без to и без -s — She can swim, не She can swims. "
        "Глаголы: swim, drive, speak, come, go, work, wait, help, stay, leave, smoke, run."
    ),
    "past_continuous": (
        "Past Continuous. Равномерно покрой три формы: утверждение (I was working / "
        "They were sleeping), отрицание (I wasn't working), вопрос (Were you working?). "
        "Не меньше половины заданий — где решает выбор was или were по подлежащему. "
        "Обязательно включи 8-10 заданий на связку с Past Simple через when/while: "
        "I was cooking when he came. "
        "Глаголы: work, sleep, read, cook, watch, wait, drive, talk, play, study, rain."
    ),
    "irregular_participle": (
        "Третья форма неправильных глаголов. Давай задания в Present Perfect, потому что "
        "именно там третья форма и нужна: I have seen it / She has taken it / "
        "Have you eaten? / I haven't written it. "
        "Не меньше трети — глаголы, где третья форма отличается от второй, потому что "
        "только там она чему-то учит: go/went/gone, see/saw/seen, take/took/taken, "
        "write/wrote/written, eat/ate/eaten, drink/drank/drunk, speak/spoke/spoken, "
        "give/gave/given, know/knew/known, do/did/done, break/broke/broken, "
        "forget/forgot/forgotten."
    ),
    "present_perfect": (
        "Present Perfect. Равномерно покрой три формы: утверждение (I have finished / "
        "She has gone), отрицание (I haven't finished / He hasn't called), вопрос "
        "(Have you finished? / Has she called?). Не меньше трети — третье лицо, где решает has. "
        "Обязательно включи 8-10 заданий с already, just, never, yet, ever — это маркеры, "
        "по которым время и опознаётся. "
        "Обязательно 6-8 заданий на контраст с Past Simple: yesterday требует Past Simple, "
        "а не Present Perfect. "
        "Глаголы: finish, go, see, do, eat, read, write, call, buy, lose, break, forget."
    ),
    "past_perfect": (
        "Past Perfect. Равномерно покрой три формы: утверждение (I had finished), "
        "отрицание (I hadn't finished), вопрос (Had you finished?). "
        "Не меньше половины заданий — с двумя действиями, где Past Perfect обозначает "
        "то, что было раньше: When I came, he had already left. "
        "Обязательно включи before и after, и 6-8 заданий на контраст с Past Simple. "
        "Глаголы: leave, finish, come, eat, see, do, go, buy, start, close, lose, forget."
    ),
    "present_perfect_continuous": (
        "Present Perfect Continuous. Равномерно покрой три формы: утверждение "
        "(I have been working), отрицание (I haven't been working), вопрос "
        "(Have you been working?). Не меньше трети — третье лицо с has been. "
        "Не меньше половины заданий — с for и since, потому что время про длительность: "
        "I have been waiting for two hours / since morning. "
        "Глаголы длительные: work, wait, study, live, read, learn, rain, play, run, talk, cook."
    ),
    "used_to": (
        "Конструкция used to. Равномерно покрой три формы: утверждение (I used to smoke), "
        "отрицание (I didn't use to smoke — БЕЗ d), вопрос (Did you use to smoke? — тоже без d). "
        "Не меньше трети заданий — отрицание и вопрос, потому что потеря d и есть ошибка. "
        "Все задания про привычку в прошлом, которой больше нет: раньше курил, раньше жил, "
        "раньше играл. "
        "Глаголы: smoke, live, play, work, go, drink, have, read, watch, study, eat."
    ),
    "gerund_infinitive": (
        "Герундий или инфинитив после глагола. Равномерно покрой: глаголы с -ing "
        "(enjoy, finish, stop, like doing), глаголы с to (want, need, decide, hope, promise), "
        "и глаголы, где возможны оба (start, begin, like). "
        "Не меньше половины заданий — на глаголы, которые жёстко требуют одного: "
        "enjoy reading, не enjoy to read; want to go, не want going. "
        "Глаголы-управляющие: want, need, like, enjoy, finish, stop, start, decide, hope, "
        "promise, try, forget, remember. "
        "Глаголы-зависимые: read, go, work, eat, smoke, play, study, travel, help."
    ),
    "conditionals_01": (
        "Условные нулевого и первого типа. Равномерно покрой оба: нулевой — общая истина "
        "(If you heat water, it boils), первый — реальное будущее "
        "(If it rains, I will stay at home). "
        "ЖЕЛЕЗНОЕ требование, и это главная ошибка: после if СТОИТ НАСТОЯЩЕЕ время, "
        "will идёт во вторую часть — If it rains, I will stay, НЕ If it will rain. "
        "Не меньше трети заданий — где if стоит первым, и ещё треть — где вторым "
        "(I will stay at home if it rains). "
        "Глаголы: rain, come, call, help, go, stay, buy, work, finish, see, ask."
    ),
    "conditional_second": (
        "Условные второго типа — нереальное настоящее. Формула: If + Past Simple, would + "
        "первая форма (If I had money, I would buy a car). "
        "ЖЕЛЕЗНОЕ: после if прошедшее время, would НЕ ставится в часть с if. "
        "Не меньше трети заданий — с were вместо was для всех лиц: If I were you. "
        "Не меньше трети — отрицания (If I didn't work, I wouldn't be tired). "
        "Глаголы: have, be, buy, go, live, know, help, come, work, travel, win."
    ),
    "conditional_third": (
        "Условные третьего типа — нереальное прошлое. Формула: If + had + третья форма, "
        "would have + третья форма (If I had known, I would have called). "
        "ЖЕЛЕЗНОЕ: обе части в прошлом, и would have никогда не стоит после if. "
        "Не меньше трети заданий — отрицания (If I hadn't been late, I wouldn't have missed it). "
        "ОБЯЗАТЕЛЬНО меняй подлежащие и лексику: не только I и we, но he, she, they, "
        "my friend, the teacher, the kids. Не больше четверти заданий с одним и тем же глаголом. "
        "Добавляй дополнения и обстоятельства, чтобы фразы были разными по смыслу: "
        "If she had studied, she would have passed the exam. "
        "Глаголы с ясной третьей формой: know, see, go, come, take, tell, call, help, "
        "leave, forget, win, lose, break, buy, find, write, speak, eat, give, meet, "
        "study, pass, miss, catch, bring."
    ),
    "passive_simple": (
        "Пассивный залог в настоящем и прошедшем. Формула: to be + третья форма "
        "(The house is built / The letter was written). "
        "Равномерно покрой: настоящее (is/are made), прошедшее (was/were built), "
        "отрицание (isn't made), вопрос (Was it built?). "
        "Не меньше трети заданий — где решает выбор is/are или was/were по числу подлежащего. "
        "Включи 6-8 заданий с by: The book was written by my brother. "
        "Глаголы: make, build, write, send, buy, clean, open, close, find, take, invite, sell."
    ),
    "reported_speech": (
        "Косвенная речь. Главное правило — сдвиг времени на шаг назад: "
        "«I am tired» → He said he was tired; «I work» → She said she worked; "
        "«I will come» → He said he would come; «I have finished» → She said she had finished. "
        "Не меньше половины заданий — на сам сдвиг времени, потому что это и есть тема. "
        "Обязательно включи смену местоимений (I → he/she) и 6-8 заданий с "
        "He asked if / He asked where. "
        "ОБЯЗАТЕЛЬНО меняй вводящую часть, не больше четверти на одну: "
        "He said / She told me / They asked / My friend said / The teacher told us / "
        "Mum asked. Меняй и содержание: работа, погода, планы, еда, дорога, деньги, "
        "здоровье, учёба — не крутись на одном сюжете. "
        "Глаголы: say, tell, ask, work, come, go, live, finish, call, help, know, want, "
        "buy, eat, sleep, travel, study, wait, rain, cost, need, start."
    ),
    "relative_clauses": (
        "Относительные придаточные: who, which, that. Равномерно покрой: who о людях "
        "(the man who lives here), which о вещах (the book which I bought), "
        "that вместо обоих (the man that lives here). "
        "Не меньше половины заданий — выбор между who и which по тому, человек это или вещь: "
        "это и есть решение, которое тема тренирует. "
        "ОБЯЗАТЕЛЬНО меняй место придаточного в предложении, не больше четверти заданий "
        "могут начинаться с This is: "
        "подлежащее — The man who lives here is my friend; "
        "дополнение — I know a girl who speaks French; "
        "после глагола — I bought the book which you wanted; "
        "с отрицанием — The film which we saw wasn't good; "
        "с вопросом — Do you know the man who called me? "
        "Существительные: man, woman, girl, boy, friend, teacher, book, car, house, film, "
        "letter, shop, city, dog, phone, bag, street, song, story, doctor."
    ),
    "tag_questions": (
        "Разделительные вопросы. Правило: утверждение — отрицательный хвостик "
        "(You are tired, aren't you?), отрицание — утвердительный (You aren't tired, are you?). "
        "Равномерно покрой хвостики с to be (isn't he / aren't you / wasn't it), "
        "с do/does/did (don't you / doesn't he / didn't they), с will и can. "
        "Не меньше половины заданий — где основная часть отрицательная, потому что "
        "там полярность хвостика и путают. "
        "Лексика: tired, ready, late, at home, work, live, go, know, come, help, see, can swim."
    ),
}
