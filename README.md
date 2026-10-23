# lego-ceny-ue

Porównywarka cen LEGO w sklepach z całej UE. Pokazuje cenę w złotówkach **razem z kosztem dostawy do Polski**.

## Jak to działa

1. `data/products.csv` to lista par: numer zestawu, sklep, adres strony produktu.
2. `python -m lego_ceny scrape` pobiera każdą stronę i odczytuje z niej cenę. Większość sklepów osadza dane produktu w formacie schema.org (JSON-LD), więc jeden parser obsługuje wiele sklepów.
3. Ceny są przeliczane na PLN po średnim kursie NBP, a do ceny dochodzi dostawa do Polski z `data/shops.json`.
4. Wynik trafia do historii w `data/prices.csv`, jeden wiersz na zestaw, sklep i dzień.
5. GitHub Actions uruchamia to codziennie o 5:00 UTC i zapisuje historię w repo (`.github/workflows/scrape.yml`).

## Dodawanie zestawu

Dopisz wiersz do `data/products.csv`:

```
75313,amazon-de,https://www.amazon.de/dp/XXXXXXXXXX
```

Sklep musi istnieć w `data/shops.json`. Pole `shipping_to_pl` ustaw na koszt dostawy do Polski w walucie sklepu. Dopóki jest `null`, strona pokaże samą cenę bez sumy.

## Katalog zestawów

`python -m lego_ceny catalog` pobiera listę zestawów od 2020 roku z darmowego zrzutu [Rebrickable](https://rebrickable.com/downloads/) do `data/sets.csv`.

## Testy

```
python -m unittest discover -s tests -v
```

## Do zrobienia

- Uzupełnić koszty dostawy do PL w `data/shops.json`.
- Sprawdzić, które sklepy blokują automatyczne pobieranie (Amazon często to robi). Docelowo dla Amazona lepsze jest oficjalne API programu partnerskiego.
- Krok 3: strona statyczna na GitHub Pages.
