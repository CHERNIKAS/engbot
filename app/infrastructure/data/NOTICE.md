# Источники данных в этой папке

## New General Service List (NGSL)

`ngsl_rank.csv` и `ngsl_forms.csv` получены из New General Service List.

> The New General Service List by Browne, C., Culligan, B., and Phillips, J.
> is licensed under a Creative Commons Attribution-ShareAlike 4.0
> International License.
>
> http://www.newgeneralservicelist.org/

NGSL — список из 2801 базового слова, построенный на подкорпусе Cambridge
English Corpus объёмом 273 млн слов. Даёт около 92% покрытия обычного
английского текста.

Файлы здесь — производные: из исходных данных оставлены только колонки,
которые использует бот.

| файл | содержимое | источник |
|---|---|---|
| `ngsl_rank.csv` | `lemma,rank` — 2809 строк | `NGSL_12_stats.csv`, колонка SFI Rank |
| `ngsl_forms.csv` | `form,headword` — 5705 строк | `NGSL_12_lemmatized_for_teaching.csv` |

Лицензия CC BY-SA 4.0 распространяется и на производные, поэтому эта ссылка на
авторов должна сохраняться при любом дальнейшем изменении файлов.
