# dax-hoc

Short-term earnings news trader for DAX/MDAX/SDAX companies. See `CLAUDE.md` for full architecture and module reference.

## Scheduling

### Where the schedule is defined

The T0 pipeline is registered as a macOS launchd agent:

```
~/Library/LaunchAgents/com.dax-hoc.t0-pipeline.plist
```

To load/unload it:

```bash
launchctl load   ~/Library/LaunchAgents/com.dax-hoc.t0-pipeline.plist
launchctl unload ~/Library/LaunchAgents/com.dax-hoc.t0-pipeline.plist
```

### When it runs

Monday–Friday at **07:00 local time** (`StartCalendarInterval` with `Weekday` 1–5, `Hour` 7).

### Logs

| Stream | Path |
|--------|------|
| stdout | `/tmp/dax-hoc-t0-pipeline.out.log` |
| stderr | `/tmp/dax-hoc-t0-pipeline.err.log` |

Tail both at once:

```bash
tail -f /tmp/dax-hoc-t0-pipeline.out.log /tmp/dax-hoc-t0-pipeline.err.log
```

> **Note:** `/tmp` is cleared on reboot. Logs do not persist across restarts.
