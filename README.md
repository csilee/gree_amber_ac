# Gree AC egyedi komponens a Home Assistant-hoz
Felelősség kizárása
Mivel lusta vagyok, ez a README.md főként ChatGPT segítségével készült.
Ez az integráció lényegében az eredeti, hivatalos Gree integráció módosított változata, amely letiltja a légkondicionáló egység hangos visszajelző sípolásait, köszönhetően a greeclimate könyvtár egy javított verziójának, amelyet @namezys készített.

Jellemzők
Közvetlenül irányíthatod Gree légkondicionálóidat a Home Assistantból.
Élvezd a csendesebb működést a sípolások kikapcsolásával.
Egyszerű telepítés a HACS segítségével.

Különbségek a hivatalos integrációhoz képest
Ez a saját integráció funkcióiban alapvetően megegyezik a Home Assistant által biztosított hivatalos Gree integrációval. Azonban tartalmaz egy javított greeclimate könyvtárat, amely letiltja az egység sípolásait, így nyugodtabb környezetet biztosít.

Telepítési útmutató
A Gree AC egyedi komponens könnyen telepíthető a Home Assistant Community Store (HACS) segítségével:

Előfeltételek
Mielőtt elkezdenéd, győződj meg róla, hogy:
A Home Assistant telepítve és fut.
A HACS (Home Assistant Community Store) telepítve van.

Telepítési lépések
Nyisd meg a HACS-t a Home Assistantban:

Navigálj a HACS menüponthoz a Home Assistant irányítópultján.

Add hozzá az egyedi tárolót:

Kattints az "Integrációk" fülre.

Kattints a jobb felső sarokban lévő három pontra, majd válaszd a "Custom Repositories" (Egyedi tárolók) menüpontot.

A "Repository" mezőbe írd be a következő URL-t: https://github.com/ov1d1u/gree_ac.

A "Category" legördülő menüből válaszd az "Integration" kategóriát.

Kattints az "Add" (Hozzáadás) gombra.

Telepítsd az integrációt:

A HACS integrációk keresőjében keresd meg a "Gree AC" kifejezést.

Kattints a találatok között a "Gree AC"-re.

Kattints a "Install" (Telepítés) gombra.

Indítsd újra a Home Assistantot:

A telepítés után indítsd újra a Home Assistantot, hogy betöltse az új egyedi komponenst.

Konfiguráld az integrációt:

Az újraindítás után menj a "Configuration" > "Devices & Services" menüpontra.

Kattints az "Add Integration" (Integráció hozzáadása) gombra, majd keresd meg a "Gree AC"-t.

Kövesd a konfigurációs lépéseket, hogy beállítsd a Gree légkondicionálóidat.

Köszönetnyilvánítás
Ez az egyedi komponens tartalmazza a greeclimate könyvtár javított verzióját, amelyet @namezys készített, és amely letiltja a légkondicionáló sípolásait.

Az eredeti Gree integrációnak a Home Assistant számára.

## Support

For any issues or feature requests, please visit the [GitHub Issues page](https://github.com/ov1d1u/gree_ac/issues) for this repository.
