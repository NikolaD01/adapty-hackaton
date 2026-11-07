# Dodatak za Adapty: ponuda po tome šta ljudi rade u aplikaciji
Finalni plan. 7. novembar 2026. (Izvor istine za ceo tim; agenti ga čitaju, a kod prati `docs/contracts/`.)

## Šta pravimo
Pravimo dodatak za Adapty koji iz toga kako ljudi koriste aplikaciju predlaže kojoj grupi korisnika da prikažemo koju ponudu. Cilj je da više ljudi iz te grupe kupi pretplatu, jer im paywall jasno pokaže šta dobijaju za ono što već rade u aplikaciji.
Ne pravimo editor paywall-ova, SDK za naplatu ni analitiku. Sve to Adapty ima. Mi dodajemo ono što mu fali: znanje o tome šta se dešava u proizvodu pre kupovine.

## Zašto to fali
Adapty ume da pokaže različit paywall različitoj grupi. Grupa se pravi kao segment nad custom atributima, poljima koja aplikacija upiše na profil korisnika.
Ali Adapty te atribute ne skuplja. Aplikacija mora sama da izračuna vrednost i da je pošalje. U njihovoj agent-skill datoteci audiences to stoji kao upozorenje developerima: „A segment over an attribute nobody sets matches nobody."
I još jedna stvar, koju smo proverili: atribut pamti samo trenutnu vrednost. Nema istoriju. Ako danas upišemo 7 a za nedelju 12, Adapty zna samo 12. Zato istorija radnji mora da živi kod nas.
U demo podacima koje smo dobili to se dobro vidi. Lumen profili imaju ai_edits_first_day, već izračunat i upisan — kao da je neko problem već rešio. A niko ga nije rešio: seed skripta je pročitala broj iz datoteke i poslala ga. U pravoj aplikaciji tog polja nema, i neko mora da odluči šta se broji i da pogodi.

## Šta developer beleži
Preko našeg SDK-a developer beleži radnje koje su bitne za njegovu aplikaciju. Svaka vrsta događaja ima naziv i opis, a po potrebi developer može da označi povezane događaje — da znamo da su uklanjanje i zamena pozadine ista porodica.
U aplikaciji za obradu fotografija tako pratimo uvoz slike, uklanjanje pozadine, izvoz, i pokušaj izvoza u punoj rezoluciji.
Opis nije ukras. On je ono što omogućava da se nalaz napiše ljudski — „ko redovno uklanja pozadinu" umesto „ključ bg_remove". Ali opis se ne koristi za izbor šta je važno. Izbor dolazi iz merenja, i o tome niže.

## Tri tabele
Katalog događaja. Jedan red po vrsti događaja: naziv, opis, porodica. Upisuje se jednom.
Istorija zabeleženih radnji. Samo se dopisuje, nikad ne menja. Svaki red nosi i kad se desilo na telefonu i kad je stiglo kod nas, jer telefon bufferuje offline — sa jednim vremenom brojač „zadnjih 7 dana" tiho laže. Svaki događaj nosi i svoj id, pa ponovljen zahtev posle timeout-a ne duplira.
Pravila po kojima iz radnji dobijamo atribute. Ovo je tabela a ne kod, da bi pravilo moglo da se doda ili promeni bez novog izdanja.
Pošto Adapty ne pamti istoriju atributa, ova istorija je jedino mesto gde postoji vremenska osa. To nije zaobilaženje platforme nego podela posla: oni drže trenutnu odluku, mi držimo put do nje.

## AI predlaže šta vredi izračunati
Ovo je prvo mesto gde AI radi, i najvažnije.
Iz kataloga događaja i njihovih opisa AI predlaže koje vrednosti vredi izvesti. Na primer: koliko je različitih slika korisnik obradio u poslednjih sedam dana, koliko ih je izvezao, i da li ga je besplatan paket zaustavio pri izvozu u punoj rezoluciji.
Vredi primetiti da to nisu sirovi brojači nego sastavljene vrednosti — različite slike a ne sve radnje, prozor od sedam dana a ne od početka, i jedan događaj kao prepreka a ne kao upotreba. Takve stvari niko ne instrumentira unapred, jer ne zna koja će biti važna.
A izbor se posle meri, ne nagađa. Predložena vrednost ulazi u rangiranje i mora da se pokaže na korisnicima koje model nije video. Ako ne razdvaja ljude, pada.
Zašto to nije prepušteno modelu: u ovim istim podacima photos_imported zvuči jednako razumno kao ai_edits_first_day, a ne predviđa ništa — od 8,73 do 9,55 dolara, ravna linija, dok drugi daje od 3,73 do 16,57. Nijedan model to ne bi pogodio iz naziva. Uvoz slike je priprema; obrada je momenat kad proizvod isporuči. Prediktivno je obično ovo drugo, a developer prvo instrumentira ovo prvo, jer je lakše.

## Od vrednosti do segmenta
Naš sistem izračuna predložene vrednosti za svakog korisnika i kombinuje ih sa onim što Adapty već zna — stanjem pretplate, zemljom, platformom.
Tako dobijemo, recimo, segment ljudi bez pretplate koji redovno uklanjaju pozadinu i već su pokušali da izvezu sliku u punoj rezoluciji.
Kombinacija je ono što nosi vrednost. Jedan atribut u ovim podacima daje razliku od 4,4 puta; kombinacija od četiri ose daje 24 puta, po 55 užih grupa, od 0,89 do 21,78 dolara po korisniku. Pet puta više iz istih podataka, samo zato što se seče po više osa.
U Adapty ide samo ono što segment mora da pročita, i to je mali i ograničen set polja — ne jedno polje po funkciji. Aplikacija sa pedeset funkcija piše isti broj polja kao i ona sa pet. Ostatak ostaje kod nas.

## Paywall za taj segment
Za taj segment AI pripremi paywall koji ističe izvoz u punoj rezoluciji — ali samo ako ga ponuđeni paket uključuje. To je važna brana: ne obećavamo ono što proizvod ne daje.
To je drugo mesto gde AI radi. Uzme živu konfiguraciju paywall-a, promeni naslov i listu planova, i upload-uje je. Može i da je sastavi sam, ali tada uz validator i pad na izmenjenu kopiju ako generisana ne prođe — jer upload odbija nevalidnu konfiguraciju, a na demou imaš jedan pokušaj.
Ne delimo popuste. Ističemo ono što čovek već radi i šta bi za to dobio. Popust je druga tema i za njega u ovim podacima nema randomizovane ruke, pa o njemu ne tvrdimo ništa.

## Human i Autopilot
Dva režima, i podrazumevani je Human.
U režimu Human tim pregleda predlog i odlučuje da li će ga pustiti. Vidi nalaz, predloženo pravilo, šta se menja na paywall-u, očekivani efekat, i tri dugmeta: odobri, izmeni, odbij. „Izmeni" menja vrednosti pravila, ne JSON paywall-a. Izmena se beleži, jer je čovekova korekcija podatak: ako sistem stalno promaši granicu, to se vidi.
U režimu Autopilot sistem sam pokrene A/B test prema unapred zadatim podešavanjima.
Autopilot je ograničen i kad je uključen. Sme da upiše atribute, napravi segment, zakači audience, napravi A/B test i napiše konfiguraciju paywall-a. Objavljivanje flow-a ostaje čoveku, jer objavljen paywall korisnici vide odmah — a i Adapty sam traži potvrdu na toj komandi, pa nam se granica poklapa sa njihovom.
Svaka odluka nosi oznaku ko ju je doneo, čovek ili autopilot. Tako se posle može uporediti da li je autopilot radio jednako dobro.

## Kako merimo
Deo korisnika u segmentu vidi postojeći paywall, a deo novi. Tako merimo da li uz novu ponudu veći procenat korisnika iz te grupe zaista kupuje.
Deo koji vidi stari paywall nije gubitak nego uslov. Bez njega ne znamo da li je razlika došla od naše promene ili od toga kakvi su ti ljudi bili. I kad počnemo da delujemo po svojim nalazima, taj deo je jedino što čuva mogućnost da i dalje merimo — ako grupa uvek dobija novi paywall, nikad više ne vidimo šta bi bila bez njega.
Merimo kupovinu umanjenu za refundacije, u istom prozoru za obe strane. Konverzija sama po sebi vara: weekly plan u ovim podacima ima 6,9 odsto refundacija, pa bi optimizacija konverzije aktivno štetila.
Jedna glava prednosti koju imamo: u datim podacima već postoje A/B ruke sa slučajnom podelom. Odatle vidimo koja ponuda koju grupu diže pre nego što pustimo svoj prvi test — lifetime ponuda vredi 14,40 dolara korisnicima sa pet i više obrada, a 5,36 onima bez ijedne. Dakle grupa menja i koja je ponuda bolja, ne samo koliko ko plaća.

## Šta ne tvrdimo
Paywall koji se pojavi kad čovek udari u limit nosi 31,18 dolara po korisniku, a onaj na onboardingu 6,14. To ukazuje da je trenutak važan, ali ne dokazuje: ko stigne do limita već ima 5,42 obrade prvog dana prema 3,34 na onboardingu, a dodela placementa nije slučajna. Broj iznosimo kao nagoveštaj.
Adapty izvršava po grupi, ne po korisniku. Svakog čoveka ocenjujemo pojedinačno, ali sadržaj se servira segmentu, jer platforma tako radi. Zato ne govorimo „personalizacija po korisniku".
Lumen dataset je sintetički. Oblik mu je realan i veze između ponašanja i plaćanja su namerno ugrađene, ali brojevi su demo podloga, ne tržišna istina.
Ne predviđamo čoveka nego ga stavljamo u izmerenu grupu. Ne tvrdimo „ovaj pojedinac će kupiti", nego „ovaj pojedinac je u grupi čiji je izmereni efekat bio toliki".

## Integracija sa Adaptyjem
Sve posle prvog koraka već postoji i radi; mi dodajemo samo prvi. Sve ispod je provereno izvršavanjem 7. novembra.
Upis atributa ide PATCH-om na https://api.adapty.io/api/v2/server-side-api/profile/, sa headerima Authorization: Api-Key i adapty-customer-user-id. Telo je lista a ne objekat, {"custom_attributes":[{"key":"...","value":"..."}]}, jer objekat vraća 400 „value is not a valid list". I PATCH i POST spajaju sa postojećim atributima, nijedan ne zamenjuje — postojeća polja su bezbedna; value postavljen na null briše jedno polje. Limiti: 30 atributa po profilu, ključ do 30 znakova, vrednost do 50. Promena stigne do segmenta za 0,6 sekunde, a SDK keš vraća stari flow dok se profil ne osveži — zato posle upisa zovemo osvežavanje profila. Da je upis sleteo vidi se po tome što se segment_hash na profilu promeni.
Segment se pravi kroz adapty segments create, a filter se piše u obliku polje:OPERATOR:vrednost. Custom atribut se adresira kao attributes__<ključ>@string ili @float. Poređenja rade samo nad @float; string podržava IN, NOT IN, IS NULL i IS NOT NULL. Filteri u jednom segmentu se spajaju sa AND.
Audience na placementu kači segment, kroz adapty placements update. Svaki unos traži eksplicitan content_type, a priority odlučuje kad čovek upada u više njih — pobeđuje najviši. Placement mora imati najmanje jedan audience i podrazumevani, pa se ne može isprazniti: „ništa ne prikaži" ne postoji kao akcija, i zato je kontrolna strana audience koji pokazuje postojeći paywall. Pročitaj placements get pa pošalji celu listu, jer --audiences prima niz.
Flow se pravi kroz flows create, pa flows config update --config-file, pa flows publish. Objavljivanje je asinhrono: vrati publishing, pa se čeka published. Nepublikovan flow zakačen na audience vraća 400.
A/B test se pravi kroz ab-tests create pa start. Samo nacrt može da se pokrene; da bi se isti test pustio ponovo, pravi se kopija.
Dve granice koje smo našli: prikazi paywall-a po korisniku ne dolaze kroz CLI, nego kroz S3 export ili zbirno u analitici; i na profilu nema polja o tome u kojoj je A/B ruci bio, pa sopstveni uplift iz živog testa ne možemo da računamo sami — čitamo Adaptyjev rezultat po ruci.
Sve je povratno. Brisanje naših polja i segmenta vraća aplikaciju u prvobitno stanje; ništa ne dira kupovine, cene ni postojeće flow-ove.

## Kako kod treba da izgleda
Portovi i adapteri: svaki sloj zna jednu stvar i ne zna ostale. Posledica je da se rizični delovi testiraju bez baze i bez mreže, a kriterijum ocenjivanja upravo to traži.
Stek: FastAPI i uvicorn, pydantic v2 i pydantic-settings, SQLAlchemy 2.0 async i Alembic, pandas i scikit-learn, openai SDK, httpx, pytest.
domain je srce, i u njemu nema ni jednog I/O poziva. Tri datoteke nose sve što je rizično: rules.py primeni pravilo na istoriju jednog korisnika i vrati broj; ranking.py nađe koja vrednost razdvaja ljude, sa proverom na odvojenom delu i bootstrap intervalom; uplift.py izračuna efekat ponude po grupi sa randomizovanih ruku.
Pravila su podaci, ne kod. Statistika odlučuje a LLM objašnjava — domain ne uvozi integrations, pa ranking.py fizički ne može da pozove model. LLM dotiče tačno dva servisa: predlog pravila i pisanje konfiguracije paywall-a.
Testovi na tri nivoa: unit nad domain bez I/O, service sa lažnim portovima bez I/O, i integration nad repozitorijumima na bazi u memoriji. Nijedan test ne ide na mrežu.

## Faze
Faza 0 repo i check-in · Faza 1 ingest (curl → baza, isti id dvaput ne duplira) · Faza 2 mozak (AI predlog vrednosti, rangiranje sa holdout-om i bootstrap intervalom, uplift sa randomizovanih ruku) · Faza 3 krug u Adapty (najrizičnije, rano) · Faza 4 demo klijent i naša strana sa karticom predloga · Faza 5 paywall za segment (kopija žive konfiguracije) · Faza 6 README, AI_LOG, demo video · Faza 7 rezerva, proba, predaja.
Ako zafali vremena režemo: generisanje konfiguracije od nule, naš MCP server, lepotu naše strane. Ne režemo fazu 3.

## Demo, tri minuta
20 s problem i citat · 40 s klikanje u aplikaciji i događaji · 40 s naša strana (AI predlog, šta je prošlo proveru, segment) · 60 s odobri pa prelaz na pravi Adapty dashboard (segment i A/B test) · 20 s isti SDK lookup za dva korisnika vraća različit flow (naziv flow-a ili screenshot).

## Šta ne radimo
Kontekst signale (dark mode, klasa uređaja) · sesije i satnicu · dodatne modele za pLTV i rizik odlaska · bandit · dekompilaciju tuđih aplikacija kao sekciju demoa · generisanje paywall-a bez žive konfiguracije kao osnove.

## Razgraničenje
Helium bira između paywall-ova po onome što aplikacija pošalje; mi predlažemo šta uopšte vredi poslati i merimo da li je pomoglo. Adapty Autopilot radi po aplikaciji, placementu i zemlji; mi po užoj grupi izvedenoj iz ponašanja.
