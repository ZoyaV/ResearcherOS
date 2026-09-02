# Запустить held-out wCTR smoke-run

Статус: завершён успешно  
Канбан: `board-wctr-evo` / `wctr-evo-smoke`  
Skill chain: `koi-grill-experiment` → `koi-evo-card` → `koi-report-review`

## 0. Привязка

| Поле | Значение |
|------|----------|
| Гипотеза | `c-wctr-prediction` |
| Метод | `m-wctr-evo-smoke` |
| Дата прогона | 2026-09-02 |
| Статус | завершён успешно |
| Данные | синтетический train/test fixture; не историческая bicycle-выгрузка |

## 1. Цель и дизайн

Проверить, можно ли оценивать weighted CTR по сегменту объявления на данных,
которых модель не видела при обучении. Benchmark обучает сглаженную оценку
по `format × device` только на train и считает итоговый score на held-out test.

Прогон Evo: `exp_0001`, hypothesis «Evaluate held-out wCTR without leakage».
Основная команда: `python3 datasets/wctr/benchmark.py --split test`.

## 2. Основная метрика

Основная метрика — test log loss; score Evo равен `-log_loss`, поэтому больше —
лучше. Gate требует непустые train/test и нулевое пересечение `impression_id`.

## 3. Подготовка и критерий завершения

### 3.1 Held-out wCTR

Подзадачи:

- [x] Обучить сегментную оценку только на train → benchmark JSON.
- [x] Посчитать test log loss и wCTR → §4.1, таблица A.
- [x] Проверить train/test disjointness → gate output.
- [x] Передать score и график в ResearchOS Monitor → `evo-live.md` и `assets/evo-wctr.svg`.

## 4. Результаты

### 4.1 Таблица A. Held-out test

| Split | Rows | Observed wCTR | Predicted wCTR | Log loss | Evo score |
|------|------:|--------------:|---------------:|---------:|----------:|
| test | 4 | 0.105 | 0.110682 | 0.329415 | -0.329415 |

Gate: `train=6`, `test=4`, `overlap=0`; `GATE_CHECK_PASSED exp_0001`.

График: [`assets/evo-wctr.svg`](assets/evo-wctr.svg). Полный live-поток:
[`evo-live.md`](evo-live.md).

### 4.2 Выводы

Из таблицы A видно, что на четырёх held-out строках прогноз близок к
наблюдаемому wCTR: 0.110682 против 0.105. Evo check завершился успешно со
score `-0.329415`. Это подтверждает корректность smoke-пайплайна и отсутствие
leakage в fixture, но не доказывает качество модели на реальной bicycle-выгрузке.

## 5. Ограничения и заявка в базу знаний

- Fixture синтетический и малый; статистическая устойчивость не проверялась.
- Нет сравнения с production baseline и нескольких seed.
- Результат подтверждает интеграцию Evo → ResearchOS, а не бизнес-эффект.

Предлагаемый verdict для `c-wctr-prediction`: **open**. Методический инсайт:
ResearchOS Monitor может принимать гипотезы, score, gate-проверки и графики из
headless Evo, а финальный научный verdict остаётся за report review.
