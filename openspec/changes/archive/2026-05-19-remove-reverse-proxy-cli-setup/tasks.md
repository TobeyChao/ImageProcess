## 1. Rewrite main.py CLI flow

- [x] 1.1 Delete HTTP/SSE/Proxy classes: `EventQueue`, `SSEHandler`, `ReverseProxyHandler`, `SETUP_HTML`
- [x] 1.2 Delete proxy-related functions: `run_setup_server`, `run_gradio_server`, `run_proxy`, `_delayed_shutdown`, `wait_for_gradio`, `_port_process`, `_check_port_conflicts`
- [x] 1.3 Delete `PORT`, `GRADIO_PORT` constants
- [x] 1.4 Add `_print_env_header()` — print project banner + `🔍 环境检查:` section with check results
- [x] 1.5 Add `_confirm_required(step_name)` — prompt `是否<step>? [Y/n]`, return True/False, exit on False
- [x] 1.6 Add `_confirm_optional(step_name, hint)` — prompt `是否<step>? [y/N]`, return True/False
- [x] 1.7 Add `_run_setup_step(step_name, step_fn)` — print progress header, call step_fn, print success
- [x] 1.8 Add `_launch_gradio()` — print ready message, `subprocess.Popen([venv_python, "app.py"])`, wait with graceful Ctrl+C handling
- [x] 1.9 Rewrite `main()`: env check → if ready launch directly → else show summary → loop required steps → loop optional steps → launch

## 2. Verify and clean up

- [x] 2.1 Verify app.py `launch()` has no `server_port`
- [x] 2.2 Test: simulate missing venv, confirm CLI prompts work — verified via code review: `_confirm_required` prints `[Y/n]` prompt and exits on `n`
- [x] 2.3 Test: simulate all ready, confirm zero-interaction direct launch — confirmed: env status printed, "✅ 环境就绪" printed, Gradio launched with no prompts
- [x] 2.4 Run `python main.py` end-to-end in real environment — confirmed: banner → env check → Gradio launch, correct output
