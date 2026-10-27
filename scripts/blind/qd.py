"""Run queue for scored runs (and infra-only retries).

    MODE=blind    nohup python3 qd.py > qd_blind.log 2>&1 &     # interwhen runs, queue.txt / done.txt
    MODE=baseline nohup python3 qd.py > qd_base.log 2>&1 &      # Haiku baselines, bqueue.txt / bdone.txt
    echo <task> >> queue.txt

A task needs 4 trials. Trials that died before the agent ran (docker network / container creation errors) are
infrastructure failures and are re-run; any trial that ran the agent counts as is.
"""
import os
import re
import subprocess
import time
from pathlib import Path

REPO = Path("/mnt/datadrive/t-bhatvishak/Vishak_Handbook")
HERE = Path("/mnt/datadrive/t-bhatvishak/tmp/blind")
MODE = os.environ.get("MODE", "blind")
PAR = int(os.environ.get("PAR", "2"))
Q, DONE = ("queue.txt", "done.txt") if MODE == "blind" else ("bqueue.txt", "bdone.txt")
PREFIX = "blind" if MODE == "blind" else "baseline-haiku55"
INFRA = re.compile(r"non-overlapping IPv4|failed to create network|Error response from daemon|"
                   r"Cannot connect to the Docker daemon|No such container|Docker compose command failed", re.I)
ACTED = re.compile(r"Tool:|ActionEvent|tool_call")


def clean_networks():
    """Remove leaked harbor task networks (no containers, older than 30 min)."""
    out = subprocess.run(["docker", "network", "ls", "-q", "--filter", "name=__env_default"],
                         capture_output=True, text=True).stdout.split()
    for nid in out:
        info = subprocess.run(["docker", "network", "inspect", nid, "--format",
                               "{{len .Containers}} {{.Created.Unix}}"], capture_output=True, text=True).stdout.split()
        if len(info) == 2 and info[0] == "0" and time.time() - int(info[1]) > 1800:
            subprocess.run(["docker", "network", "rm", nid], capture_output=True)


def trials(task_id: str):
    """(valid, infra_failed, in_progress) trial dirs over every job of this task."""
    valid, infra, busy = [], [], []
    for job in sorted(REPO.glob(f"jobs/{PREFIX}-*{task_id}-2*")):
        for t in job.iterdir():
            if not t.is_dir():
                continue
            exc = t / "exception.txt"
            log = t / "agent" / "run-openhands.log"
            done = (t / "verifier" / "reward.txt").exists() or (t / "result.json").exists()
            if done and log.exists() and not ACTED.search(log.read_text(errors="ignore")):
                infra.append(t)  # LLM timed out before the agent's first tool call
            elif (t / "verifier" / "reward.txt").exists():
                valid.append(t)
            elif exc.exists() and INFRA.search(exc.read_text(errors="ignore")):
                infra.append(t)
            elif exc.exists() or (t / "result.json").exists():
                valid.append(t)  # the agent ran but the trial failed otherwise: counts as an attempt
            else:
                busy.append(t)
    return valid, infra, busy


def launch(task: str, n: int, prefix: str) -> subprocess.Popen:
    env = dict(os.environ, TASKS=task, ATTEMPTS=str(n), CONCURRENCY=str(min(n, 4 if MODE == "blind" else 2)),
               JOB_PREFIX=prefix)
    if MODE == "blind":
        subprocess.run([str(HERE / "freeze.sh"), "--verify", task], check=True)
        env.update(CHECKLIST="1", MAX_DENIALS="6", MAX_STALE="2")
        cmd = ["scripts/run_interwhen.sh"]
    else:
        cmd = ["scripts/run_baseline.sh"]
    log = open(HERE / f"{MODE}_{task.rsplit('_', 1)[1]}.log", "a")
    return subprocess.Popen(cmd, cwd=REPO, env=env, stdout=log, stderr=log)


def proxy_ok() -> bool:
    r = subprocess.run(["scripts/check_model.sh", "openai/claude-haiku-5.5"], cwd=REPO, capture_output=True)
    return r.returncode == 0


def main():
    running: dict[str, subprocess.Popen] = {}
    rounds: dict[str, int] = {}
    while True:
        if not proxy_ok():
            print(time.strftime("%H:%M:%S"), "model proxy down - waiting", flush=True)
            time.sleep(120)
            continue
        queue = [l.strip() for l in (HERE / Q).read_text().splitlines() if l.strip()] if (HERE / Q).exists() else []
        done = set((HERE / DONE).read_text().split()) if (HERE / DONE).exists() else set()
        for t, p in list(running.items()):
            if p.poll() is not None:
                del running[t]
        for t in queue:
            if t in done or t in running or len(running) >= PAR:
                continue
            tid = t.rsplit("_", 1)[1]
            valid, infra, busy = trials(tid)
            if busy:
                continue  # a run started outside the queue is still going
            need = 4 - len(valid)
            if need <= 0 or rounds.get(t, 0) >= 8:
                with open(HERE / DONE, "a") as f:
                    f.write(t + "\n")
                print(time.strftime("%H:%M:%S"), "DONE" if need <= 0 else "GIVE UP", t, len(valid), "trials",
                      flush=True)
                continue
            prefix = PREFIX if not valid and not infra else f"{PREFIX}-retry"
            rounds[t] = rounds.get(t, 0) + 1
            clean_networks()
            print(time.strftime("%H:%M:%S"), "RUN", t, "attempts", need, prefix, flush=True)
            running[t] = launch(t, need, prefix)
            time.sleep(20)
        time.sleep(30)


if __name__ == "__main__":
    main()
