# SenseWord — Ücretsiz Deploy Rehberi

Bu uygulama bir **FastAPI** servisidir. Kelime kataloğu her açılışta
`app/data/vocabulary_full.json` dosyasından otomatik olarak yüklendiği için
(SQLite), boş bir sunucuda bile veriyle ayağa kalkar.

> **Not (veritabanı kalıcılığı):** Ücretsiz planlarda disk genellikle geçicidir;
> her yeniden dağıtımda SQLite sıfırlanır ama katalog tekrar otomatik yüklenir.
> Kullanıcı hesaplarını/ilerlemeyi kalıcı tutmak istersen `DATABASE_URL` ortam
> değişkenini yönetilen bir Postgres adresine ayarla:
> `postgresql+psycopg://kullanici:sifre@host:5432/senseword`

Repo zaten şu dosyalarla deploy'a hazır: `Dockerfile`, `render.yaml`,
`Procfile`, `runtime.txt`, `.dockerignore`.

---

## 1) Render (önerilen — GitHub'dan gerçekten ücretsiz, tek tık)

**Tek tık (Blueprint):**

https://render.com/deploy?repo=https://github.com/sonmezbaris/senseword

1. GitHub ile giriş yap → repoya erişim ver.
2. Render `render.yaml`'ı otomatik okur (Free plan, `/health` health check).
3. **Apply** / **Create** de. Birkaç dakikada `https://senseword-xxxx.onrender.com`
   adresinde yayında olur.

> Free plan ~15 dk hareketsizlikte uykuya geçer; ilk istek birkaç saniye
> bekletebilir (cold start). Demo için yeterlidir.

Manuel yol: Render Dashboard → **New +** → **Blueprint** → repoyu seç.

---

## 2) Hugging Face Spaces (tamamen ücretsiz, uyumaz)

1. https://huggingface.co/new-space → **Docker** SDK → **Blank** seç.
2. Space'i GitHub repona bağla veya bu reponun dosyalarını Space'e it.
3. Space ayarlarında (README metadata) portu 8000 yap:

   ```yaml
   ---
   title: SenseWord
   sdk: docker
   app_port: 8000
   ---
   ```

4. Space otomatik build eder; `https://huggingface.co/spaces/<kullanıcı>/senseword`
   adresinde yayında olur.

---

## 3) Koyeb (ücretsiz tier, GitHub'dan)

**Tek tık:**

https://app.koyeb.com/deploy?type=git&repository=github.com/sonmezbaris/senseword&branch=main&ports=8000;http;/&run_command=uvicorn%20app.main:app%20--host%200.0.0.0%20--port%208000

Veya Koyeb Dashboard → **Create Web Service** → **GitHub** → repoyu seç →
Port `8000`, run command `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

---

## 4) Railway (deneme kredisiyle ücretsiz)

1. https://railway.app/new → **Deploy from GitHub repo** → repoyu seç.
2. Railway `Dockerfile`'ı otomatik kullanır; `$PORT`'u kendisi enjekte eder.
3. Settings → **Generate Domain** ile herkese açık URL al.

---

## Yerelde Docker ile test

```bash
docker build -t senseword .
docker run -p 8000:8000 senseword
# http://localhost:8000
```

## Hangi platform?

| Platform | Ücretsiz | Uyur mu? | GitHub tek-tık | Not |
|---|---|---|---|---|
| **Render** | ✓ | ~15 dk sonra uyur | ✓ (`render.yaml`) | En kolay başlangıç |
| **HF Spaces** | ✓ | Hayır | Docker | Demo için ideal |
| **Koyeb** | ✓ (sınırlı) | Hayır | ✓ | İyi alternatif |
| **Railway** | Deneme kredisi | Hayır | ✓ | Kredi bitince ücretli |
