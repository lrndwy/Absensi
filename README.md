# Absensi

## Run

```bash
docker build -t absensi-app .
```

```bash
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/media:/app/media \
  -v $(pwd)/static:/app/static \
  --name absensi-container \
  absensi-app
```
