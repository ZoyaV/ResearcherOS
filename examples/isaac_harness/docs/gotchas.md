# Gotchas — проверенные грабли

Подтверждено на практике (RTX 5090 / IsaacLab 3.0-beta2 / Isaac Sim 6.0).

1. Общий `/tmp/Assets`. omni.client зеркалирует облачные USD в `<TMPDIR>/Assets`; на общей
   машине `/tmp/Assets` может принадлежать другому пользователю → `Could not open asset`
   и падение `No collision prim found at '/World/ground'`. Лечение:
   `export TMPDIR=$HOME/<...>/tmp_isaac` перед запуском.

2. `./isaaclab.sh --install rsl_rl` в этом форке не ставит rsl_rl (токен неизвестен).
   Ставить вручную: `uv pip install 'rsl-rl-lib==5.0.1' 'onnxscript>=0.5'`.

3. PhysX дорог на старте. Первое создание сцены с `physics=physx` ~287 с (холодное
   зеркалирование ассетов) против ~17 с у `newton_mjwarp`; «блокирующие» стек-трейсы
   omni.client при этом — предупреждения, не ошибки. В сравнениях throughput тренировки
   (`throughput_steps_s`) отделять от старта (`scene_creation_s`).

4. Один GPU → прогоны строго последовательны (так и устроен `examples/isaac_harness/bench_matrix.sh`).

5. Общий аккаунт. Перед/после правок: `git status --short && git diff --stat`; чужие
   незакоммиченные изменения не трогать. Деструктивное (rm/kill/git reset/checkout) —
   только с явного согласия владельца задачи.

6. VPN (если включён) может душить загрузки и оставлять зомби-TCP при выключении —
   после переключения VPN проверять прогресс качающих процессов.
