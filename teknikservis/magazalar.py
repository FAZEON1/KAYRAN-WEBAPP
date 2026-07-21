# -*- coding: utf-8 -*-
"""Mağaza listeleri (firma bazlı). Teknik serviste mağaza seçimi için.
Yeni firma mağazaları eklemek için MAGAZALAR sözlüğüne yeni anahtar ekleyin."""

MAGAZALAR = {
    "D-MARKET": [
        {"ad": "D-MARKET (HEPSİBURADA) TEKNİK SERVİS — GEBZE", "sehir": "KOCAELİ", "ilce": "Gebze",
         "tel": "0850 252 40 00",
         "adres": "İnönü Mah. Mimar Sinan Cad. No: 3 Gebze Güzeller OSB",
         "mail": "teknikservis@hepsiburada.com"},
    ],
    "SERVISPOINT": [
        {"ad": "SERVISPOINT — MECİDİYEKÖY", "sehir": "İSTANBUL", "ilce": "Şişli",
         "tel": "0212 288 42 30",
         "adres": "Gülbahar Mah. Uysal Sk. No:3C Mecidiyeköy",
         "mail": "bilgi@servispoint.com"},
    ],
    "EERA": [
        {"ad": "İSTANBUL ACIBADEM MAĞAZASI", "sehir": "İSTANBUL", "ilce": "Kadıköy", "tel": "0850 259 2696", "adres": "Hasanpaşa Mahallesi, Lavanta Sokak, Etap İş Merkezi D Blok No: 22, Kadıköy/İstanbul", "mail": "acibademmh@itopya.com"},
        {"ad": "İSTANBUL BEYLİKDÜZÜ MAĞAZASI", "sehir": "İSTANBUL", "ilce": "Beylikdüzü", "tel": "0850 259 2696", "adres": "Barış Mahallesi, Belediye Caddesi, Ginza Lavinya No: 30/A5, Beylikdüzü/İstanbul", "mail": "beylikduzumh@itopya.com"},
        {"ad": "ANKARA SÖĞÜTÖZÜ MAĞAZASI", "sehir": "ANKARA", "ilce": "Çankaya", "tel": "0850 259 2696", "adres": "Söğütözü Mahallesi, 2176. Sokak, No: 7B Çankaya/Ankara", "mail": "ankaramh@itopya.com"},
        {"ad": "İSTANBUL KARTAL DEPO", "sehir": "İSTANBUL", "ilce": "Kartal", "tel": "0850 259 2696", "adres": "Esentepe Mahallesi, Cevizli D100 Yanyolu, Kartal/İstanbul", "mail": "kartalmh@itopya.com"},
        {"ad": "İSTANBUL AIRPORT AVM MAĞAZASI", "sehir": "İSTANBUL", "ilce": "Bakırköy", "tel": "0850 259 2696", "adres": "Ataköy 7-8-9-10, Kısım, Çoban Çeşme E-5 Yanyol Caddesi, Airport AVM Kat:2, 34158 Bakırköy/İstanbul", "mail": "airportmh@itopya.com"},
    ],
    "MONDAY": [
        {"ad": "Monday/Teknoklik", "sehir": "İSTANBUL", "ilce": "Ümraniye", "tel": "0850 259 8818", "adres": "Yukarı Dudullu, Necip Fazıl Blv. Keyap Sitesi D:44-59, 34775 Ümraniye/İstanbul", "mail": "teknik@mondaybilisim.com"},
    ],
    "VATAN": [
        {"ad": "VATAN BİLG.  ADANA 01 AVM", "sehir": "ADANA", "ilce": "SEYHAN", "tel": "0322 5043180", "adres": "AHMET REMZİ YÜREĞİR MAHALLESİ, TURHAN CEMAL BERİKER BULVARI NO:162"},
        {"ad": "VATAN BİLG.  ADANA BULVAR", "sehir": "ADANA", "ilce": "ÇUKUROVA", "tel": "0322 2120106", "adres": "GÜZELYALI MAHALLESİ, TURGUT ÖZAL BULVARI, BAYRAM BAKIRCI APARTMANI, NO:1 01332"},
        {"ad": "VATAN BİLG.  ADANA ÇUKUROVA", "sehir": "ADANA", "ilce": "ÇUKUROVA", "tel": "0322 2472266", "adres": "BELEDİYE EVLERİ MAHALESİ, DR. SADIK AHMET BULVARI NO:54/A"},
        {"ad": "VATAN BİLG.  ADANA M1 AVM", "sehir": "ADANA", "ilce": "SEYHAN", "tel": "0322 2710248", "adres": "YENİ MAHALLESİ, ÖĞRETMENLER BULVARI, 87071 SOKAK, NO:5, M1 AVM"},
        {"ad": "VATAN BİLG.  ADANA OPTİMUM AVM", "sehir": "ADANA", "ilce": "YÜREĞİR", "tel": "0322 3332031", "adres": "HACI SABANCI BULVARI NO:28"},
        {"ad": "VATAN BİLG.  ADANA ŞEHİRİÇİ", "sehir": "ADANA", "ilce": "SEYHAN", "tel": "0322 3633100", "adres": "TURHAN CEMAL BERİKER BULVARI NO:53"},
        {"ad": "VATAN BİLG.  AFYONKARAHİSAR", "sehir": "AFYON", "ilce": "MERKEZ", "tel": "0123 4567890", "adres": "DUMLUPINAR MAHALLESİ ATATÜRK CADDESİ NO:41/A-B"},
        {"ad": "VATAN BİLG.  AKSARAY", "sehir": "AKSARAY", "ilce": "MERKEZ", "tel": "0382 2220314", "adres": "EREĞLİKAPI MAHALLESİ, ATATÜRK BULVARI NO:78A/78 B"},
        {"ad": "VATAN BİLG.  AMASYA", "sehir": "AMASYA", "ilce": "MERKEZ", "tel": "0358 2121034", "adres": "TORUMTAY SOKAK, ŞEREF YÜCE İŞ MERKEZİ NO:5"},
        {"ad": "VATAN BİLG.  ANADOLU SEVKİYAT", "sehir": "İSTANBUL", "ilce": "DUDULLU", "tel": "0216 6116767", "adres": "ALEMDAĞ CAD. NO:457 YUKARIDUDULLU ÜMRANİYE"},
        {"ad": "VATAN BİLG.  ANK. (INTERNET)", "sehir": "ANKARA", "ilce": "ÇANKAYA", "tel": "0312 2079400", "adres": "KIZILIRMAK MH. 1443 CD. NO:7 BAYINDIR HAST. YANI"},
        {"ad": "VATAN BİLG.  ANK. ANKAMALL", "sehir": "ANKARA", "ilce": "AKKÖPRÜ", "tel": "0312 5412658", "adres": "KONYA DEVLET KARAYOLU ÜZERİ, MEVLANA BULVARI, NO:2, ANKAMALL AVM"},
        {"ad": "VATAN BİLG.  ANK. BATIKENT", "sehir": "ANKARA", "ilce": "YENİMAHALLE", "tel": "0312 2787960", "adres": "İNÖNÜ MAHALLESİ, FATİH SULTAN MEHMET BULVARI NO:348/2"},
        {"ad": "VATAN BİLG.  ANK. ERYAMAN", "sehir": "ANKARA", "ilce": "ETİMESGUT", "tel": "0312 2814330", "adres": "ALTAY MAHALLESİ, ORHAN BEY CADDESİ, NO:5/C"},
        {"ad": "VATAN BİLG.  ANK. FORUM ANK.", "sehir": "ANKARA", "ilce": "KEÇİÖREN", "tel": "0312 5780494", "adres": "OVACIK MAHALLESİ, YOZGAT BULVARI, FORUM ANKARA AVM, NO:97/Z-49"},
        {"ad": "VATAN BİLG.  ANK. GORDİON AVM", "sehir": "ANKARA", "ilce": "ÇANKAYA", "tel": "0312 2367146", "adres": "ANKARALILAR CADDESİ, KORU MAHALLESİ, NO:2-A"},
        {"ad": "VATAN BİLG.  ANK. KEÇİÖREN", "sehir": "ANKARA", "ilce": "KEÇİÖREN", "tel": "0312 3580007", "adres": "KALABA MAHALLESİ, FATİH CADDESİ, NO:36/105-106, FTZ AVM"},
        {"ad": "VATAN BİLG.  ANK. KUZU AVM", "sehir": "ANKARA", "ilce": "ÇANKAYA", "tel": "0312 5579015", "adres": "ORAN MAHALLESİ, ZÜLFÜ TİĞREL CADDESİ, NO:1"},
        {"ad": "VATAN BİLG.  ANK. NATA VEGA", "sehir": "ANKARA", "ilce": "MAMAK", "tel": "0312 3929301", "adres": "DOĞUKENT BULVARI, 2308 SOKAK, NO:1 NATAVEGA AVM"},
        {"ad": "VATAN BİLG.  ANK. PODİUM AVM", "sehir": "ANKARA", "ilce": "YENİMAHALLE", "tel": "0312 5028248", "adres": "MEHMET AKİF ERSOY MAHALLESİ, BAĞDAT CADDESİ, NO:60/B"},
        {"ad": "VATAN BİLG.  ANK. SİNCAN", "sehir": "ANKARA", "ilce": "SİNCAN", "tel": "0312 2630003", "adres": "ANDİÇEN MAHALLESİ, AHİ MESUT BULVARI, NO:254/A"},
        {"ad": "VATAN BİLG.  ANK. SÖĞÜTÖZÜ", "sehir": "ANKARA", "ilce": "ÇANKAYA", "tel": "0312 2079400", "adres": "KIZILIRMAK MAHALLESİ,1443. CADDE, NO:12, BAYINDIR HASTANESİ YANI,"},
        {"ad": "VATAN BİLG.  ANT. (KEPEZ)", "sehir": "ANTALYA", "ilce": "MURATPAŞA", "tel": "0123 4567890", "adres": "MEVLANA CADDESİ, NO:54"},
        {"ad": "VATAN BİLG.  ANT. (KONYAALTI)", "sehir": "ANTALYA", "ilce": "KONYAALTI", "tel": "0123 4567890", "adres": "TOROS MAHALLESİ, ATATÜRK BULVARI M.AYGÜN APARTMANI, NO:46/C"},
        {"ad": "VATAN BİLG.  ANT. ALANYA", "sehir": "ANTALYA", "ilce": "ALANYA", "tel": "0242 5152545", "adres": "CUMHURİYET MAHALLESİ, KEYKUBAT BULVARI, NO:223"},
        {"ad": "VATAN BİLG.  ANT. LARA", "sehir": "ANTALYA", "ilce": "MURATPAŞA", "tel": "0242 3234646", "adres": "FENER MAHALLESİ, AKANAY SİTESİ, A BLOK, NO:5/2"},
        {"ad": "VATAN BİLG.  ANT. MALL OF", "sehir": "ANTALYA", "ilce": "KEPEZ", "tel": "0242 5021182", "adres": "ALTINOVA SİNAN MAHALLESİ, SERİK CADDESİ YAN YOLU NO:309"},
        {"ad": "VATAN BİLG.  ANT. MANAVGAT", "sehir": "ANTALYA", "ilce": "MANAVGAT", "tel": "0242 7467391", "adres": "TUGAYOĞLU CADDESİ, 7001 SOKAK, NO:3"},
        {"ad": "VATAN BİLG.  ANT. ÖZDİLEK", "sehir": "ANTALYA", "ilce": "KEPEZ", "tel": "0242 3356296", "adres": "FABRİKALAR MAHALLESİ, FİKRİ ERTEN CADDESİ, NO:2, ÖZDİLEK PARK AVM"},
        {"ad": "VATAN BİLG.  AYDIN", "sehir": "AYDIN", "ilce": "MERKEZ", "tel": "0123 4567890", "adres": "DENİZLİ BULVARI, NO:42"},
        {"ad": "VATAN BİLG.  AYDIN KUŞADASI", "sehir": "AYDIN", "ilce": "KUŞADASI", "tel": "0256 6223072", "adres": "SÜLEYMAN DEMİREL BULVARI, NO:43"},
        {"ad": "VATAN BİLG.  AYDIN NAZİLLİ", "sehir": "AYDIN", "ilce": "NAZİLLİ", "tel": "0256 3150669", "adres": "ALTINTAŞ MAHALLESİ, MİMAR SİNAN CADDESİ, NO:20/A-B"},
        {"ad": "VATAN BİLG.  BALIKESİR", "sehir": "BALIKESİR", "ilce": "KARESI", "tel": "0266234 04 94", "adres": "PAŞA ALANI MAHALLESİ, BANDIRMA CADDESİ, 74/2A"},
        {"ad": "VATAN BİLG.  BALIKESİR 10 BURDA AV", "sehir": "BALIKESİR", "ilce": "GAZİOSMANPAŞA", "tel": "0266 5026976", "adres": "GAZİOSMANPAŞA MAHALLESİ, YENİ İZMİR YOLU, NO:002-003"},
        {"ad": "VATAN BİLG.  BALIKESİR AYVALIK", "sehir": "BALIKESİR", "ilce": "AYVALIK", "tel": "0266 3316039", "adres": "ALİ ÇETİNKAYA MAHALLESİ, ATATÜRK CADDESİ, NO:77, PARAGON AVM"},
        {"ad": "VATAN BİLG.  BALIKESİR BANDIRMA", "sehir": "BALIKESİR", "ilce": "BANDIRMA", "tel": "0266 7120772", "adres": "17 EYLÜL MAHALLESİ, CELAL ATİK CADDESİ, NO:3"},
        {"ad": "VATAN BİLG.  BALIKESİR EDREMİT", "sehir": "BALIKESİR", "ilce": "EDREMİT", "tel": "0266 3921293", "adres": "AKÇAY YOLU 3.KM. AKIN AVM YANI, (ESKİ KALE CENTER)"},
        {"ad": "VATAN BİLG.  BATMAN", "sehir": "BATMAN", "ilce": "MERKEZ", "tel": "0488 5022739", "adres": "GÜLTEPE MAHALLESİ, DEMOKRASİ BULVARI, NO:60 PETROLCİTY AVM, KAT:2"},
        {"ad": "VATAN BİLG.  BOLU", "sehir": "BOLU", "ilce": "MERKEZ", "tel": "0374 2502024", "adres": "ELMALIK MEVKİİ, NO:5/95, HİGHWAY AVM"},
        {"ad": "VATAN BİLG.  BURSA (ANATOLİUM AVM)", "sehir": "BURSA", "ilce": "OSMANGAZİ", "tel": "0123 4567890", "adres": "İSTANBUL CADDESİ, ANATOLİUM AVM NO:487 D:1.KAT:1"},
        {"ad": "VATAN BİLG.  BURSA ANATOLİUM AVM", "sehir": "BURSA", "ilce": "OSMANGAZİ", "tel": "0224 2610889", "adres": "İSTANBUL CADDESİ, ANATOLİUM AVM, NO:487 D:1.KAT, 16245"},
        {"ad": "VATAN BİLG.  BURSA AS MERKEZ", "sehir": "BURSA", "ilce": "OSMANGAZİ", "tel": "0224 2611333", "adres": "DEMİRTAŞ DUMLUPINAR MAHALLESİ, İSTANBUL CADDESİ, AS MERKEZ, AS OUTLET AVM AÇIK ÇARŞI NO:475 /16"},
        {"ad": "VATAN BİLG.  BURSA KENT AVM", "sehir": "BURSA", "ilce": "OSMANGAZİ", "tel": "0224 2716081", "adres": "KIBRIS ŞEHİTLERİ CADDESİ, NO:64 / D:2B09"},
        {"ad": "VATAN BİLG.  BURSA KORUPARK AVM", "sehir": "BURSA", "ilce": "OSMANGAZİ", "tel": "0224 2429138", "adres": "EMEK ADNAN MENDERES MAHALLESİ, TURGUT ÖZAL CADDESİ, NO:2"},
        {"ad": "VATAN BİLG.  BURSA NİLÜFER", "sehir": "BURSA", "ilce": "NİLÜFER", "tel": "0224 4510314", "adres": "ORHANELİ YOLU, LEFKOŞE CADDESİ, NO:21/B-C-D-E"},
        {"ad": "VATAN BİLG.  ÇANAKKALE", "sehir": "ÇANAKKALE", "ilce": "MERKEZ", "tel": "0286 2183624", "adres": "BARBAROS MAHALLESİ, TROYA CADDESİ, NO:2, TROYPARK AVM"},
        {"ad": "VATAN BİLG.  ÇORUM", "sehir": "ÇORUM", "ilce": "MERKEZ", "tel": "0364 3330470", "adres": "ÇEPNİ MAHALLESİ, AKŞEMSEDDİN CADDESİ, NO:4"},
        {"ad": "VATAN BİLG.  DENİZLİ", "sehir": "DENİZLİ", "ilce": "MERKEZ", "tel": "0258 2681152", "adres": "ANKARA BULVARI ÜZERİ, ZEYBEK DURAĞI KARŞISI, NO:73"},
        {"ad": "VATAN BİLG.  DENİZLİ YENİŞEHİR", "sehir": "DENİZLİ", "ilce": "MERKEZEFENDİ", "tel": "0258 3734248", "adres": "TERAS PARK AVM, ZEMİN KAT  YENİŞEHİR 55.SOKAK, NO:1"},
        {"ad": "VATAN BİLG.  DİYARBAKIR", "sehir": "DİYARBAKIR", "ilce": "BAĞLAR", "tel": "0412 2374036", "adres": "BAĞLAR MAHALLESİ, ŞANLIURFA YOLU ÜZERİ,1. KM, NO:15"},
        {"ad": "VATAN BİLG.  DÜZCE", "sehir": "DÜZCE", "ilce": "MERKEZ", "tel": "0380 7901243", "adres": "İSTANBUL CADDESİ, NO:1, KREM PARK AVM"},
        {"ad": "VATAN BİLG.  EDİRNE", "sehir": "EDİRNE", "ilce": "MERKEZ", "tel": "0284 2144060", "adres": "ABDURRAHMAN MAHALLESİ, ATATÜRK BULVARI, NO:138/139/140/141, ERASTA AVM"},
        {"ad": "VATAN BİLG.  ELAZIĞ", "sehir": "ELAZIĞ", "ilce": "MERKEZ", "tel": "0424 2478203", "adres": "MALATYA CADDESİ, NO:4/7, A BLOK"},
        {"ad": "VATAN BİLG.  ERZURUM", "sehir": "ERZURUM", "ilce": "MERKEZ", "tel": "0442 2450700", "adres": "ÖMER NASUHİ BİLMEN MAHALLESİ, İSTİKLAL CADDESİ, NO:1/A"},
        {"ad": "VATAN BİLG.  ESKİŞEHİR", "sehir": "ESKİŞEHİR", "ilce": "TEPEBAŞI", "tel": "0222 3354200", "adres": "İSMET İNÖNÜ 1 CADDESİ, NO:141"},
        {"ad": "VATAN BİLG.  G.ANTEP FORUM AVM", "sehir": "GAZİANTEP", "ilce": "ŞEHİTKAMİL", "tel": "0342 5020435", "adres": "YAPRAK MAHALLESİ, İSTASYON CADDESİ, NO:76"},
        {"ad": "VATAN BİLG.  G.ANTEP GAZİMUHTAR", "sehir": "GAZİANTEP", "ilce": "ŞEHİTKAMİL", "tel": "0342 2152454", "adres": "DEĞİRMİÇEM MAHALLESİ, MUAMMER AKSOY BULVARI, NO:22"},
        {"ad": "VATAN BİLG.  G.ANTEP PRİME MALL", "sehir": "GAZİANTEP", "ilce": "ŞEHİTKAMİL", "tel": "0342 2903735", "adres": "15 TEMMUZ MAHALLESİ, PROF. DR. NECMETTİN ERBAKAN CADDESİ, NO:33, SOKAK NO:K1-S-36A"},
        {"ad": "VATAN BİLG.  G.ANTEP SANKO PARK", "sehir": "GAZİANTEP", "ilce": "ŞEHİTKAMİL", "tel": "0342 3364856", "adres": "MAREŞAL FEVZİ ÇAKMAK BULVARI, NO:R242B, SANKOPARK AVM"},
        {"ad": "VATAN BİLG.  GİRESUN", "sehir": "GİRESUN", "ilce": "MERKEZ", "tel": "0454 2124430", "adres": "GEDİKKAYA MAHALLESİ, GAZİ MUSTAFA KEMAL BULVARI, NO:214-216A"},
        {"ad": "VATAN BİLG.  HATAY", "sehir": "HATAY", "ilce": "ANTAKYA", "tel": "0326 2904751", "adres": "MEHMET AKİF MAH. BAHARİYE CD. NO 115/A"},
        {"ad": "VATAN BİLG.  HATAY İSKENDERUN", "sehir": "HATAY", "ilce": "İSKENDERUN", "tel": "0326 6192102", "adres": "NUMUNE MAHALLESİ, EYÜP SULTAN CADDESİ, NO:1, PRİMEMALL AVM"},
        {"ad": "VATAN BİLG.  INTERNET", "sehir": "İSTANBUL", "ilce": "KÜÇÜKÇEKMECE", "tel": "0212 6947474", "adres": "MEHMET AKİF MAH. BAHARİYE CD. NO 115/A"},
        {"ad": "VATAN BİLG.  ISPARTA", "sehir": "ISPARTA", "ilce": "MERKEZ", "tel": "0246 2284402", "adres": "SÜLEYMAN DEMİREL BULVARI, NO:B06/A, IYAŞ PARK AVM"},
        {"ad": "VATAN BİLG.  İST. 212 OUTLET A", "sehir": "İSTANBUL", "ilce": "BAĞCILAR", "tel": "0212 6023482", "adres": "MAHMUTBEY MAHALLESİ, TAŞOCAĞI YOLU CADDESİ, NO:5"},
        {"ad": "VATAN BİLG.  İST. ACIBADEM", "sehir": "İSTANBUL", "ilce": "KADIKÖY", "tel": "0216 3266926", "adres": "FATİH SOKAK, SARAYARDI CADDESİ, NO:6, NAUTİLUS AVM KARŞISI"},
        {"ad": "VATAN BİLG.  İST. ALİBEYKÖY", "sehir": "İSTANBUL", "ilce": "EYÜP", "tel": "0212 6270080", "adres": "VARDAR BULVARI, NO:5, BİZ CEVAHİR HALİÇ AVM"},
        {"ad": "VATAN BİLG.  İST. ALTUNİZADE", "sehir": "İSTANBUL", "ilce": "ÜSKÜDAR", "tel": "0216 4745406", "adres": "ALTUNİZADE MAHALLESİ, KISIKLI CADDESİ, NO:47/Z1"},
        {"ad": "VATAN BİLG.  İST. AVCILAR", "sehir": "İSTANBUL", "ilce": "AVCILAR", "tel": "0212 6947474", "adres": "E-5 YAN YOL, NO:42, PELİCAN MALL AVM"},
        {"ad": "VATAN BİLG.  İST. BAHÇELİEVLER", "sehir": "İSTANBUL", "ilce": "BAHÇELİEVLER", "tel": "0212 4410561", "adres": "MEHMETÇİK SOKAK, NO:1, KADİR HAS CENTER AVM"},
        {"ad": "VATAN BİLG.  İST. BAHÇEŞEHİR", "sehir": "İSTANBUL", "ilce": "BAHÇEŞEHİR", "tel": "0212 6723577", "adres": "1655 SOKAK, NO:3 /1-2, AKBATI AVM ANA GİRİŞ KAPISI"},
        {"ad": "VATAN BİLG.  İST. BAŞAKŞEHİR A", "sehir": "İSTANBUL", "ilce": "BAŞAKŞEHİR", "tel": "0212 4854384", "adres": "BAŞAKŞEHİR MAHALLESİ, TOROS CADDESİ, ARTERİUM SİTESİ, NO:11/12"},
        {"ad": "VATAN BİLG.  İST. BEYLİKDÜZÜ", "sehir": "İSTANBUL", "ilce": "ESENYURT", "tel": "0212 8521839", "adres": "E5 KARAYOLU ÜZERİ, 1995. SOKAK, NO:2"},
        {"ad": "VATAN BİLG.  İST. BOSTANCI", "sehir": "İSTANBUL", "ilce": "ATAŞEHİR", "tel": "0216  4692454", "adres": "İÇERENKÖY MAHALLESİ, YEŞİL VADİ SOKAK NO:3/1"},
        {"ad": "VATAN BİLG.  İST. BUYAKA AVM", "sehir": "İSTANBUL", "ilce": "ÜMRANİYE", "tel": "0216 5103447", "adres": "FATİH SULTAN MEHMET MAHALLESİ, BALKAN CADDESİ, NO:56, BUYAKA AVM"},
        {"ad": "VATAN BİLG.  İST. CANPARK", "sehir": "İSTANBUL", "ilce": "ÜMRANİYE", "tel": "0216 5155064", "adres": "YAMANEVLER MAHALLESİ, ALEMDAĞ CADDESİ, NO:169"},
        {"ad": "VATAN BİLG.  İST. DUDULLU", "sehir": "İSTANBUL", "ilce": "DUDULLU", "tel": "0216 6116767", "adres": "YUKARIDUDULLU MAHALLESİ, ALEMDAĞ CADDESİ, NO:457"},
        {"ad": "VATAN BİLG.  İST. ELMADAĞ", "sehir": "İSTANBUL", "ilce": "ŞİŞLİ", "tel": "0212 2344800", "adres": "CUMHURİYET CADDESİ, FERAH APARTMANI, NO:139/5 (RADYO EVİ KARŞISI)"},
        {"ad": "VATAN BİLG.  İST. ESENYURT", "sehir": "İSTANBUL", "ilce": "ESENYURT", "tel": "0212 6202052", "adres": "PINAR MAHALLESİ, 19 MAYIS BULVARI, ESİLA KENT SİTESİ, ZEMİN KAT, NO:38"},
        {"ad": "VATAN BİLG.  İST. FORUM İSTANB", "sehir": "İSTANBUL", "ilce": "BAYRAMPAŞA", "tel": "0212 4372074", "adres": "KOCATEPE MAHALLESİ, PAŞA CADDESİ, NO:45, FORUM İSTANBUL AVM"},
        {"ad": "VATAN BİLG.  İST. GAZİOSMANPAŞ", "sehir": "İSTANBUL", "ilce": "BAYRAMPAŞA", "tel": "0212 5784646", "adres": "MURATPAŞA MAHALLESİ, ESKİ EDİRNE ASFALTI, NO:1 PASHADOR AVM"},
        {"ad": "VATAN BİLG.  İST. HARAMİDERE", "sehir": "İSTANBUL", "ilce": "ESENYURT", "tel": "0212 8524807", "adres": "E5 ÜZERİ, MEHMET AKİF ERSOY CADDESİ, GÖKDEMİR PLAZA, D:1"},
        {"ad": "VATAN BİLG.  İST. İSTWEST", "sehir": "İSTANBUL", "ilce": "BAHÇELİEVLER", "tel": "0212 7774774", "adres": "DEĞİRMENBAHÇE CADDESİ, NO:17A1-17A2"},
        {"ad": "VATAN BİLG.  İST. KALE CENTER", "sehir": "İSTANBUL", "ilce": "GÜNGÖREN", "tel": "0212 4335404", "adres": "ESKİ LONDRA ASFALTI, NO:89, KALE CENTER AVM"},
        {"ad": "VATAN BİLG.  İST. LEVENT", "sehir": "İSTANBUL", "ilce": "KAĞITHANE", "tel": "0212 2684651", "adres": "YENİÇERİ SOKAK, GÜLER İŞ MERKEZİ APARTMANI, NO:2/1"},
        {"ad": "VATAN BİLG.  İST. MALL OF İSTA", "sehir": "İSTANBUL", "ilce": "İKİTELLİ", "tel": "0212 8010401", "adres": "SÜLEYMAN DEMİREL CADDESİ, NO:7, MALL OF İSTANBUL AVM"},
        {"ad": "VATAN BİLG.  İST. MALTEPE", "sehir": "İSTANBUL", "ilce": "MALTEPE/KARTAL", "tel": "0216 3993326", "adres": "FEYZULLAH MAHALLESİ, BAĞDAT CADDESİ, MCA CADDE AVM, NO:286 D:290/2"},
        {"ad": "VATAN BİLG.  İST. MALTEPE PİAZ", "sehir": "İSTANBUL", "ilce": "MALTEPE/KARTAL", "tel": "0216 5155028", "adres": "TUGAY YOLU CADDESİ, NO:69/C, PİAZZA AVM"},
        {"ad": "VATAN BİLG.  İST. MARMARA FORU", "sehir": "İSTANBUL", "ilce": "BAKIRKÖY", "tel": "0212 4666079", "adres": "ÇOBANÇEŞME KOŞUYOLU BULVARI, NO:3, KAT 2, MARMARA FORUM AVM"},
        {"ad": "VATAN BİLG.  İST. METROGARDEN", "sehir": "İSTANBUL", "ilce": "ÜMRANİYE", "tel": "0216 7599039", "adres": "NECİP FAZIL MAHALLESİ, ALEMDAĞ CADDESİ, NO:940, METROGARDEN AVM, KAT:2, İÇ KAPI NO:148-149-150-151"},
        {"ad": "VATAN BİLG.  İST. MEYDAN AVM C", "sehir": "İSTANBUL", "ilce": "ÜMRANİYE", "tel": "0216 6502235", "adres": "FATİH SULTAN MEHMET MAHALLESİ, BALKAN CADDESİ MEYDAN İSTANBUL AVM, A APARTMANI, NO:62 A"},
        {"ad": "VATAN BİLG.  İST. NB KADIKÖY", "sehir": "İSTANBUL", "ilce": "KADIKÖY", "tel": "0216 4051327", "adres": "OSMAN AĞA MAHALLESİ, MÜHÜRDAR FUAT SOKAK, NO:6"},
        {"ad": "VATAN BİLG.  İST. NEOMARİN", "sehir": "İSTANBUL", "ilce": "PENDİK", "tel": "0216 6701393", "adres": "KAYNARCA MAHALLESİ, E5 YOLU ÜZERİ, TERSANE KAVŞAĞI, ZK-D04 NOLU İŞYERİ, NO:9"},
        {"ad": "VATAN BİLG.  İST. OLİVİUM AVM", "sehir": "İSTANBUL", "ilce": "ZEYTİNBURNU", "tel": "0212 6653105", "adres": "PROF. MUAMMER AKSOY CADDESİ, NO:30, OLİVİUM OUTLET CENTER ALT ÇARŞI KATI"},
        {"ad": "VATAN BİLG.  İST. OPTİMUM AVM", "sehir": "İSTANBUL", "ilce": "ATAŞEHİR", "tel": "0216 6641799", "adres": "İSTİKLAL CAD. OPTİMUM OUTLET AVM APT. NO:2B/1B06"},
        {"ad": "VATAN BİLG.  İST. PALLADİUM AV", "sehir": "İSTANBUL", "ilce": "ATAŞEHİR", "tel": "0216 6631732", "adres": "BARBAROS MAHALLESİ, HALK CADDESİ, NO:8/B"},
        {"ad": "VATAN BİLG.  İST. PENDİK", "sehir": "İSTANBUL", "ilce": "PENDİK", "tel": "0216 5061090", "adres": "BAHÇELİEVLER MAHALLESİ, ADNAN MENDERES BULVARI, NO:41"},
        {"ad": "VATAN BİLG.  İST. RİNGS AVM", "sehir": "İSTANBUL", "ilce": "SANCAKTEPE", "tel": "0216 5048435", "adres": "VEYSEL KARANİ MAHALLESİ, OSMAN GAZİ CADDESİ, NO:158"},
        {"ad": "VATAN BİLG.  İST. SANCAKTEPE", "sehir": "İSTANBUL", "ilce": "SANCAKTEPE", "tel": "0216 6211240", "adres": "KEMAL TÜRKLER MAHALLESİ, ATATÜRK CADDESİ, NO:124/ D:13B"},
        {"ad": "VATAN BİLG.  İST. SİLİVRİ KİPA", "sehir": "İSTANBUL", "ilce": "SİLİVRİ", "tel": "0212 7270830", "adres": "GENERAL ALİ İHSAN TÜRKCAN CADDESİ, NO:30, KİPA AVM"},
        {"ad": "VATAN BİLG.  İST. SULTANBEYLİ", "sehir": "İSTANBUL", "ilce": "SULTANBEYLİ", "tel": "0216 3986020", "adres": "FATİH BULVARI, NO:67, ATLAS PARK AVM"},
        {"ad": "VATAN BİLG.  İST. TOPKAPI", "sehir": "İSTANBUL", "ilce": "ZEYTİNBURNU", "tel": "0212 6655656", "adres": "E-5 KARAYOLU, GÜNEY YAN YOL, MEVLANA CADDESİ, NO:138"},
        {"ad": "VATAN BİLG.  İST. ÜMRANİYE", "sehir": "İSTANBUL", "ilce": "ÜMRANİYE", "tel": "0216 5059411", "adres": "İSTİKLAL MAHALLESİ, SÜTÇÜ İMAM CADDESİ, NO:148/A"},
        {"ad": "VATAN BİLG.  İST. VİALAND AVM", "sehir": "İSTANBUL", "ilce": "EYÜP", "tel": "0212 8017504", "adres": "ŞEHİT METİN KAYA SOKAK, NO:11, VİALAND AVM"},
        {"ad": "VATAN BİLG.  İZMİR BALÇOVA", "sehir": "İZMİR", "ilce": "BALÇOVA", "tel": "0232 2791264", "adres": "MİTHATPAŞA CADDESİ, NO:34, PALMİYE AVM"},
        {"ad": "VATAN BİLG.  İZMİR BORNOVA", "sehir": "İZMİR", "ilce": "BORNOVA", "tel": "0232 4951200", "adres": "KAZIM DİRİK MAHALLESİ, ANKARA CADDESİ, NO:58/2"},
        {"ad": "VATAN BİLG.  İZMİR BUCA", "sehir": "İZMİR", "ilce": "BUCA", "tel": "0232 4402503", "adres": "ADATEPE MAHALLESİ, ERDEM CADDESİ, NO:33"},
        {"ad": "VATAN BİLG.  İZMİR ÇANKAYA", "sehir": "İZMİR", "ilce": "KONAK", "tel": "0232 4020124", "adres": "İSMET KAPTAN MAHALLESİ, GAZİ BULVARI, NO:97"},
        {"ad": "VATAN BİLG.  İZMİR GAZİEMİR", "sehir": "İZMİR", "ilce": "GAZİEMİR", "tel": "0232 2375497", "adres": "EMREZ MAHALLESİ, AKÇAY CADDESİ, NO:34, 27090"},
        {"ad": "VATAN BİLG.  İZMİR KARŞIYAKA", "sehir": "İZMİR", "ilce": "KARŞIYAKA", "tel": "0232 3727762", "adres": "BAHRİYE ÜÇOK MAHALLESİ, ATATÜRK BULVARI, NO:45/C, 35600"},
        {"ad": "VATAN BİLG.  İZMİR MAVİŞEHİR", "sehir": "İZMİR", "ilce": "ÇİĞLİ", "tel": "0232 3245593", "adres": "ATAŞEHİR MAHALLESİ, 8294/1 SOKAK NO 5A VE 5B"},
        {"ad": "VATAN BİLG.  İZMİR OPTİMUM AVM", "sehir": "İZMİR", "ilce": "GAZİEMİR", "tel": "0232 5034572", "adres": "BEYAZEVLER MH, AKÇAY CD. NO:103, 35410"},
        {"ad": "VATAN BİLG.  K.MARAŞ", "sehir": "KAHRAMANMARAŞ", "ilce": "ONIKIŞUBAT", "tel": "0344 2251766", "adres": "ŞAZİBEY MAHALLESİ, HAYDAR ALİYEV BULVARI, PİAZZA AVM"},
        {"ad": "VATAN BİLG.  KARABÜK", "sehir": "KARABÜK", "ilce": "MERKEZ", "tel": "0370 4121482", "adres": "KEMAL GÜNEŞ CADDESİ, NO:92 ONEL AVM"},
        {"ad": "VATAN BİLG.  KASTAMONU", "sehir": "KASTAMONU", "ilce": "MERKEZ", "tel": "0366 2122005", "adres": "YALÇIN CADDESİ, NO:20, BARUTÇUOĞLU AVM"},
        {"ad": "VATAN BİLG.  KAYSERİ", "sehir": "KAYSERİ", "ilce": "MELİKGAZİ", "tel": "0352 2280300", "adres": "MELİKGAZİ MAHALLESİ, SİVAS CADDESİ, NO:182, İPEKSARAY AVM"},
        {"ad": "VATAN BİLG.  KAYSERİ BELSİN", "sehir": "KAYSERİ", "ilce": "BELSİN", "tel": "0352 5033028", "adres": "OSMAN KAVUNCU BULVARI, 6161. SOKAK, NO:1"},
        {"ad": "VATAN BİLG.  KAYSERİ TUNA LİFE AVM", "sehir": "KAYSERİ", "ilce": "KOCASİNAN", "tel": "0352 5133957", "adres": "BAĞIŞLI SOKAK, MİMARSİNAN CADDESİ, NO:5, K:2 D:68-69-70 TUNA LİFE CENTER"},
        {"ad": "VATAN BİLG.  KIRIKKALE", "sehir": "KIRIKKALE", "ilce": "YAHŞİHAN", "tel": "0318 5020030", "adres": "BAĞDAT CADDESİ, NO:6-8, PODİUM AVM"},
        {"ad": "VATAN BİLG.  KIRKLARELİ LÜLEBURGAZ", "sehir": "KIRKLARELİ", "ilce": "LÜLEBURGAZ", "tel": "0288 4131490", "adres": "İSTASYON CADDESİ, NO:9"},
        {"ad": "VATAN BİLG.  KOCAELİ GEBZE", "sehir": "KOCAELİ", "ilce": "GEBZE", "tel": "0262 6444265", "adres": "ANKARA CADDESİ,1301/4 SOKAK,NO:19"},
        {"ad": "VATAN BİLG.  KOCAELİ İZMİT", "sehir": "KOCAELİ", "ilce": "MERKEZ", "tel": "0262 3350646", "adres": "SANAYİ MAHALLESİ, ÖMER TÜRKÇAKAL BULVARI, NO:89, ESKİ GÖLCÜK YOLU"},
        {"ad": "VATAN BİLG.  KOCAELİ ÖZÜER AVM", "sehir": "KOCAELİ", "ilce": "MERKEZ", "tel": "0262 3351605", "adres": "KÖRFEZ MAHALLESİ, ANKARA YOLU CADDESİ, NO:18, ÖZÜER MOBİLYA AVM"},
        {"ad": "VATAN BİLG.  KONYA", "sehir": "KONYA", "ilce": "SELÇUKLU", "tel": "0332 2330033", "adres": "FERİTPAŞA MAHALLESİ, KULE CADDESİ, NO:19"},
        {"ad": "VATAN BİLG.  KONYA KENT PLAZA AVM", "sehir": "KONYA", "ilce": "SELÇUKLU", "tel": "0332 5028785", "adres": "ATASEVEN CADDESİ, NO:2, KENT PLAZA AVM"},
        {"ad": "VATAN BİLG.  KONYA SELÇUKER AVM", "sehir": "KONYA", "ilce": "SELÇUKLU", "tel": "0332 5031746", "adres": "PARSANA MAHALLESİ, KALETAŞ CADDESİ, NO:8 SELÇUKER AVM"},
        {"ad": "VATAN BİLG.  KÜTAHYA", "sehir": "KÜTAHYA", "ilce": "MERKEZ", "tel": "0274 2740121", "adres": "ADNAN MENDERES BULVARI, AKİF MUSTAFA PAŞA SOKAK, NO:6/29-30"},
        {"ad": "VATAN BİLG.  MALATYA", "sehir": "MALATYA", "ilce": "MERKEZ", "tel": "0422 2121240", "adres": "İNÖNÜ CADDESİ, NO:192, MALATYA PARK AVM"},
        {"ad": "VATAN BİLG.  MANİSA", "sehir": "MANİSA", "ilce": "MERKEZ", "tel": "0236 2116776", "adres": "HAFSA SULTAN MAHALLESİ, BAHTİYAR TOSUNBAŞ CADDESİ, NO:89/A"},
        {"ad": "VATAN BİLG.  MARDİN", "sehir": "MARDİN", "ilce": "ARTUKLU", "tel": "0482 2902474", "adres": "YENİŞEHİR MAHALLESİ, VALİ OZAN CADDESİ, MARDİAN MALL AVM"},
        {"ad": "VATAN BİLG.  MERKEZ -- 1", "sehir": "İSTANBUL", "ilce": "ŞİŞLİ", "tel": "0212 4145900", "adres": "İZZET PAŞA MAH. YENİ YOL CAD. NUROL TOWER NO:3 İÇ KAPI NO:301"},
        {"ad": "VATAN BİLG.  MERKEZ -- 2", "sehir": "İSTANBUL", "ilce": "ŞİŞLİ", "tel": "0123 4567890", "adres": "IZZET PASA MAH. YENI YOL CAD.  NUROL TOWER NO: 3 IÇ"},
        {"ad": "VATAN BİLG.  MERKEZ SEVKİYAT SELEN", "sehir": "İSTANBUL", "ilce": "BAKIRKÖY", "tel": "0212 4145900", "adres": "ATAKÖY MAH. 7-8-9-10. KISIM BEDRİ RAHMİ EYÜPOĞLU CAD. NO:4 SELENİUM İŞ MERKEZİ 1 BODRUM KAT"},
        {"ad": "VATAN BİLG.  MERSİN", "sehir": "MERSİN", "ilce": "YENİŞEHİR", "tel": "0324 3271515", "adres": "EĞRİÇAM MALLESİ, GAZİ MUSTAFA KEMAL BULVARI, NO:506"},
        {"ad": "VATAN BİLG.  MERSİN TARSUS", "sehir": "MERSİN", "ilce": "TARSUS", "tel": "0324 2904231", "adres": "FEVZİ ÇAKMAK MAHALLESİ, TARSU AVM"},
        {"ad": "VATAN BİLG.  MUĞLA BODRUM", "sehir": "MUĞLA", "ilce": "BODRUM", "tel": "0252 3196101", "adres": "KONACIK MAHALLESİ, ATATÜRK BULVARI, NO:210"},
        {"ad": "VATAN BİLG.  MUĞLA FETHİYE", "sehir": "MUĞLA", "ilce": "FETHİYE", "tel": "0252 6149092", "adres": "ÖLÜDENİZ CADDESİ, NO:14, ERASTA AVM, KAT:1, MAĞAZA NO:42"},
        {"ad": "VATAN BİLG.  MUĞLA MARMARİS", "sehir": "MUĞLA", "ilce": "MARMARİS", "tel": "0252 4172270", "adres": "ARMUTALAN MAHALLESİ, MUSTAFA KEMAL PAŞA BULVARI, 507. SOKAK"},
        {"ad": "VATAN BİLG.  MUĞLA MERKEZ", "sehir": "MUĞLA", "ilce": "MENTEŞE", "tel": "0252 2125281", "adres": "EMİRBEYAZIT, 28 SOKAK, A BLOK, NO:18A/2-3-4-5, 48100"},
        {"ad": "VATAN BİLG.  NEVŞEHİR FORUM KAPADO", "sehir": "NEVŞEHİR", "ilce": "MERKEZ", "tel": "0384 2137427", "adres": "BAHÇELİEVLER MAHALLESİ, MUSTAFA PARMAKSIZ CADDESİ, NO:56 FORUM KAPADOKYA AVM"},
        {"ad": "VATAN BİLG.  NİĞDE", "sehir": "NİĞDE", "ilce": "MERKEZ", "tel": "0388 2120130", "adres": "AŞAĞI KAYABAŞI MAHALLESİ, ATATÜRK BULVARI, NO:6"},
        {"ad": "VATAN BİLG.  ORDU", "sehir": "ORDU", "ilce": "MERKEZ", "tel": "0452 2223370", "adres": "SELİMİYE MAHALLESİ, BUHARALI ŞEYH ŞAKİR EFENDİ CADDESİ, NO:19"},
        {"ad": "VATAN BİLG.  OSMANİYE", "sehir": "OSMANİYE", "ilce": "MERKEZ", "tel": "0328 4040071", "adres": "ALİBEYLİ MAHALLESİ, DR. DEVLET BAHÇELİ BULVARI, 1. ETAP, NO:25/A-B-C"},
        {"ad": "VATAN BİLG.  RİZE", "sehir": "RİZE", "ilce": "MERKEZ", "tel": "0464 2177637", "adres": "MÜFTÜ MERKEZ MAHALLESİ, MENDERES BULVARI, NO: 292-294"},
        {"ad": "VATAN BİLG.  SAKARYA ADAPAZARI", "sehir": "SAKARYA", "ilce": "ADAPAZARI", "tel": "0264 2411339", "adres": "HACIOĞLU MAHALLESİ, S AKARBABA CADDESİ, NO:2"},
        {"ad": "VATAN BİLG.  SAKARYA SERDİVAN", "sehir": "SAKARYA", "ilce": "ADAPAZARI", "tel": "0264 2101303", "adres": "İSTİKLAL MAHALLESİ, ÇARK CADDESİ, NO:333/A"},
        {"ad": "VATAN BİLG.  SAMSUN ADALET DEPO", "sehir": "SAMSUN", "ilce": "İLKADIM", "tel": "0123 4567890", "adres": "ADALET MAH. PİYADE UZMAN ÇAVUŞ ADEM ŞENGÜL CAD. HİLAL APT. NO:19"},
        {"ad": "VATAN BİLG.  SAMSUN MERKEZ", "sehir": "SAMSUN", "ilce": "İLKADIM", "tel": "0362 4200009", "adres": "PAZAR MAHALLESİ, TELGRAFHANE SOKAK, NO:14"},
        {"ad": "VATAN BİLG.  SAMSUN PİAZZA AVM", "sehir": "SAMSUN", "ilce": "CANİK", "tel": "0362 9777099", "adres": "YENİ MAHALLE, ÇARŞAMBA CADDESİ, NO:52 PİAZZA AVM"},
        {"ad": "VATAN BİLG.  SİVAS", "sehir": "SİVAS", "ilce": "MERKEZ", "tel": "0346 2234171", "adres": "AHİEMİR CADDESİ, POLAT CENTER, NO:23"},
        {"ad": "VATAN BİLG.  ŞANLIURFA", "sehir": "ŞANLIURFA", "ilce": "MERKEZ", "tel": "0414 2151527", "adres": "11 NİSAN FUAR CADDESİ, NO:42, PİAZZA AVM"},
        {"ad": "VATAN BİLG.  TEKİRDAĞ", "sehir": "TEKİRDAĞ", "ilce": "MERKEZ", "tel": "0282 2600933", "adres": "AYDOĞDU, HÜKÜMET CADDESİ, NO:186, TEKİRA AVM, 59100"},
        {"ad": "VATAN BİLG.  TEKİRDAĞ ÇERKEZKÖY", "sehir": "TEKİRDAĞ", "ilce": "ÇERKEZKÖY", "tel": "0282 7268606", "adres": "GAZİ MUSTAFA KEMAL PAŞA MAHALLESİ, ATATÜRK CADDESİ, NO:110"},
        {"ad": "VATAN BİLG.  TEKİRDAĞ ÇORLU", "sehir": "TEKİRDAĞ", "ilce": "ÇORLU", "tel": "0282 6531799", "adres": "MUHİTTİN MAHALLES, ATATÜRK BULVARI, NO:3A/3B"},
        {"ad": "VATAN BİLG.  TOKAT", "sehir": "TOKAT", "ilce": "MERKEZ", "tel": "0356 2121252", "adres": "VALİ ZEKAİ GÜMÜŞDİŞ CADDESİ, NO:7"},
        {"ad": "VATAN BİLG.  TRABZON", "sehir": "TRABZON", "ilce": "MERKEZ", "tel": "0462 3256873", "adres": "SANAYİ MAHALLESİ, ANADOLU 1 NOLU SOKAK, NO:4"},
        {"ad": "VATAN BİLG.  UŞAK", "sehir": "UŞAK", "ilce": "MERKEZ", "tel": "0276 2310087", "adres": "GAZİ BULVARI, DENİZLİ YOL KAVŞAĞI, NO:123"},
        {"ad": "VATAN BİLG.  VAN", "sehir": "VAN", "ilce": "MERKEZ", "tel": "0432 2150180", "adres": "CEVDETPAŞA MAHALLES, İKİ NİSAN BULVARI, NO:37/A"},
        {"ad": "VATAN BİLG.  YALOVA", "sehir": "YALOVA", "ilce": "MERKEZ", "tel": "0226 8138353", "adres": "GAZİ OSMANPAŞA MAHALLESİ, ATATÜRK BULVARI, NO:88/A"},
        {"ad": "VATAN BİLG.  ZONGULDAK EREĞLİ", "sehir": "ZONGULDAK", "ilce": "EREĞLİ", "tel": "0372 3100420", "adres": "MÜFTÜ MAHALLESİ, ŞEHİT ÖMER HALİSDEMİR BULVARI, NO:45-2"},
        {"ad": "VATAN BİLG.  ZONGULDAK ESAS 67 BUR", "sehir": "ZONGULDAK", "ilce": "MERKEZ", "tel": "0372 5020011", "adres": "İNCİVEZ MAHALLESİ, MİLLİ EGEMENLİK CADDESİ NO:130"},
    ],
}


def magaza_listesi(firma=None):
    """firma verilirse o firmanın, verilmezse tüm mağazaları döndürür (ad başında firma etiketiyle)."""
    if firma and firma in MAGAZALAR:
        return MAGAZALAR[firma]
    _hepsi = []
    for _f, _lst in MAGAZALAR.items():
        _hepsi.extend(_lst)
    return _hepsi


# Mağaza grubu (MAGAZALAR anahtarı) → tam cari unvan (TS_FIRMALAR ile birebir).
GRUP_CARI = {
    "D-MARKET": "D-MARKET ELEKTRONİK HİZMETLER VE TİCARET ANONİM ŞİRKETİ",
    "SERVISPOINT": "SERVİS NOKTASI TEKNOLOJİ ANONİM ŞİRKETİ",
    "EERA": "EERA ELEKTRONİK TİCARET VE BİLİŞİM HİZMETLERİ ANONİM ŞİRKETİ",
    "MONDAY": "MONDAY BİLİŞİM SANAYİ VE TİCARET ANONİM ŞİRKETİ",
    "VATAN": "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI",
}


def _cari_grup(cari):
    """Tam cari unvandan mağaza grubunu (MAGAZALAR anahtarı) bulur. Bulunamazsa None."""
    _c = str(cari or "").strip().upper()
    for _g, _u in GRUP_CARI.items():
        if _c == _u.upper():
            return _g
    # Gevşek eşleşme (ilk kelime): EERA…/MONDAY…/VATAN…
    for _g in GRUP_CARI:
        if _c.startswith(_g):
            return _g
    return None


def magaza_cari(magaza_adi):
    """Bir mağaza adının hangi cari unvana ait olduğunu döndürür (mağaza→firma otomatik seçimi için)."""
    for _g, _lst in MAGAZALAR.items():
        for _m in _lst:
            if _m.get("ad") == magaza_adi:
                return GRUP_CARI.get(_g, "")
    return ""
