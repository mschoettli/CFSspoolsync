# K2 SSH Troubleshooting (CFS Live Data)

This guide explains why `/api/cfs/live` can return:

```json
{"reachable":false,"slots":{"1":null,"2":null,"3":null,"4":null}}
```

and how to fix it step by step.

## Typical Symptoms

- UI shows no CFS live data.
- API returns:
  - `/api/printer/status` with `reachable: true` (Moonraker works),
  - but `/api/cfs/live` with `reachable: false`.
- Logs show SSH authentication errors:
  - `Authentication failed`
  - or Paramiko key-algorithm issues.

## Architecture Reminder

- Moonraker access (`/api/printer/status`) is HTTP-based.
- CFS live access (`/api/cfs/live`) is SSH-based and reads `CFS_JSON_PATH`.
- Therefore Moonraker can be healthy while CFS live still fails.

## Root Causes

1. Wrong key file mounted into container.
2. Wrong env mapping (`K2_SSH_KEY_HOST` vs `K2_SSH_KEY`).
3. Host key mismatch in `known_hosts` after firmware/host-key changes.
4. Public key not installed where Dropbear reads it.
5. Password login works, but key-only login is still not working.

## Required Environment Variables

Use these values in your stack `.env`:

```env
K2_HOST=192.168.1.100 -> your ip
K2_SSH_USER=root
K2_SSH_KEY_HOST=/root/.ssh/id_k2
K2_SSH_KEY=/run/secrets/id_k2
```

Compose mount must map host key file to container key path:

```yaml
volumes:
  - ./data:/app/data
  - ${K2_SSH_KEY_HOST}:${K2_SSH_KEY}:ro
```

## Step 1: Verify Mount and Runtime Config

On Docker host:

```bash
docker exec cfsspoolsync printenv K2_HOST K2_SSH_USER K2_SSH_KEY
docker inspect cfsspoolsync --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
docker exec cfsspoolsync ls -l /run/secrets/id_k2
```

Expected:

- `K2_SSH_KEY=/run/secrets/id_k2`
- mount like `/root/.ssh/id_k2 -> /run/secrets/id_k2`
- file exists, not a directory.

## Step 2: Confirm Host and Container Use the Same Key

```bash
ssh-keygen -lf /root/.ssh/id_k2
docker exec cfsspoolsync ssh-keygen -lf /run/secrets/id_k2
```

Fingerprints must match exactly.

## Step 3: Fix Known Host Change Warnings

If SSH reports `REMOTE HOST IDENTIFICATION HAS CHANGED`:

```bash
ssh-keygen -f /root/.ssh/known_hosts -R 192.168.1.100 -> your ip
ssh root@192.168.178.192
```

Accept new fingerprint once, then reconnect.

## Step 4: Install Public Key on K2 (Dropbear)

Generate public key from the exact private key used by Docker host:

```bash
ssh-keygen -y -f /root/.ssh/id_k2 > /tmp/id_k2.pub
cat /tmp/id_k2.pub
```

On K2, install it in both common locations:

```sh
mkdir -p /root/.ssh
chmod 700 /root/.ssh
cat /tmp/id_k2.pub > /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys

mkdir -p /etc/dropbear
cat /tmp/id_k2.pub > /etc/dropbear/authorized_keys
chmod 600 /etc/dropbear/authorized_keys

/etc/init.d/dropbear restart
```

## Step 5: Test Key-Only Login (No Password Fallback)

This is critical. If this fails, app will also fail.

```bash
ssh -o BatchMode=yes -o PreferredAuthentications=publickey -i /root/.ssh/id_k2 root@192.168.178.192 "echo KEY_OK"
```

Expected output: `KEY_OK`.

## Step 6: Restart App and Validate API

```bash
docker restart cfsspoolsync
curl -s http://127.0.0.1:8080/api/cfs/live; echo
```

Expected: `reachable: true` and slot payloads.

## If It Still Fails

Collect these outputs:

```bash
docker logs --tail=120 cfsspoolsync
docker exec cfsspoolsync python -c "from app.services.ssh_client import _get_client; c=_get_client(); print('APP_SSH_OK'); c.close()"
ssh -o BatchMode=yes -o PreferredAuthentications=publickey -i /root/.ssh/id_k2 root@192.168.178.192 "echo KEY_OK"
cat /etc/config/dropbear
ls -la /root/.ssh
cat /root/.ssh/authorized_keys
```

Then verify:

- key fingerprints match host/container,
- Dropbear has public key auth enabled,
- key exists in the path Dropbear actually uses.

## Windows Notes

- PowerShell `curl` is often `Invoke-WebRequest`; use `curl.exe` for raw curl behavior.
- Linux paths like `/root/.ssh/...` are not valid on Windows host filesystem.
- For copying keys from Windows to Linux host:

```powershell
scp "$env:USERPROFILE\.ssh\id_k2" root@192.168.178.201:/root/.ssh/id_k2
```

