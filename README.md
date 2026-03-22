# AI Média Obszervatórium – Budapest Bar Association

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

## PDF-kezelés

**Fontos:** A parser csak PDF-hivatkozásokat gyűjt, a fájl tartalmát nem olvassa be automatikusan.

- **PDF letöltés:** Az áttekintő felületen a letöltés jelölőnégyzet kipipálásával a PDF a `content_[yyyymmdd]/downloaded/` mappába kerül. Ha a fájl nem érhető el automatikusan, kézzel is letölthető ugyanide.
- **PDF fordítás:** Az automatikus fordítás PDF-fájloknál nem támogatott. Ha a PDF szöveges tartalma kinyerhető (pl. copy-paste vagy külső eszközzel), a szöveget a következő névkonvencióval kell menteni:

  ```
  content_[yyyymmdd]/translations/[biztonságos_fájlnév]_en.txt
  ```

  Ha ez a fájl létezik, a Drafter automatikusan felhasználja a magyar összefoglaló elkészítéséhez, és a tartalom bekerül a hírlevelbe.

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