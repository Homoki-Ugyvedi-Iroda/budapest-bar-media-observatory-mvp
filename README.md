# AI Média Obszervatórium – Budapest Bar Association

## Hogyan használd? — Normál heti folyamat

### 1. lépés: Parser futtatása
1. Nyisd meg a webalkalmazást böngészőben, és jelentkezz be
2. Kattints a **Run Parser** gombra a dashboardon
3. A parser lekéri a `sites.yaml`-ban szereplő weboldalakat, kulcsszavas szűréssel kiválasztja az AI-vonatkozású híreket, és elmenti a `parsed_[mai dátum].yaml` fájlba
4. A futás eredménye (talált tételek száma) flash üzenetben jelenik meg; a részletek a `logs/parser.log` fájlban olvashatók

### 2. lépés: Áttekintés és kijelölés
1. A dashboardon kattints a legfrissebb parse-futás dátumára
2. Az áttekintő oldalon a találatok forrás szerint csoportosítva jelennek meg; a kivonatokat a rendszer automatikusan angolra fordítja a gyors átfutáshoz
3. Minden tételnél:
   - Kattints az **Open** gombra az eredeti tartalom megtekintéséhez új ablakban
   - Pipáld be a **Download** jelölőnégyzetet, ha a teljes HTML/PDF tartalmat le szeretnéd tölteni
   - Pipáld be a **Translate** jelölőnégyzetet, ha az egész tartalmat angolra kell fordítani a hírlevélhez
4. Kattints a lap alján a **Save** gombra — a rendszer elmenti a `tosummarize_[dátum].yaml` fájlt, elvégzi a kötegelt letöltést és fordítást, és az oldalon maradsz
5. Ha szükséges, módosíthatod a kijelölést, és újra mentheted

### 3. lépés: Hírlevél elkészítése
1. Visszatérve a dashboardra, kattints a **Run Drafter** gombra
2. A Drafter megkeresi a legfrissebb, még fel nem dolgozott `tosummarize_*.yaml` fájlt, és az `editorial_instructions.md` alapján magyar nyelvű hírlevelet készít
3. A kész hírlevél HTML formátumban elérhető: `content_[dátum]/newsletter/`
4. Töltsd le FTP-n, ellenőrizd, majd küldd el

---

## Célkitűzés

Az eszköz célja, hogy a Budapesti Ügyvédi Kamara számára automatikusan figyelje a közép-európai nemzeti és regionális ügyvédi kamarák weboldalain megjelenő, mesterséges intelligenciával kapcsolatos híreket, és azokat heti magyar nyelvű hírlevél formájában eljuttassa a szerkesztőhöz.

---

## Működési mód

A rendszer három fő komponensből áll, amelyek egyetlen Flask webalkalmazásban futnak a PythonAnywhere platformon:

### 1. Parser (automatikus, heti futás)
- Lekéri a `sites.yaml`-ban megadott ügyvédi kamarai weboldalak hírlistáit
- A találatokat kulcsszavas szűréssel (magyar, angol és helyi nyelvű AI-kulcsszavak alapján) szűkíti
- Az eredményeket `parsed_[yyyymmdd].yaml` fájlba menti
- Duplikátumokat nem rögzít: az egyszer már látott URL-eket kihagyja

### 2. Áttekintő eszköz (Flask webes felület, emberi felügyelet)
- A szerkesztő megnyitja a kívánt `parsed_[yyyymmdd].yaml` fájlt
- Az összes cím és kivonat automatikusan lefordítódik angolra (Claude Sonnet segítségével) az áttekinthetőség érdekében
- Minden találatnál lehetőség van:
  - az eredeti tartalom megnyitására új ablakban
  - a tartalom letöltésére (`content_[yyyymmdd]/downloaded/`)
  - az eredeti HTML tartalom angolra fordítására (`content_[yyyymmdd]/translations/`)
- A kijelölt tételek mentése: `tosummarize_[yyyymmdd].yaml`

### 3. Hírlevél-szerkesztő (Drafter)
- Automatikusan megkeresi a legutóbbi, még fel nem dolgozott `tosummarize_*.yaml` fájlt
- Az `editorial_instructions.md` irányelvei alapján kamaránként csoportosítva, magyar nyelvű összefoglalókkal hírlevelet készít
- A kész hírlevelet HTML formátumban menti: `content_[yyyymmdd]/newsletter/`
- A fájl FTP-n tölthető le, majd a szerkesztő ellenőrzés és küldés előtt átnézi

---

## Külső tartalmak integrálása

Nem minden fontos tartalom érhető el automatikus scraping-gel. Az alábbi módszerekkel manuálisan is beilleszthető tartalom a hírlevelbe.

### Nem scrape-elhető HTML-ek (pl. CCBE LinkedIn-bejegyzések, zárt oldalak)

1. Nyisd meg a tartalmat a böngészőben, és mentsd el HTML-ként (vagy másold ki a szöveget egy `.txt` fájlba)
2. A dashboardon, az **Add Manual Item** űrlapon add meg:
   - A kívánt dátumot (amelyik `tosummarize_*.yaml`-ba kerüljön)
   - A forrást (pl. CCBE)
   - A cikk címét
   - Az eredeti URL-t (a hírlevelben forrásként fog szerepelni)
3. Kattints az **Add Item** gombra — a rendszer hozzáadja a tételt a `tosummarize_[dátum].yaml`-hoz, és megmutatja a várt fordítási fájlnevet
4. Az **Upload Translation** űrlapon töltsd fel a mentett HTML vagy TXT fájlt (ugyanazon dátummal és URL-lel)
5. A Drafter automatikusan felhasználja a feltöltött fájlt a magyar összefoglaló elkészítéséhez

### PDF-ek (automatikus scraping esetén is, manuális fordítással)

**Fontos:** A parser csak PDF-hivatkozásokat gyűjt, a fájl tartalmát nem olvassa be automatikusan.

- **Letöltés:** Az áttekintő felületen a Download jelölőnégyzet kipipálásával a PDF a `content_[yyyymmdd]/downloaded/` mappába kerül. Ha automatikusan nem érhető el, kézzel is letölthető FTP-n keresztül ugyanide.
- **Fordítás:** Az automatikus fordítás PDF-fájloknál nem támogatott. A szöveg kinyeréséhez:
  1. Nyisd meg a PDF-et, és másold ki a szöveget (vagy használj külső PDF-szövegkinyerő eszközt)
  2. Fordítsd le angolra (pl. DeepL vagy Claude segítségével)
  3. Mentsd el a fordítást `.txt` fájlként, és töltsd fel az **Upload Translation** űrlapon — vagy helyezd el közvetlenül FTP-n:

  ```
  content_[yyyymmdd]/translations/[biztonságos_fájlnév]_en.txt
  ```

  Ha ez a fájl megtalálható, a Drafter automatikusan felhasználja a magyar összefoglaló elkészítéséhez.

> **Megjegyzés a fájlnevekről:** A rendszer az URL-ből képezi a fájlnevet (speciális karakterek helyett aláhúzás, max. 80 karakter). Az Add Manual Item után megjelenő flash üzenet pontosan megmutatja a várt fájlnevet.

---

## Éves költségterv

| Tétel | Számítás | Éves összeg |
|---|---|---|
| Anthropic API (Claude Sonnet) | ~1 USD/futtatás × 52 hét | ~52 USD |
| PythonAnywhere hosting | éves előfizetés | ~100 USD |
| **Összesen** | | **~152 USD/év** |

> Az API-költség becslése egy teszt alapján: 9 weboldal egyszeri feldolgozásán és öt hír fordításán alapszik, becsült érték. A tényleges költség a feldolgozott tételek számától függően változhat.

---

## Az MVP-ben még nem implementált lépések

Az alábbi funkciók tudatosan ki lettek hagyva a demonstrációs verzióból:

- **CSS selectorok kitöltése** a `sites.yaml`-ban minden egyes weboldalnál. Jelenleg az összes oldal általános, visszaesési módban fut (az összes link begyűjtése), ami sok zajt és kevés strukturált adatot eredményez. A selectorokat böngésző fejlesztői eszközzel (F12) kell egyenként beállítani.
- **JavaScript által renderelt oldalak kezelése.** Néhány weboldal (pl. az OZS, UNBR, ВАдС várhatóan) dinamikusan tölt be tartalmat, amelyet a sima HTTP-kérés nem lát. Ezeknél Playwright vagy hasonló eszköz szükséges.
- **E-mail küldés.** A Drafter jelenleg csak a hírlevelet menti fájlba; az automatikus e-mail-küldés (célszerűen csak a szerkesztőnek vagy a kamarának) még nincs megvalósítva.
- **PythonAnywhere ütemezett futtatás beállítása** a heti automatikus parseoláshoz.

---

## Javasolt fejlesztési irányok

- **További weboldalak felvétele** a `sites.yaml`-ba. Javasolt célpontok: további lengyel regionális kamarák, a litván, lett és észt ügyvédi kamarák, illetve az CCBE (Európai Ügyvédi Kamarák Tanácsa).
- **Finomított kulcsszószűrés** az első futtatások visszajelzései alapján (téves pozitív jelzések, kimaradt hírek elemzése).
- **PDF szövegkinyerés automatizálása** (pl. `pdfplumber` könyvtárral), hogy a szöveges PDF-fájlok emberi beavatkozás nélkül feldolgozhatók legyenek.
- **E-mail küldés integrálása** a Drafter modulba (pl. SMTP vagy egy e-mail API segítségével). Kamarai hírlevélkiküldővel integrálni.
- **Archív nézet:** korábbi hírlevelek és fordítások böngészése a webes felületen.
- **Többnyelvű összefoglaló opció:** az angol fordítás mellett opcionálisan az eredeti nyelven is megőrizni a szöveget.
- **FTP letöltés konfiguráció, régi állományok automatikus törlése**
- **Szerkesztői felület több felhasználóssá tétele**

---

## Technikai követelmények

- Python 3.9+
- PythonAnywhere fiók (paid plan ajánlott)
- Anthropic API kulcs
- Függőségek: `flask`, `requests`, `beautifulsoup4`, `pyyaml`, `anthropic`, `python-dotenv`

```bash
pip install flask requests beautifulsoup4 pyyaml anthropic python-dotenv
```

A szükséges környezeti változók a `.env` fájlban:

```
ANTHROPIC_API_KEY=sk-ant-...
APP_PASSWORD=...
FLASK_SECRET_KEY=...
```

---
*Developed with the assistance of [Claude Code](https://claude.ai/claude-code) (Anthropic).*