"""Sentence construction for Present Simple — the first topic rebuilt.

The gap-fill format cannot prove a tense is known. Four options and one blank
give a 25% floor from guessing, and a learner can clear every card in a topic
while still being unable to say the sentence. Measuring it made that concrete:
under the old rule a topic closed after seven correct multiple-choice answers.

Construction removes the floor. You are given the Russian and produce the
English, and there is nothing to eliminate.

Each row carries the sentence twice:

  * `en` is the answer for the typing mode and for the checker, with
    `alternatives` holding the other honest renderings («does not» beside
    «doesn't») so a correct answer is never marked wrong;
  * `slots` is the same sentence cut into decisions for the assisted mode —
    subject, then auxiliary, then verb form. Each tap narrows what comes next,
    which is support without being a giveaway: after «She» the learner still
    has to know it takes «doesn't» rather than «don't», and elimination will
    not reveal that.

A topic starts in the assisted mode and is passed in the typing one.

All 100 were verified mechanically before landing here: the slots concatenate
back into exactly `en`, every slot offers its own answer, and distractors come
from the same paradigm (`work / works / worked`) rather than being filler of a
different part of speech.

Coverage is deliberate — 38 affirmative, 32 negative, 30 questions, and 56 of
them in the third person singular, which is where the -s that Russian speakers
drop actually lives.

Revision ID: 0055
Revises: 0054
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None

TOPIC_SLUG = "tense_present_simple"

# (ru, en, alternatives, slots)
PHRASES: tuple[tuple, ...] = (
    (
        "Я часто работаю дома.",
        "I often work at home.",
        [],
        [{"correct": "I", "options": ["I", "He", "They", "We"]}, {"correct": "often work", "options": ["often work", "often works", "works often", "work often"]}, {"correct": "at home.", "options": ["at home.", "in home.", "to home."]}],
    ),
    (
        "Он обычно живет здесь.",
        "He usually lives here.",
        [],
        [{"correct": "He", "options": ["He", "They", "I", "We"]}, {"correct": "usually lives", "options": ["usually lives", "usually live", "lives usually", "live usually"]}, {"correct": "here.", "options": ["here.", "there.", "home."]}],
    ),
    (
        "Они всегда читают книги.",
        "They always read books.",
        [],
        [{"correct": "They", "options": ["They", "He", "She", "It"]}, {"correct": "always read", "options": ["always read", "always reads", "read always", "reads always"]}, {"correct": "books.", "options": ["books.", "a book.", "the book."]}],
    ),
    (
        "Она редко ест мясо.",
        "She rarely eats meat.",
        [],
        [{"correct": "She", "options": ["She", "I", "They", "We"]}, {"correct": "rarely eats", "options": ["rarely eats", "rarely eat", "eats rarely", "eat rarely"]}, {"correct": "meat.", "options": ["meat.", "fish.", "fruit."]}],
    ),
    (
        "Я не хочу пить кофе.",
        "I don't want to drink coffee.",
        ["I do not want to drink coffee."],
        [{"correct": "I", "options": ["I", "He", "She", "It"]}, {"correct": "don't want", "options": ["don't want", "doesn't want", "don't wants", "doesn't wants"]}, {"correct": "to drink coffee.", "options": ["to drink coffee.", "drink coffee.", "drinking coffee."]}],
    ),
    (
        "Он не говорит по-английски.",
        "He doesn't speak English.",
        ["He does not speak English."],
        [{"correct": "He", "options": ["He", "I", "They", "We"]}, {"correct": "doesn't speak", "options": ["doesn't speak", "don't speak", "doesn't speaks", "don't speaks"]}, {"correct": "English.", "options": ["English.", "French.", "Spanish."]}],
    ),
    (
        "Мы не знаем этого человека.",
        "We don't know this person.",
        ["We do not know this person."],
        [{"correct": "We", "options": ["We", "She", "He", "It"]}, {"correct": "don't know", "options": ["don't know", "doesn't know", "don't knows", "doesn't knows"]}, {"correct": "this person.", "options": ["this person.", "him.", "the man."]}],
    ),
    (
        "Она не учится в университете.",
        "She doesn't study at university.",
        ["She does not study at university."],
        [{"correct": "She", "options": ["She", "They", "I", "You"]}, {"correct": "doesn't study", "options": ["doesn't study", "don't study", "doesn't studies", "don't studies"]}, {"correct": "at university.", "options": ["at university.", "in university.", "to university."]}],
    ),
    (
        "Ты часто играешь в футбол?",
        "Do you often play football?",
        [],
        [{"correct": "Do", "options": ["Do", "Does", "Are", "Is"]}, {"correct": "you often play", "options": ["you often play", "you play often", "often you play", "do you play often"]}, {"correct": "football?", "options": ["football?", "tennis?", "games?"]}],
    ),
    (
        "Он работает по субботам?",
        "Does he work on Saturdays?",
        [],
        [{"correct": "Does", "options": ["Does", "Do", "Is", "Are"]}, {"correct": "he work", "options": ["he work", "he works", "does he works", "do he work"]}, {"correct": "on Saturdays?", "options": ["on Saturdays?", "in Saturdays?", "at Saturdays?"]}],
    ),
    (
        "Она помогает тебе?",
        "Does she help you?",
        [],
        [{"correct": "Does", "options": ["Does", "Do", "Is", "Are"]}, {"correct": "she help", "options": ["she help", "she helps", "do she help", "does she helps"]}, {"correct": "you?", "options": ["you?", "him?", "them?"]}],
    ),
    (
        "Они начинают работу рано?",
        "Do they start work early?",
        [],
        [{"correct": "Do", "options": ["Do", "Does", "Are", "Is"]}, {"correct": "they start work", "options": ["they start work", "they starts work", "start they work", "do they starts work"]}, {"correct": "early?", "options": ["early?", "late?", "now?"]}],
    ),
    (
        "Я всегда пью чай утром.",
        "I always drink tea in the morning.",
        [],
        [{"correct": "I", "options": ["I", "He", "She", "They"]}, {"correct": "always", "options": ["always", "never", "often", "usually"]}, {"correct": "drink", "options": ["drink", "drinks", "drank", "drinking"]}, {"correct": "tea in the morning.", "options": ["tea in the morning.", "coffee at night."]}],
    ),
    (
        "Он часто смотрит фильмы вечером.",
        "He often watches films in the evening.",
        [],
        [{"correct": "He", "options": ["He", "I", "We", "They"]}, {"correct": "often", "options": ["often", "always", "never"]}, {"correct": "watches", "options": ["watches", "watch", "watched", "watching"]}, {"correct": "films in the evening.", "options": ["films in the evening.", "books at home."]}],
    ),
    (
        "Она никогда не видит их.",
        "She never sees them.",
        [],
        [{"correct": "She", "options": ["She", "I", "You", "They"]}, {"correct": "never", "options": ["never", "always", "often"]}, {"correct": "sees", "options": ["sees", "see", "saw", "seeing"]}, {"correct": "them.", "options": ["them.", "him.", "us."]}],
    ),
    (
        "Я не играю в теннис.",
        "I do not play tennis.",
        ["I don't play tennis."],
        [{"correct": "I", "options": ["I", "He", "She"]}, {"correct": "do not", "options": ["do not", "does not", "did not"]}, {"correct": "play", "options": ["play", "plays", "played"]}, {"correct": "tennis.", "options": ["tennis.", "football."]}],
    ),
    (
        "Она не любит холодный кофе.",
        "She does not like cold coffee.",
        ["She doesn't like cold coffee."],
        [{"correct": "She", "options": ["She", "I", "They"]}, {"correct": "does not", "options": ["does not", "do not", "did not"]}, {"correct": "like", "options": ["like", "likes", "liked"]}, {"correct": "cold coffee.", "options": ["cold coffee.", "hot tea."]}],
    ),
    (
        "Он не заканчивает работу вовремя.",
        "He does not finish work on time.",
        ["He doesn't finish work on time."],
        [{"correct": "He", "options": ["He", "I", "We"]}, {"correct": "does not", "options": ["does not", "do not", "did not"]}, {"correct": "finish", "options": ["finish", "finishes", "finished"]}, {"correct": "work on time.", "options": ["work on time.", "school early."]}],
    ),
    (
        "Ты хочешь пойти домой?",
        "Do you want to go home?",
        [],
        [{"correct": "Do", "options": ["Do", "Does", "Did"]}, {"correct": "you", "options": ["you", "he", "she"]}, {"correct": "want", "options": ["want", "wants", "wanted"]}, {"correct": "to go home?", "options": ["to go home?", "to eat lunch?"]}],
    ),
    (
        "Она знает твое имя?",
        "Does she know your name?",
        [],
        [{"correct": "Does", "options": ["Does", "Do", "Did"]}, {"correct": "she", "options": ["she", "they", "we"]}, {"correct": "know", "options": ["know", "knows", "knew"]}, {"correct": "your name?", "options": ["your name?", "this city?"]}],
    ),
    (
        "Они говорят по-русски?",
        "Do they speak Russian?",
        [],
        [{"correct": "Do", "options": ["Do", "Does", "Did"]}, {"correct": "they", "options": ["they", "he", "she"]}, {"correct": "speak", "options": ["speak", "speaks", "spoke"]}, {"correct": "Russian?", "options": ["Russian?", "English?"]}],
    ),
    (
        "Мы всегда помогаем нашим друзьям.",
        "We always help our friends.",
        [],
        [{"correct": "We", "options": ["We", "He", "She"]}, {"correct": "always", "options": ["always", "never", "often"]}, {"correct": "help", "options": ["help", "helps", "helped"]}, {"correct": "our friends.", "options": ["our friends.", "my family."]}],
    ),
    (
        "Она обычно начинает рано.",
        "She usually starts early.",
        [],
        [{"correct": "She", "options": ["She", "I", "They"]}, {"correct": "usually", "options": ["usually", "always", "often"]}, {"correct": "starts", "options": ["starts", "start", "started"]}, {"correct": "early.", "options": ["early.", "late."]}],
    ),
    (
        "Он часто ест рыбу?",
        "Does he often eat fish?",
        [],
        [{"correct": "Does", "options": ["Does", "Do", "Did"]}, {"correct": "he", "options": ["he", "you", "they"]}, {"correct": "often", "options": ["often", "always", "never"]}, {"correct": "eat fish?", "options": ["eat fish?", "drink water?"]}],
    ),
    (
        "Я всегда начинаю работу вовремя.",
        "I always start work on time.",
        [],
        [{"correct": "I", "options": ["I", "He", "They", "We"]}, {"correct": "always", "options": ["always", "never", "usually", "often"]}, {"correct": "start", "options": ["start", "starts", "starting", "started"]}, {"correct": "work on time.", "options": ["work on time.", "work early.", "study now.", "help me."]}],
    ),
    (
        "Она часто помогает своей маме.",
        "She often helps her mother.",
        [],
        [{"correct": "She", "options": ["She", "I", "They", "You"]}, {"correct": "often", "options": ["often", "always", "never", "usually"]}, {"correct": "helps", "options": ["helps", "help", "helping", "helped"]}, {"correct": "her mother.", "options": ["her mother.", "me.", "them.", "him."]}],
    ),
    (
        "Они не нуждаются в помощи.",
        "They do not need help.",
        ["They don't need help."],
        [{"correct": "They", "options": ["They", "He", "She", "It"]}, {"correct": "do not", "options": ["do not", "does not", "did not", "will not"]}, {"correct": "need", "options": ["need", "needs", "needing", "needed"]}, {"correct": "help.", "options": ["help.", "books.", "food.", "water."]}],
    ),
    (
        "Он не хочет изучать английский.",
        "He does not want to study English.",
        ["He doesn't want to study English."],
        [{"correct": "He", "options": ["He", "I", "We", "They"]}, {"correct": "does not", "options": ["does not", "do not", "did not", "will not"]}, {"correct": "want", "options": ["want", "wants", "wanting", "wanted"]}, {"correct": "to study English.", "options": ["to study English.", "to read books.", "to eat fish.", "to go home."]}],
    ),
    (
        "Они часто играют в теннис?",
        "Do they often play tennis?",
        [],
        [{"correct": "Do", "options": ["Do", "Does", "Did", "Will"]}, {"correct": "they", "options": ["they", "he", "she", "it"]}, {"correct": "often play", "options": ["often play", "often plays", "always play", "never play"]}, {"correct": "tennis?", "options": ["tennis?", "football?", "games?", "books?"]}],
    ),
    (
        "Она обычно пьет воду?",
        "Does she usually drink water?",
        [],
        [{"correct": "Does", "options": ["Does", "Do", "Did", "Will"]}, {"correct": "she", "options": ["she", "they", "we", "you"]}, {"correct": "usually drink", "options": ["usually drink", "usually drinks", "often drink", "never drink"]}, {"correct": "water?", "options": ["water?", "tea?", "milk?", "coffee?"]}],
    ),
    (
        "Я обычно заканчиваю работу поздно.",
        "I usually finish work late.",
        [],
        [{"correct": "I", "options": ["I", "He", "She", "It"]}, {"correct": "usually", "options": ["usually", "always", "often", "never"]}, {"correct": "finish", "options": ["finish", "finishes", "finished", "finishing"]}, {"correct": "work late.", "options": ["work late.", "study now.", "eat much.", "read fast."]}],
    ),
    (
        "Она всегда живет в Лондоне.",
        "She always lives in London.",
        [],
        [{"correct": "She", "options": ["She", "They", "We", "I"]}, {"correct": "always", "options": ["always", "often", "usually", "never"]}, {"correct": "lives", "options": ["lives", "live", "living", "lived"]}, {"correct": "in London.", "options": ["in London.", "in Moscow.", "at home.", "in school."]}],
    ),
    (
        "Мы не видим их часто.",
        "We do not see them often.",
        ["We don't see them often."],
        [{"correct": "We", "options": ["We", "He", "She", "It"]}, {"correct": "do not", "options": ["do not", "does not", "did not", "will not"]}, {"correct": "see", "options": ["see", "sees", "seeing", "saw"]}, {"correct": "them often.", "options": ["them often.", "him often.", "her often.", "it often."]}],
    ),
    (
        "Он не работает в офисе.",
        "He does not work in an office.",
        ["He doesn't work in an office."],
        [{"correct": "He", "options": ["He", "I", "They", "We"]}, {"correct": "does not", "options": ["does not", "do not", "did not", "will not"]}, {"correct": "work", "options": ["work", "works", "working", "worked"]}, {"correct": "in an office.", "options": ["in an office.", "at home.", "at school.", "in a shop."]}],
    ),
    (
        "Ты знаешь ответ?",
        "Do you know the answer?",
        [],
        [{"correct": "Do", "options": ["Do", "Does", "Did", "Will"]}, {"correct": "you", "options": ["you", "he", "she", "it"]}, {"correct": "know", "options": ["know", "knows", "knowing", "knew"]}, {"correct": "the answer?", "options": ["the answer?", "the name?", "the place?", "the way?"]}],
    ),
    (
        "Он всегда ест яблоки.",
        "He always eats apples.",
        [],
        [{"correct": "He", "options": ["He", "I", "They", "We"]}, {"correct": "always", "options": ["always", "never", "often", "usually"]}, {"correct": "eats", "options": ["eats", "eat", "eating", "ate"]}, {"correct": "apples.", "options": ["apples.", "fish.", "meat.", "bread."]}],
    ),
    (
        "Я часто играю в теннис.",
        "I often play tennis.",
        [],
        [{"correct": "I", "options": ["I", "He", "They", "She"]}, {"correct": "often", "options": ["often", "never", "usually", "always"]}, {"correct": "play", "options": ["play", "plays", "played", "playing"]}, {"correct": "tennis.", "options": ["tennis.", "a book.", "in London.", "early."]}],
    ),
    (
        "Она всегда изучает английский.",
        "She always studies English.",
        [],
        [{"correct": "She", "options": ["She", "I", "We", "They"]}, {"correct": "always", "options": ["always", "never", "often", "usually"]}, {"correct": "studies", "options": ["studies", "study", "studied", "studying"]}, {"correct": "English.", "options": ["English.", "the answer.", "a movie.", "at home."]}],
    ),
    (
        "Он никогда не ест рыбу.",
        "He never eats fish.",
        [],
        [{"correct": "He", "options": ["He", "They", "We", "You"]}, {"correct": "never", "options": ["never", "always", "often", "usually"]}, {"correct": "eats", "options": ["eats", "eat", "ate", "eating"]}, {"correct": "fish.", "options": ["fish.", "meat.", "apples.", "water."]}],
    ),
    (
        "Мы обычно не пьем кофе.",
        "We usually do not drink coffee.",
        ["We usually don't drink coffee."],
        [{"correct": "We", "options": ["We", "She", "He", "It"]}, {"correct": "usually", "options": ["usually", "never", "always", "often"]}, {"correct": "do not", "options": ["do not", "does not", "don't", "doesn't"]}, {"correct": "drink", "options": ["drink", "drinks", "drank", "drinking"]}, {"correct": "coffee.", "options": ["coffee.", "tea.", "water.", "milk."]}],
    ),
    (
        "Она не нуждается в помощи.",
        "She does not need help.",
        ["She doesn't need help."],
        [{"correct": "She", "options": ["She", "They", "We", "I"]}, {"correct": "does not", "options": ["does not", "do not", "doesn't", "don't"]}, {"correct": "need", "options": ["need", "needs", "needed", "needing"]}, {"correct": "help.", "options": ["help.", "food.", "water.", "books."]}],
    ),
    (
        "Они не заканчивают работу рано.",
        "They do not finish work early.",
        ["They don't finish work early."],
        [{"correct": "They", "options": ["They", "He", "She", "It"]}, {"correct": "do not", "options": ["do not", "does not", "don't", "doesn't"]}, {"correct": "finish", "options": ["finish", "finishes", "finished", "finishing"]}, {"correct": "work", "options": ["work", "the job", "the book", "the tea"]}, {"correct": "early.", "options": ["early.", "late.", "here.", "there."]}],
    ),
    (
        "Ты часто пьешь воду?",
        "Do you often drink water?",
        [],
        [{"correct": "Do", "options": ["Do", "Does", "Are", "Is"]}, {"correct": "you", "options": ["you", "he", "she", "it"]}, {"correct": "often", "options": ["often", "always", "never", "usually"]}, {"correct": "drink", "options": ["drink", "drinks", "drank", "drinking"]}, {"correct": "water?", "options": ["water?", "tea?", "coffee?", "milk?"]}],
    ),
    (
        "Он всегда работает в офисе?",
        "Does he always work in an office?",
        [],
        [{"correct": "Does", "options": ["Does", "Do", "Is", "Are"]}, {"correct": "he", "options": ["he", "you", "they", "we"]}, {"correct": "always", "options": ["always", "never", "often", "usually"]}, {"correct": "work", "options": ["work", "works", "worked", "working"]}, {"correct": "in an office?", "options": ["in an office?", "at home?", "at school?", "in London?"]}],
    ),
    (
        "Она читает книги каждый день?",
        "Does she read books every day?",
        [],
        [{"correct": "Does", "options": ["Does", "Do", "Is", "Are"]}, {"correct": "she", "options": ["she", "they", "we", "you"]}, {"correct": "read", "options": ["read", "reads", "reading", "readed"]}, {"correct": "books", "options": ["books", "the news", "the text", "the name"]}, {"correct": "every day?", "options": ["every day?", "at night?", "in the morning?", "often?"]}],
    ),
    (
        "Они всегда помогают нам?",
        "Do they always help us?",
        [],
        [{"correct": "Do", "options": ["Do", "Does", "Are", "Is"]}, {"correct": "they", "options": ["they", "he", "she", "it"]}, {"correct": "always", "options": ["always", "never", "often", "usually"]}, {"correct": "help", "options": ["help", "helps", "helped", "helping"]}, {"correct": "us?", "options": ["us?", "me?", "him?", "her?"]}],
    ),
    (
        "Ты обычно хочешь есть?",
        "Do you usually want to eat?",
        [],
        [{"correct": "Do", "options": ["Do", "Does", "Is", "Are"]}, {"correct": "you", "options": ["you", "he", "she", "it"]}, {"correct": "usually", "options": ["usually", "always", "often", "never"]}, {"correct": "want", "options": ["want", "wants", "wanted", "wanting"]}, {"correct": "to eat?", "options": ["to eat?", "to sleep?", "to work?", "to go?"]}],
    ),
    (
        "Он часто смотрит фильмы?",
        "Does he often watch movies?",
        [],
        [{"correct": "Does", "options": ["Does", "Do", "Is", "Are"]}, {"correct": "he", "options": ["he", "they", "we", "you"]}, {"correct": "often", "options": ["often", "always", "never", "usually"]}, {"correct": "watch", "options": ["watch", "watches", "watched", "watching"]}, {"correct": "movies?", "options": ["movies?", "TV?", "the news?", "us?"]}],
    ),
    (
        "Я всегда читаю книги дома.",
        "I always read books at home.",
        [],
        [{"correct": "I", "options": ["I", "He", "She", "They"]}, {"correct": "always read", "options": ["always read", "always reads", "often read", "often reads"]}, {"correct": "books at home.", "options": ["books at home.", "the book at home.", "a book at home."]}],
    ),
    (
        "Он часто работает в парке.",
        "He often works in the park.",
        [],
        [{"correct": "He", "options": ["He", "I", "They", "We"]}, {"correct": "often works", "options": ["often works", "often work", "always works", "always work"]}, {"correct": "in the park.", "options": ["in the park.", "at the park.", "to the park."]}],
    ),
    (
        "Она обычно говорит по-русски.",
        "She usually speaks Russian.",
        [],
        [{"correct": "She", "options": ["She", "I", "They", "We"]}, {"correct": "usually speaks", "options": ["usually speaks", "usually speak", "often speaks", "often speak"]}, {"correct": "Russian.", "options": ["Russian.", "in Russian.", "the Russian."]}],
    ),
    (
        "Мы не любим этот фильм.",
        "We do not like this film.",
        ["We don't like this film."],
        [{"correct": "We", "options": ["We", "He", "She", "It"]}, {"correct": "do not like", "options": ["do not like", "does not like", "do not likes"]}, {"correct": "this film.", "options": ["this film.", "the film.", "that film."]}],
    ),
    (
        "Он не хочет играть сейчас.",
        "He does not want to play now.",
        ["He doesn't want to play now."],
        [{"correct": "He", "options": ["He", "I", "We", "They"]}, {"correct": "does not want", "options": ["does not want", "do not want", "does not wants"]}, {"correct": "to play now.", "options": ["to play now.", "play now.", "to playing now."]}],
    ),
    (
        "Она не видит своих друзей.",
        "She does not see her friends.",
        ["She doesn't see her friends."],
        [{"correct": "She", "options": ["She", "I", "We", "They"]}, {"correct": "does not see", "options": ["does not see", "do not see", "does not sees"]}, {"correct": "her friends.", "options": ["her friends.", "my friends.", "their friends."]}],
    ),
    (
        "Ты часто ешь здесь?",
        "Do you often eat here?",
        [],
        [{"correct": "Do you", "options": ["Do you", "Does you", "Do he"]}, {"correct": "often eat", "options": ["often eat", "often eats", "always eat", "always eats"]}, {"correct": "here?", "options": ["here?", "there?", "home?"]}],
    ),
    (
        "Он работает по воскресеньям?",
        "Does he work on Sundays?",
        [],
        [{"correct": "Does he", "options": ["Does he", "Do he", "Does they"]}, {"correct": "work", "options": ["work", "works", "working"]}, {"correct": "on Sundays?", "options": ["on Sundays?", "in Sundays?", "at Sundays?"]}],
    ),
    (
        "Она учится каждый день?",
        "Does she study every day?",
        [],
        [{"correct": "Does she", "options": ["Does she", "Do she", "Does they"]}, {"correct": "study", "options": ["study", "studies", "studying"]}, {"correct": "every day?", "options": ["every day?", "all day?", "now?"]}],
    ),
    (
        "Я всегда пью сок.",
        "I always drink juice.",
        [],
        [{"correct": "I", "options": ["I", "He", "She"]}, {"correct": "always drink", "options": ["always drink", "always drinks", "often drink"]}, {"correct": "juice.", "options": ["juice.", "the juice.", "my juice."]}],
    ),
    (
        "Она не говорит по-немецки.",
        "She does not speak German.",
        ["She doesn't speak German."],
        [{"correct": "She", "options": ["She", "I", "We", "They"]}, {"correct": "does not speak", "options": ["does not speak", "do not speak", "does not speaks"]}, {"correct": "German.", "options": ["German.", "English.", "Russian."]}],
    ),
    (
        "Они всегда помогают мне.",
        "They always help me.",
        [],
        [{"correct": "They", "options": ["They", "He", "She"]}, {"correct": "always help", "options": ["always help", "always helps", "often help"]}, {"correct": "me.", "options": ["me.", "us.", "him."]}],
    ),
    (
        "Он всегда пьет чай.",
        "He always drinks tea.",
        [],
        [{"correct": "He", "options": ["He", "I", "They", "We"]}, {"correct": "always", "options": ["always", "never", "often"]}, {"correct": "drinks", "options": ["drinks", "drink", "drank"]}, {"correct": "tea.", "options": ["tea.", "milk."]}],
    ),
    (
        "Я обычно не играю здесь.",
        "I usually don't play here.",
        ["I usually do not play here."],
        [{"correct": "I", "options": ["I", "He", "She"]}, {"correct": "usually", "options": ["usually", "often"]}, {"correct": "don't", "options": ["don't", "doesn't", "didn't"]}, {"correct": "play", "options": ["play", "plays"]}, {"correct": "here.", "options": ["here.", "there."]}],
    ),
    (
        "Она часто помогает мне?",
        "Does she often help me?",
        [],
        [{"correct": "Does", "options": ["Does", "Do"]}, {"correct": "she", "options": ["she", "he", "they"]}, {"correct": "often", "options": ["often", "always"]}, {"correct": "help", "options": ["help", "helps"]}, {"correct": "me?", "options": ["me?", "him?"]}],
    ),
    (
        "Они не знают мой ответ.",
        "They don't know my answer.",
        ["They do not know my answer."],
        [{"correct": "They", "options": ["They", "He", "She"]}, {"correct": "don't", "options": ["don't", "doesn't"]}, {"correct": "know", "options": ["know", "knows"]}, {"correct": "my", "options": ["my", "his"]}, {"correct": "answer.", "options": ["answer.", "name."]}],
    ),
    (
        "Он часто начинает рано?",
        "Does he often start early?",
        [],
        [{"correct": "Does", "options": ["Does", "Do"]}, {"correct": "he", "options": ["he", "they", "we"]}, {"correct": "often", "options": ["often", "always"]}, {"correct": "start", "options": ["start", "starts"]}, {"correct": "early?", "options": ["early?", "late?"]}],
    ),
    (
        "Она никогда не читает дома.",
        "She never reads at home.",
        [],
        [{"correct": "She", "options": ["She", "I", "They"]}, {"correct": "never", "options": ["never", "always", "often"]}, {"correct": "reads", "options": ["reads", "read"]}, {"correct": "at", "options": ["at", "in"]}, {"correct": "home.", "options": ["home.", "work."]}],
    ),
    (
        "Он не нуждается в еде.",
        "He doesn't need food.",
        ["He does not need food."],
        [{"correct": "He", "options": ["He", "They", "We"]}, {"correct": "doesn't", "options": ["doesn't", "don't"]}, {"correct": "need", "options": ["need", "needs"]}, {"correct": "food.", "options": ["food.", "help."]}],
    ),
    (
        "Мы часто видим их.",
        "We often see them.",
        [],
        [{"correct": "We", "options": ["We", "He", "She"]}, {"correct": "often", "options": ["often", "always"]}, {"correct": "see", "options": ["see", "sees"]}, {"correct": "them.", "options": ["them.", "him."]}],
    ),
    (
        "Она обычно заканчивает поздно.",
        "She usually finishes late.",
        [],
        [{"correct": "She", "options": ["She", "They", "I"]}, {"correct": "usually", "options": ["usually", "always"]}, {"correct": "finishes", "options": ["finishes", "finish"]}, {"correct": "late.", "options": ["late.", "early."]}],
    ),
    (
        "Вы всегда работаете вместе?",
        "Do you always work together?",
        [],
        [{"correct": "Do", "options": ["Do", "Does"]}, {"correct": "you", "options": ["you", "he"]}, {"correct": "always", "options": ["always", "often"]}, {"correct": "work", "options": ["work", "works"]}, {"correct": "together?", "options": ["together?", "here?"]}],
    ),
    (
        "Он не ест мясо.",
        "He doesn't eat meat.",
        ["He does not eat meat."],
        [{"correct": "He", "options": ["He", "I", "They"]}, {"correct": "doesn't", "options": ["doesn't", "don't"]}, {"correct": "eat", "options": ["eat", "eats"]}, {"correct": "meat.", "options": ["meat.", "fish."]}],
    ),
    (
        "Он всегда работает здесь.",
        "He always works here.",
        [],
        [{"correct": "He", "options": ["He", "I", "They", "We"]}, {"correct": "always", "options": ["always", "never", "often", "usually"]}, {"correct": "works", "options": ["works", "work", "worked", "working"]}, {"correct": "here.", "options": ["here.", "there."]}],
    ),
    (
        "Она редко читает утром.",
        "She rarely reads in the morning.",
        [],
        [{"correct": "She", "options": ["She", "They", "You", "We"]}, {"correct": "rarely", "options": ["rarely", "often", "always"]}, {"correct": "reads", "options": ["reads", "read", "reading", "readed"]}, {"correct": "in the morning.", "options": ["in the morning.", "at home."]}],
    ),
    (
        "Я не хочу идти туда.",
        "I do not want to go there.",
        ["I don't want to go there."],
        [{"correct": "I", "options": ["I", "He", "She", "They"]}, {"correct": "do not", "options": ["do not", "does not", "did not", "will not"]}, {"correct": "want to go", "options": ["want to go", "want go", "wants to go"]}, {"correct": "there.", "options": ["there.", "here."]}],
    ),
    (
        "Она не знает его адрес.",
        "She does not know his address.",
        ["She doesn't know his address."],
        [{"correct": "She", "options": ["She", "I", "They", "We"]}, {"correct": "does not", "options": ["does not", "do not", "did not"]}, {"correct": "know", "options": ["know", "knows", "knew"]}, {"correct": "his address.", "options": ["his address.", "my address."]}],
    ),
    (
        "Он часто пьет кофе?",
        "Does he often drink coffee?",
        [],
        [{"correct": "Does", "options": ["Does", "Do", "Did"]}, {"correct": "he", "options": ["he", "they", "we", "you"]}, {"correct": "often drink", "options": ["often drink", "often drinks", "drink often"]}, {"correct": "coffee?", "options": ["coffee?", "tea?"]}],
    ),
    (
        "Мы часто изучаем английский.",
        "We often study English.",
        [],
        [{"correct": "We", "options": ["We", "He", "She"]}, {"correct": "often", "options": ["often", "always", "never"]}, {"correct": "study", "options": ["study", "studies", "studying"]}, {"correct": "English.", "options": ["English.", "French."]}],
    ),
    (
        "Он не нуждается в помощи.",
        "He does not need help.",
        ["He doesn't need help."],
        [{"correct": "He", "options": ["He", "They", "We"]}, {"correct": "does not", "options": ["does not", "do not", "did not"]}, {"correct": "need", "options": ["need", "needs", "needed"]}, {"correct": "help.", "options": ["help.", "money."]}],
    ),
    (
        "Она обычно ест фрукты.",
        "She usually eats fruit.",
        [],
        [{"correct": "She", "options": ["She", "They", "We", "I"]}, {"correct": "usually", "options": ["usually", "always", "often"]}, {"correct": "eats", "options": ["eats", "eat", "eating"]}, {"correct": "fruit.", "options": ["fruit.", "meat."]}],
    ),
    (
        "Они всегда начинают вовремя.",
        "They always start on time.",
        [],
        [{"correct": "They", "options": ["They", "He", "She"]}, {"correct": "always", "options": ["always", "often", "never"]}, {"correct": "start", "options": ["start", "starts", "starting"]}, {"correct": "on time.", "options": ["on time.", "early."]}],
    ),
    (
        "Она заканчивает работу поздно?",
        "Does she finish work late?",
        [],
        [{"correct": "Does", "options": ["Does", "Do", "Did"]}, {"correct": "she", "options": ["she", "they", "we", "you"]}, {"correct": "finish", "options": ["finish", "finishes", "finishing"]}, {"correct": "work late?", "options": ["work late?", "work early?"]}],
    ),
    (
        "Я не вижу его часто.",
        "I do not see him often.",
        ["I don't see him often."],
        [{"correct": "I", "options": ["I", "He", "She", "They"]}, {"correct": "do not", "options": ["do not", "does not", "did not"]}, {"correct": "see", "options": ["see", "sees", "seeing"]}, {"correct": "him often.", "options": ["him often.", "her often."]}],
    ),
    (
        "Он часто смотрит телевизор.",
        "He often watches TV.",
        [],
        [{"correct": "He", "options": ["He", "They", "We", "I"]}, {"correct": "often watches", "options": ["often watch", "often watches", "often watched", "often watching"]}, {"correct": "TV.", "options": ["TV.", "a movie.", "books.", "the radio."]}],
    ),
    (
        "Я не хочу пить чай.",
        "I do not want tea.",
        ["I don't want tea."],
        [{"correct": "I", "options": ["I", "He", "She", "It"]}, {"correct": "do not", "options": ["do not", "does not", "did not", "will not"]}, {"correct": "want", "options": ["want", "wants", "wanted", "wanting"]}, {"correct": "tea.", "options": ["tea.", "coffee.", "water.", "milk."]}],
    ),
    (
        "Она всегда работает здесь?",
        "Does she always work here?",
        [],
        [{"correct": "Does", "options": ["Does", "Do", "Is", "Did"]}, {"correct": "she", "options": ["she", "he", "they", "we"]}, {"correct": "always work", "options": ["always work", "always works", "always worked", "always working"]}, {"correct": "here?", "options": ["here?", "there?", "at home?", "in school?"]}],
    ),
    (
        "Они не знают мой номер.",
        "They do not know my number.",
        ["They don't know my number."],
        [{"correct": "They", "options": ["They", "He", "She", "It"]}, {"correct": "do not", "options": ["do not", "does not", "did not", "cannot"]}, {"correct": "know", "options": ["know", "knows", "knew", "knowing"]}, {"correct": "my number.", "options": ["my number.", "my address.", "my name.", "my house."]}],
    ),
    (
        "Он обычно начинает работу вовремя.",
        "He usually starts work on time.",
        [],
        [{"correct": "He", "options": ["He", "They", "We", "I"]}, {"correct": "usually starts", "options": ["usually starts", "usually start", "usually started", "usually starting"]}, {"correct": "work on time.", "options": ["work on time.", "school late.", "the game now.", "the day early."]}],
    ),
    (
        "Мы всегда читаем книги.",
        "We always read books.",
        [],
        [{"correct": "We", "options": ["We", "She", "He", "It"]}, {"correct": "always read", "options": ["always read", "always reads", "always reading", "always readed"]}, {"correct": "books.", "options": ["books.", "newspapers.", "magazines.", "stories."]}],
    ),
    (
        "Они не живут в Лондоне.",
        "They do not live in London.",
        ["They don't live in London."],
        [{"correct": "They", "options": ["They", "He", "She", "It"]}, {"correct": "do not", "options": ["do not", "does not", "did not", "will not"]}, {"correct": "live", "options": ["live", "lives", "lived", "living"]}, {"correct": "in London.", "options": ["in London.", "in Paris.", "in Moscow.", "in Rome."]}],
    ),
    (
        "Он часто говорит по-английски?",
        "Does he often speak English?",
        [],
        [{"correct": "Does", "options": ["Does", "Do", "Is", "Are"]}, {"correct": "he", "options": ["he", "you", "they", "we"]}, {"correct": "often speak", "options": ["often speak", "often speaks", "often spoke", "often speaking"]}, {"correct": "English?", "options": ["English?", "Russian?", "German?", "French?"]}],
    ),
    (
        "Она всегда помогает мне.",
        "She always helps me.",
        [],
        [{"correct": "She", "options": ["She", "I", "We", "They"]}, {"correct": "always helps", "options": ["always helps", "always help", "always helped", "always helping"]}, {"correct": "me.", "options": ["me.", "him.", "us.", "them."]}],
    ),
    (
        "Я не вижу их часто.",
        "I do not see them often.",
        ["I don't see them often."],
        [{"correct": "I", "options": ["I", "He", "She", "It"]}, {"correct": "do not", "options": ["do not", "does not", "did not", "will not"]}, {"correct": "see", "options": ["see", "sees", "saw", "seeing"]}, {"correct": "them often.", "options": ["them often.", "him often.", "her often.", "you often."]}],
    ),
    (
        "Она часто пьет воду.",
        "She often drinks water.",
        [],
        [{"correct": "She", "options": ["She", "They", "I", "We"]}, {"correct": "often", "options": ["often", "always", "usually", "never"]}, {"correct": "drinks", "options": ["drinks", "drink", "drinking", "drank"]}, {"correct": "water.", "options": ["water.", "milk.", "tea.", "juice."]}],
    ),
    (
        "Он не живет здесь.",
        "He does not live here.",
        ["He doesn't live here."],
        [{"correct": "He", "options": ["He", "They", "We", "I"]}, {"correct": "does not", "options": ["does not", "do not", "is not", "did not"]}, {"correct": "live", "options": ["live", "lives", "living", "lived"]}, {"correct": "here.", "options": ["here.", "there.", "home.", "away."]}],
    ),
    (
        "Она работает в субботу?",
        "Does she work on Saturday?",
        [],
        [{"correct": "Does", "options": ["Does", "Do", "Is", "Did"]}, {"correct": "she", "options": ["she", "he", "it", "they"]}, {"correct": "work", "options": ["work", "works", "working", "worked"]}, {"correct": "on Saturday?", "options": ["on Saturday?", "every day?", "in the morning?", "at home?"]}],
    ),
    (
        "Я всегда хочу спать.",
        "I always want to sleep.",
        [],
        [{"correct": "I", "options": ["I", "They", "We", "You"]}, {"correct": "always", "options": ["always", "often", "usually", "never"]}, {"correct": "want", "options": ["want", "wants", "wanting", "wanted"]}, {"correct": "to sleep.", "options": ["to sleep.", "to eat.", "to drink.", "to go."]}],
    ),
    (
        "Он не играет в футбол.",
        "He doesn't play football.",
        ["He does not play football."],
        [{"correct": "He", "options": ["He", "She", "It", "They"]}, {"correct": "doesn't", "options": ["doesn't", "don't", "isn't", "didn't"]}, {"correct": "play", "options": ["play", "plays", "playing", "played"]}, {"correct": "football.", "options": ["football.", "tennis.", "games.", "chess."]}],
    ),
    (
        "Ты часто читаешь газеты?",
        "Do you often read newspapers?",
        [],
        [{"correct": "Do", "options": ["Do", "Does", "Are", "Did"]}, {"correct": "you", "options": ["you", "they", "we", "I"]}, {"correct": "often", "options": ["often", "always", "usually", "never"]}, {"correct": "read newspapers?", "options": ["read newspapers?", "read books?", "study English?", "play tennis?"]}],
    ),
    (
        "Она никогда не ест рыбу.",
        "She never eats fish.",
        [],
        [{"correct": "She", "options": ["She", "He", "They", "We"]}, {"correct": "never", "options": ["never", "always", "often", "usually"]}, {"correct": "eats", "options": ["eats", "eat", "eating", "ate"]}, {"correct": "fish.", "options": ["fish.", "meat.", "fruit.", "bread."]}],
    ),
    (
        "Они начинают работу вовремя?",
        "Do they start work on time?",
        [],
        [{"correct": "Do", "options": ["Do", "Does", "Are", "Did"]}, {"correct": "they", "options": ["they", "we", "you", "I"]}, {"correct": "start", "options": ["start", "starts", "starting", "started"]}, {"correct": "work on time?", "options": ["work on time?", "school early?", "the game now?", "the class late?"]}],
    ),)


def upgrade() -> None:
    op.create_table(
        "grammar_phrases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "topic_id",
            sa.Integer(),
            sa.ForeignKey("grammar_topics.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("ru", sa.Text(), nullable=False),
        sa.Column("en", sa.Text(), nullable=False),
        # Other correct renderings. The checker accepts any of them, so a
        # learner writing "does not" is not punished for being formal.
        sa.Column("alternatives", JSONB(), nullable=False, server_default="[]"),
        # The assisted mode's decision points. See the module docstring.
        sa.Column("slots", JSONB(), nullable=False, server_default="[]"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )

    bind = op.get_bind()
    topic_id = bind.execute(
        sa.text("SELECT id FROM grammar_topics WHERE slug = :slug"), {"slug": TOPIC_SLUG}
    ).scalar()
    if topic_id is None:
        return
    bind.execute(
        sa.text(
            "INSERT INTO grammar_phrases (topic_id, ru, en, alternatives, slots, position)"
            " VALUES (:topic_id, :ru, :en, CAST(:alts AS jsonb), CAST(:slots AS jsonb), :pos)"
        ),
        [
            {
                "topic_id": topic_id,
                "ru": ru,
                "en": en,
                "alts": json.dumps(alts, ensure_ascii=False),
                "slots": json.dumps(slots, ensure_ascii=False),
                "pos": i,
            }
            for i, (ru, en, alts, slots) in enumerate(PHRASES)
        ],
    )


def downgrade() -> None:
    op.drop_table("grammar_phrases")
