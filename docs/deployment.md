# Deployment

**Recommended free option:** a full 24x7 install on Oracle Cloud Always Free with one command.
See [deploy-oracle.md](deploy-oracle.md).

## Option 1: Docker on any VM

```bash
git clone https://github.com/PrachiYadav-16/vayu-aqi.git
cd vayu-aqi
cp backend/.env.example backend/.env      # set VAYU_JWT_SECRET and any API keys
docker compose up -d --build
```

The image builds the PWA, serves it from FastAPI on port 8000, keeps the SQLite database in the
`vayu-data` volume and seeds stations on start. Put Nginx or Caddy in front for HTTPS; geolocation, service
workers and push all require HTTPS outside localhost.

To use InfluxDB for readings:

```bash
docker compose --profile influx up -d
# in backend/.env
VAYU_TIMESERIES_BACKEND=influx
VAYU_INFLUX_URL=http://influxdb:8086
VAYU_INFLUX_TOKEN=change-me-token
```

## Option 2: Render / Railway

* Create a web service from the repository using the Dockerfile.
* Add a persistent disk mounted at `/data`.
* Set environment variables from `backend/.env.example`, at least `VAYU_JWT_SECRET`.
* Health check path: `/api/health`.

## Option 3: Frontend on Vercel, API elsewhere

* Deploy `backend/` as above.
* In Vercel, set the root directory to `frontend`, build command `npm run build`, output `dist`.
* Add a rewrite so `/api/*` goes to the API host (`vercel.json`):

```json
{ "rewrites": [{ "source": "/api/:path*", "destination": "https://YOUR-API-HOST/api/:path*" },
               { "source": "/(.*)", "destination": "/index.html" }] }
```

* Set `VAYU_CORS_ORIGINS` on the API to the Vercel domain.

## Getting the API keys

| Key | Where | Free tier |
|---|---|---|
| `VAYU_OPENAQ_API_KEY` | explore.openaq.org, account settings | Yes |
| `VAYU_WAQI_TOKEN` | aqicn.org/data-platform/token | Yes |
| `VAYU_OPENWEATHER_API_KEY` | openweathermap.org/api | Yes, 1,000 calls/day |
| `VAYU_TOMTOM_API_KEY` | developer.tomtom.com | Yes, 2,500 calls/day |
| `VAYU_GOOGLE_MAPS_API_KEY` | Google Cloud console, enable Directions and Geocoding | Monthly credit |

With 31 stations and a 30-minute ingest, OpenWeatherMap uses about 600 calls a day because calls are shared
per 10 km cell. TomTom uses about 1,500; raise `VAYU_INGEST_INTERVAL_MINUTES` to 60 if you are close to the limit.

## Push notifications (Firebase)

1. Create a Firebase project and add a Web app.
2. Project settings > Service accounts > Generate new private key. Save the JSON on the server and set
   `VAYU_FIREBASE_CREDENTIALS_FILE` to its path. Never commit this file.
3. Project settings > General: copy the web config into `frontend/.env` (`VITE_FIREBASE_*`).
4. Project settings > Cloud Messaging > Web Push certificates: generate a key pair and set
   `VITE_FIREBASE_VAPID_KEY`.
5. Rebuild the frontend. In the app, Settings > Notifications > Allow on this device.

## Moving from simulated to live data

1. Add `VAYU_OPENAQ_API_KEY` or `VAYU_WAQI_TOKEN` and restart. `/api/air/meta` will report `"data_mode": "live"`.
2. Clear simulated readings so they do not mix with live ones: delete `vayu.db` (or the `readings` table) and
   run `python -m scripts.seed --no-demo`.
3. After at least 60 days of live readings, retrain:
   `python -m training.train_forecaster --source db --days 365 --report`.
   Until then the simulated-data model keeps serving.
