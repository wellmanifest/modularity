# ai-claude.md — ticket-005

## Rozumienie intencji

To repozytorium definiuje regułę `contractOwnership=single-exporter`: jeden pack
jest eksporterem kontraktu, reszta konsumuje go jako fasada, a bramka dryfu ma
padać przed merge'em. Reguła jest dziś opisana wyłącznie dla arkuszy
komercyjnych (`subactor/offer`, `subactor/brand`, `policy-dsl`).

Tymczasem wewnątrz wellmanifest istnieje drugi, nieopisany przypadek tej samej
klasy: silnik lifecycle, skopiowany do sześciu repozytoriów bez wskazania
eksportera i bez bramki parzystości.

## Ustalenie faktów

Silnik ma jednoznacznego właściciela. `wellmanifest/lifecycle` zawiera
`src/lifecycle.py` wraz z `tests/test_lifecycle.py`, a jego README stwierdza, że
rdzeń jest celowo niezależny od domeny.

Sześć plików `standard/lifecycle.py` to jego kopie. Wszystkie siedem —
oryginał i sześć kopii — jest **bajt-w-bajt identycznych**:

    $ md5sum lifecycle/src/lifecycle.py */standard/lifecycle.py | awk '{print $1}' | sort -u | wc -l
    1

    740 linii w każdym pliku
    konsumenci: git-lifecycle, legal-lifecycle, product-lifecycle,
                saas-lifecycle, ticket-lifecycle, twin-lifecycle
    każdy używa go przez własny standard/conformance.py

## Dlaczego to ticket typu SERVICE, a nie BUG

Dryf jeszcze nie wystąpił. Kopie są zgodne z oryginałem co do bajtu, więc nie ma
dziś defektu funkcjonalnego — jest niezabezpieczone ryzyko. Zgodnie z regułą
W-CLASS-006 to praca utrzymaniowa, nie defekt.

Ryzyko jest jednak realne i asymetryczne: 740 linii × 6 kopii, edytowanych
niezależnie przez różne sesje, bez żadnego mechanizmu, który zauważyłby
rozjechanie. Pierwsza rozbieżność będzie cicha.

## Zakres

Jeden plik: `README.md`. Dopisać do sekcji o kontraktach single-exporter drugi
przypadek — silnik lifecycle — w tej samej formie tabeli, której repozytorium
już używa:

| Contract | Exporter (HOME) | Consumers (ADOPT / facade) |
| --- | --- | --- |
| Lifecycle engine (`lifecycle.py`) | `wellmanifest/lifecycle` (`src/lifecycle.py`) | sześć packów `*-lifecycle` jako `standard/lifecycle.py` |

Poza zakresem: przenoszenie lub usuwanie kodu, dodawanie workflow parzystości do
sześciu konsumentów, jakakolwiek zmiana samego silnika. Bramka parzystości
należy do konsumentów i jest osobną pracą — ten ticket zapisuje kontrakt, na
który tamta praca będzie się powoływać.

## Kryteria Odbioru

- **AC-01** README nazywa `wellmanifest/lifecycle` eksporterem, a sześć
  repozytoriów fasadami.
- **AC-02** Oryginał i sześć kopii nadal mają jeden wspólny digest, więc
  kontrakt zapisuje stan faktyczny, a nie postuluje migrację.
- **AC-03** Bramka governance przypisuje diff do ticket-005.

## Praca następcza

Test parzystości w każdym z sześciu konsumentów, porównujący ich
`standard/lifecycle.py` z przypiętą wersją eksportera. Do rozstrzygnięcia
procedurą z `wellmanifest/ssot`: czy kopie mają pozostać vendorowane z
parzystością, czy zostać zastąpione zależnością.
