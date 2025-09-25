# PersistentSandboxFusion – Stateful, Multi-Language Sandbox

This fork adds two key capabilities on top of the original
**SandboxFusion**:

1. **Persistent sessions** – files you `fetch` in one call are cached and
   automatically restored in subsequent calls.
2. **Runtime switching** – the same `session_id` can hop between
   languages (e.g. Python → Bash) while keeping its file cache.

Additionally we ship a convenience runtime **`pybash`**: the full Python
image that also runs Bash scripts, giving you `pip`, scientific libs and
shell tools in one place.

---

## 1 · Quick start

```bash
# clone & install (extras for redis persistence)
python -m pip install -e .[redis]

# optional: run redis for production-grade persistence
docker run -d --name redis -p 6379:6379 redis:7
export REDIS_URL=redis://localhost:6379/0

# launch API (multi-language version)
cd PersistentSandboxFusionMultiLang
uvicorn sandbox.server.server:app --reload --port 8080
```

---

## 2 · Single-language session

```bash
# create Python session
sid=$(curl -sX POST localhost:8080/create_session \
          -H 'Content-Type: application/json' \
          -d '{"language":"python"}' | jq -r .session_id)

# write a file & export it
curl -X POST localhost:8080/execute_session \
     -H 'Content-Type: application/json' \
     -d '{"session_id":"'$sid'",\
          "code":"with open(\"note.txt\", \"w\") as f: f.write(\"hello\")",\
          "fetch_files":["note.txt"]}'

# read the file in a later call (still Python)
curl -X POST localhost:8080/execute_session \
     -H 'Content-Type: application/json' \
     -d '{"session_id":"'$sid'",\
          "code":"print(open(\"note.txt\").read())"}'
```

---

## 3 · Mixing languages in one session

```bash
# create session in Python (could start with bash instead)
sid=$(curl -sX POST localhost:8080/create_session \
          -H 'Content-Type: application/json' \
          -d '{"language":"python"}' | jq -r .session_id)

# Python writes file and exports it
curl -X POST localhost:8080/execute_session \
     -H 'Content-Type: application/json' \
     -d '{"session_id":"'$sid'",\
          "code":"with open(\"hello.txt\", \"w\") as f: f.write(\"hi\")",\
          "fetch_files":["hello.txt"]}'

# same session switches to bash and reads the file
curl -X POST localhost:8080/execute_session \
     -H 'Content-Type: application/json' \
     -d '{"session_id":"'$sid'",\
          "language":"bash",\
          "code":"cat hello.txt"}'
```

The server kills the Python container, starts a Bash container, copies
`hello.txt` in, executes the script, then updates the cache again.

---

## 4 · `pybash` – all-in-one runtime

Need `pip` **and** quick shell scripting?  Create the session with
`"language":"pybash"`.  Behind the scenes we reuse the Python image, so
you get:

* Full Python + `pip`
* `/bin/bash`, `coreutils`, build tools

Example:

```bash
sid=$(curl -sX POST localhost:8080/create_session \
          -H 'Content-Type: application/json' \
          -d '{"language":"pybash"}' | jq -r .session_id)

# use bash and python in one snippet
curl -X POST localhost:8080/execute_session \
     -H 'Content-Type: application/json' \
     -d '{"session_id":"'$sid'",\
          "code":"echo 1 2 3 | awk \"{print $1+$2+$3}\" && python3 -c \"print(2**8)\""}'
```

---

## 5 · Endpoint reference (new/changed)

| Endpoint                  | Purpose                                      |
|---------------------------|----------------------------------------------|
| `POST /create_session`    | `{language:str, ttl:int}` → `session_id`      |
| `POST /execute_session`   | Run code using cached files; optional `language` override |

All other original SandboxFusion endpoints remain unchanged.

---

## 6 · Tips & gotchas

* `fetch_files` **must** list every file you want to persist.
* Switching languages resets RAM state (variables, imports).
* Keep one active container per session; excessive flips may incur cold-start latency.

Enjoy hacking! 🚀

