# Troubleshooting

Every entry here is a failure we actually hit while building this, with the fix
that worked. Most of them are environment problems rather than code problems,
which is exactly why they are worth writing down.

---

## The app says "Failed to fetch" or "Network error while scanning"

The app cannot reach the backend. Which address is correct depends entirely on
where the app is running:

| Running on | `EXPO_PUBLIC_API_URL` |
|---|---|
| Web browser on the same machine | `http://127.0.0.1:8000` |
| Android emulator | `http://10.0.2.2:8000` (the emulator's alias for the host) |
| iOS simulator | `http://127.0.0.1:8000` |
| Physical phone over Wi-Fi | `http://<your-machine-LAN-IP>:8000` |

A physical phone can never reach `127.0.0.1` — that address means the phone
itself. Find your LAN IP with `ipconfig` (Windows) or `ifconfig | grep inet`
(macOS/Linux), put it in `app/.env`, and start the backend bound to all
interfaces:

```bash
python manage.py runserver 0.0.0.0:8000
```

Both devices must be on the same network, and the host firewall must allow
inbound connections on port 8000.

If the browser console shows a CORS error rather than a connection failure, add
the Expo dev server's origin to `CORS_ALLOWED_ORIGINS` in `backend/.env`. Expo
picks a new port when 8081 is taken, so the origin may not be the one you
expect — read the port off the Expo startup banner.

---

## Every spine comes back unreadable, or the scan returns nothing

Run the health check before assuming the code is wrong:

```bash
cd backend
python manage.py check_vlm
```

It makes one small call and names the exact failure. The likely causes:

| What it prints | Meaning | Fix |
|---|---|---|
| `key: MISSING` | No key loaded for the configured provider | Set the key in `backend/.env` and restart the server |
| `vlm_auth_failed` | The provider rejected the key | Check for a typo, a trailing space, or a revoked key |
| `vlm_model_unavailable` | The model name no longer exists | `python manage.py check_vlm --list-models`, then set `GEMINI_MODEL` |
| `vlm_rate_limited` | Too many requests | Wait, or lower `VLM_CONCURRENCY` |
| `vlm_unreadable_response` | The model replied, but not with the JSON we asked for | Usually transient; persistent cases mean the model is a poor fit for the prompt |

**Model names expire.** This project originally defaulted to
`gemini-2.0-flash`, which Google retired; every call started returning HTTP 404
and, before the error handling was improved, that was indistinguishable from a
bad key. If the project has been sitting for a few months, this is the first
thing to check.

---

## Editing `.env` seems to have no effect

Django reads `.env` once at startup. Restart `runserver`. The same applies to
`app/.env`: Expo inlines `EXPO_PUBLIC_*` variables at bundle time, so restart
`npx expo start` (and clear the cache with `npx expo start -c` if it persists).

---

## `pip install` is downloading gigabytes

You are installing `requirements-detector.txt`, which pulls `ultralytics` and
therefore torch. If you do not need the YOLO detector:

```bash
pip install -r requirements.txt          # core only
```

The detector falls back to OpenCV, which is a supported path — see the
detector comparison in the README. Set `DETECTOR_BACKEND=opencv` to skip the
YOLO attempt entirely and save the load time.

---

## `load_catalog` says it cannot find `catalog.csv`

Run it from the `backend/` directory. The command resolves the CSV relative to
the Django `BASE_DIR`, not the current working directory.

---

## Expo will not start: port already in use

Metro leaves processes behind when a terminal is closed without stopping it.
Either accept the new port Expo offers and update `CORS_ALLOWED_ORIGINS` to
match, or kill the stale process:

```powershell
netstat -ano | findstr :8081      # find the PID
taskkill /PID <pid> /F
```

---

## A scan takes 15+ seconds

Stage 2 calls the provider once per crop. If `VLM_CONCURRENCY=1`, those calls
run one after another and ten crops cost ten round trips. The default is `5`.
Raise it for speed, lower it if the provider starts rate limiting you.

Check the split in the response `metrics`: `stage1_ms` is local detection,
`stage2_ms` is the hosted model. If `stage1_ms` is the large one, YOLO is
loading its weights — the first inference in a process includes warm-up.
