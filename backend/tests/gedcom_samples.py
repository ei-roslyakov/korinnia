"""GEDCOM files used by the import tests."""

SAMPLE = """0 HEAD
1 SOUR MYHERITAGE
2 NAME MyHeritage Family Tree Builder
2 VERS 5.5.1
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
1 DATE 7 OCT 2026
0 @I1@ INDI
1 NAME Іван Петрович /Коваленко/
2 GIVN Іван Петрович
2 SURN Коваленко
2 ROMN Ivan /Kovalenko/
1 SEX M
1 BIRT
2 DATE 12 MAR 1890
2 PLAC Великі Сорочинці, Полтавська губернія, Російська імперія
3 MAP
4 LATI N50.0241
4 LONG E33.9368
2 SOUR @S1@
3 PAGE Арк. 15 зв.
3 QUAY 3
1 DEAT
2 DATE ABT 1944
2 CAUS Війна
1 BURI
2 PLAC Великі Сорочинці, Полтавська губернія, Російська імперія
1 OCCU Коваль
1 RELI Православний
1 RESI
2 DATE BET 1920 AND 1930
2 PLAC Полтава, Полтавська губернія, Російська імперія
1 EVEN
2 TYPE Нагорода
2 DATE 1938
1 NOTE Був найкращим ковалем у селі,
2 CONC  кував коней для всієї округи.
2 CONT Друга лінія.
1 NOTE @N1@
1 FAMS @F1@
1 OBJE
2 FILE photos/ivan.jpg
1 _UID 1234
1 _CUSTOM something
0 @I2@ INDI
1 NAME Ганна /Мельник/
2 _MARNM Коваленко
1 SEX F
1 BIRT
2 DATE 1894
1 DEAT
2 DATE 1971
1 FAMS @F1@
0 @I3@ INDI
1 NAME Олександр Іванович /Коваленко/
1 SEX M
1 BIRT
2 DATE 4 JUL 1919
1 FAMC @F1@
0 @I4@ INDI
1 NAME Марія /Коваленко/
1 SEX F
1 BIRT
2 DATE (Великдень 1922)
1 FAMC @F1@
2 PEDI adopted
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 CHIL @I3@
1 CHIL @I4@
1 MARR
2 DATE 1915
2 PLAC Полтава, Полтавська губернія, Російська імперія
2 SOUR @S1@
3 PAGE Арк. 3
0 @S1@ SOUR
1 TITL Метрична книга Преображенської церкви
1 AUTH Полтавська духовна консисторія
1 REPO @R1@
2 CALN Ф. 1011, оп. 1, спр. 34
0 @R1@ REPO
1 NAME Державний архів Полтавської області
0 @N1@ NOTE Спільна примітка з окремого запису.
0 TRLR
"""
