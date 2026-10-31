# Deploy on Oracle Cloud (Always Free)

Runs the whole of Vayu (API, PWA, background alerts, morning brief, database)
24x7 on one free VM, with HTTPS and no domain purchase.

Time needed: about 30 minutes, most of it waiting.

## 1. Create the account

1. Sign up at oracle.com/cloud/free. Pick the home region closest to you
   (India South, Hyderabad, or India West, Mumbai). The home region cannot be
   changed later, and free ARM capacity is per region.
2. A card is used only to verify identity. Always Free resources are not billed.

## 2. Create the VM

Console > Compute > Instances > Create instance.

| Setting | Value |
|---|---|
| Name | `vayu` |
| Image | Canonical Ubuntu 24.04 |
| Shape | Ampere, `VM.Standard.A1.Flex`, 2 OCPU, 12 GB memory |
| Networking | Create new VCN and public subnet, assign a public IPv4 address |
| SSH keys | Generate a key pair and **download the private key** |
| Boot volume | default (50 GB) |

**Easiest path, no SSH:** before clicking Create, open *Show advanced options >
Management > Initialization script*, choose *Paste cloud-init script* and paste
the contents of [`deploy/oracle/cloud-init.sh`](../deploy/oracle/cloud-init.sh).
The VM installs Vayu by itself on first boot (about 10 minutes). Then do step 3
and open `https://<public-ip-with-dashes>.sslip.io`, for example
`https://152-67-1-23.sslip.io` for IP `152.67.1.23`. Skip step 4.

If you see "Out of capacity", try again later or pick another availability
domain; free ARM capacity frees up through the day.

## 3. Open ports 80 and 443

Instance page > Primary VNIC > Subnet > Security Lists > Default Security
List > Add Ingress Rules. Add two rules:

| Source CIDR | IP protocol | Destination port |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

(The setup script opens the same ports in the VM's own firewall.)

## 4. Connect and install

From Windows PowerShell, in the folder where the key was downloaded:

```powershell
ssh -i .\ssh-key-XXXX.key ubuntu@<PUBLIC_IP>
```

If Windows complains that the key permissions are too open, run once:

```powershell
icacls .\ssh-key-XXXX.key /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

On the VM:

```bash
curl -fsSL https://raw.githubusercontent.com/PrachiYadav-16/vayu-aqi/main/deploy/oracle/setup.sh | bash
```

The script installs Docker, opens the firewall, clones the repository,
writes `backend/.env` with a fresh JWT secret, builds the image and starts
the app behind Caddy. At the end it prints the address, which looks like
`https://152-67-1-23.sslip.io`. sslip.io turns the IP into a hostname, so
Let's Encrypt can issue a real certificate with no DNS setup.

If the repository is private, clone it yourself first with a personal
access token, then run `bash ~/vayu-aqi/deploy/oracle/setup.sh`.

## 5. After install

| Task | Command (on the VM) |
|---|---|
| Live logs | `cd ~/vayu-aqi/deploy/oracle && sudo docker compose logs -f app` |
| Restart | `cd ~/vayu-aqi/deploy/oracle && sudo docker compose restart` |
| Update to latest GitHub code | `bash ~/vayu-aqi/deploy/oracle/update.sh` |
| Backup database | `bash ~/vayu-aqi/deploy/oracle/backup.sh` |
| Daily backup at 3 am | `crontab -e`, add `0 3 * * * bash ~/vayu-aqi/deploy/oracle/backup.sh` |
| Add API keys | edit `~/vayu-aqi/backend/.env`, then restart |
| Turn off demo account | set `VAYU_SEED_DEMO=false` in `deploy/oracle/.env`, then `update.sh` |

## 6. Optional: live data and push

* Live air data: put `VAYU_OPENAQ_API_KEY` or `VAYU_WAQI_TOKEN` (and
  `VAYU_OPENWEATHER_API_KEY`) in `backend/.env`, restart. See
  [deployment.md](deployment.md#moving-from-simulated-to-live-data).
* Push notifications: copy the Firebase service-account JSON to
  `~/vayu-aqi/secrets/firebase.json`, set
  `VAYU_FIREBASE_CREDENTIALS_FILE=/secrets/firebase.json` in `backend/.env`,
  put the `VITE_FIREBASE_*` values in `deploy/oracle/.env`, then run
  `update.sh` (the web values are built into the app).

## Things to know

* Oracle may reclaim Always Free VMs that stay almost idle for a week.
  Vayu's scheduler keeps some load going, but the safe fix is to upgrade the
  account to Pay As You Go: Always Free resources stay free and the VM is no
  longer reclaimed. Set a budget alert of 1 rupee to be sure.
* Keep the downloaded SSH key safe; it is the only way into the VM.
* The app runs one web worker on purpose, so the background jobs never run twice.
