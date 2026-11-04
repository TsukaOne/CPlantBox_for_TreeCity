# Croissance secondaire TreeCity : modèle, sources et modifications

Ce document est la référence unique sur la croissance secondaire (`secondary_growth/`, `tree/species.py`, `grid.py`, XML des 3 espèces). Il remplace `secondary_root_growth_math.md` : les points vérifiés de ce dernier sont repris ici, le reste est listé au §17. Il note, pour chaque choix, ce qui a été fait, pourquoi, et sur quelle source ou quel essai cela repose.

État : 28 octobre 2026. Proxy d'effilement Betula appliqué aux feuillus ; option B du §2 (collet calé sur le DBH du projet) appliquée et testée à 5, 20, 50 et 120 ans (c = 1,0 ; sensibilité à c = 1,2) ; les résultats du §13 sont ceux de l'option B ; commit en attente.

Statuts utilisés :
- **Sourcé** : valeur ou loi retrouvée dans une publication relue (la source et la page ou le tableau sont indiqués).
- **Proxy** : valeur d'une autre espèce, provisoire, à signaler.
- **Choix** : décision de modélisation, justifiée par un essai ou un raisonnement, sans source.
- **À recontrôler** : source ou valeur non vérifiée, ou vérifiée avec une réserve.
- **À corriger** : incohérence constatée, décision en attente.

Conditions des essais cités : `sandbox_v3`, sol 1 `loose_uniform`, sans rue, 50 arbres, graine 7, 120 ans sauf mention contraire. `analyse_vtp_vti.py` donne les mesures détaillées sur 3 arbres (ordres de grandeur) et reprend le résumé sur 50 arbres écrit par `sandbox_v3.py` (`_summary.txt`).

## 0. Contexte

CPlantBox donne à chaque segment un rayon `a` statique, tiré à la création de la racine et gardé pendant toute la simulation. Il n'y a donc pas d'épaississement radial (affirmation reprise de l'ancien .md, qui l'attribuait à Schnepf et al. 2018, *Ann. Bot.* 121:1033-1053 : **À recontrôler**). Pour un arbre de 120 ans c'est inacceptable : le cambium épaissit les racines structurales toute leur vie. La croissance secondaire est donc un post-traitement qui réaffecte les rayons après la simulation, sans rétroaction sur la croissance (limite assumée : un segment plus épais ne change ni la conductance ni l'élongation).

Données du post-traitement : graphe de segments reconstruit depuis le `.vtp`, avec pour chaque segment son âge, son sous-type, son rayon primaire `r0` (le `a` du XML) et ses enfants. Sous-types structuraux : ST1 (collet ou pivot), ST2, ST4, ST6, ST7. Fines : ST3, ST5.

## 1. Chaîne de calcul

Pour chaque nœud d'un arbre racinaire :

1. **Loi d'âge** : `r_age = r0 + k · t^α`, appliquée aux structurales ; les fines gardent leur rayon primaire. Elle donne la taille du collet (§2).
2. **Section conservée** d'exposant Δ = 2,0 (§3) : schéma par organe (§6) pour ST2/4/6/7, récurrence par nœud pour ST1 (§5).
3. **Fusion quadratique** (§8) : la loi d'âge donne la magnitude au collet, la section conservée donne la répartition dans la hiérarchie.
4. **Continuité** : aucune racine plus fine que son rayon primaire ni plus épaisse que son porteur, puis plafond de rayon (§10).

Le pipe model (κ = 0,8) et la règle de da Vinci × SGC (0,8), d'abord calculés et écrits dans le `.vtp` comme témoins (`radius_pipe`, `radius_da_vinci`), ont été **supprimés** du code (`pipe_efficiency`, `area_conservation`, les deux fonctions de rayon et les deux tableaux) : ils n'entraient dans aucun rayon final et, à l'ordre près, donnaient les rayons primaires (mesure sur un Picea de 120 ans). Leurs formules et sources (Shinozaki et al. 1964 ; McMahon & Kronauer 1976 ; Pagès et al. 2014 pour SGC) ne sont donc plus utilisées ici.

## 2. Loi d'âge et taille du collet

**Quoi (état du code avant l'option B).** `r_age = r0 + k · t^α`, t en jours, k = 0,021 cm·j^-α, α = 0,6 (`PICEA_SECONDARY_GROWTH`, repris par les feuillus). Au collet à 120 ans : 12,8 cm + r0, soit un diamètre de 26,0 cm (Picea), 26,4 cm (Quercus, r0 = 0,40) et 28,4 cm (Aesculus, r0 = 1,40).

**Ajustement d'origine.** Diamètre de souche D0 de Picea à 15, 28 et 41 ans : 7,9 / 11,7 / 14,7 cm (Kalliokoski, Nygren & Sievänen 2008, *Silva Fennica* 42(2):189-210, Tableau 1 ; mêmes valeurs dans Kalliokoski, Sievänen & Nygren 2010, *Trees* 24:219-236, Tableau 2). Le modèle donne 7,7 / 11,1 / 13,8 cm (-3 à -6 %). Les valeurs sont **confirmées** ; le choix des points ne l'est pas.

**Ce que les sources montrent.**

| Peuplement (Silva Fennica 2008, Tableau 1) | Âge | D0 observé | Modèle k = 0,021 / α = 0,6 |
|---|---|---|---|
| Picea sapling MT (planté) | 15 | 7,9 cm | 7,7 |
| Picea pole MT (naturel) | 28 | 11,7 | 11,1 |
| Picea pole OMT (planté) | 34 | 18,2 | 12,4 |
| Picea pole VT (naturel, supprimé) | 41 | 14,7 | 13,8 |
| Picea mature MT (planté, éclairci) | 55 | 29,2 | 16,4 |
| Betula sapling / pole / mature MT | 13 / 29 / 48 | 8,1 / 16,1 / 30,0 | ajusté α = 0,6 : ×1,31 / ×1,04 / ×0,74 |

- Les 3 points retenus viennent de 3 peuplements différents. Le gradient d'âge de l'étude est celui des peuplements **MT** (15, 30, 50 ans) ; le VT appartient au gradient de fertilité, et ses épicéas ont été supprimés une vingtaine d'années (§3.2.3 et §4.4.1 de l'article : « à traiter avec prudence »). Les deux plus gros épicéas (34 ans OMT, 55 ans MT) ne sont pas utilisés : le modèle les sous-estime de 32 % et 44 %.
- Betula MT donne D0 / âge = 0,62 / 0,56 / 0,62 cm par an : croissance **linéaire** (pente log-log 1,0). Ajustement libre sur ces 3 points : α = 1,05. Pour Picea MT (15, 28, 55 ans) : α ≈ 1,0 aussi. Aucune série de l'article ne donne α = 0,6 ; avec α fixé à 0,6, le meilleur k est 0,026 (Picea MT) ou 0,031 (Betula MT), avec des résidus de +22 % à -30 %.
- Les peuplements diffèrent par la densité (530 à 6 480 arbres/ha), la fertilité et le mode de régénération : l'âge est confondu avec ces facteurs, ce n'est pas une série de croissance. k n'est qu'une échelle approximative.
- **Thamm et al. 2019** (*R. Soc. Open Sci.* 6:190126), cité par l'ancien .md pour α = 0,4-0,6, porte sur le xylème secondaire d'*Arabidopsis* à un stade précoce (exposant 2/5 entre l'aire de la base et la hauteur du cône de xylème). Ce n'est pas une loi rayon-âge d'arbre : **ne soutient pas α**.

**Incohérence avec le DBH du projet (corrigée par l'option B).** `tree/attributes.py` donne DBH = 1,2 · âge^0,85 cm, soit 70,2 cm à 120 ans. Le collet du modèle racinaire fait 26-28 cm de diamètre au même âge (rapport 0,37-0,40) alors qu'un diamètre de souche est en général au moins égal au DBH. Le DBH n'est qu'une entrée de conditionnement du réseau, mais il contredit les racines simulées.

| Âge | D0 boréal (Kalliokoski) | DBH du projet |
|---|---|---|
| Picea 15 / 28 / 55 ans | 7,9 / 11,7 / 29,2 | 12,0 / 20,4 / 36,2 |
| Betula 13 / 29 / 48 ans | 8,1 / 16,1 / 30,0 | 10,6 / 21,0 / 32,2 |

L'allométrie du projet est de 1,1 à 1,7 fois supérieure aux diamètres de souche boréaux et s'en rapproche à 48-55 ans. Pour un arbre urbain à croissance libre, elle est plus plausible que la forêt dense de Hyytiälä.

**Décision (28 oct. 2026) : option B, collet calé sur le DBH du projet.** Les trois options étudiées étaient : A, garder k = 0,021 / α = 0,6 et documenter l'écart ; B, caler le collet sur l'allométrie du projet ; C, ajuster k = 0,026 (α = 0,6) sur la chronoséquence MT (collet de 16 cm à 120 ans, encore moitié du DBH). B est retenue parce que c'est la seule qui rend l'arbre simulé cohérent avec lui-même.

**Loi retenue.** Diamètre au collet D0 = c · DBH(âge), avec DBH(âge) = `DBH_COEFFICIENT` · âge^`DBH_AGE_EXPONENT` (1,2 · âge^0,85 cm, `tree/attributes.py`) et c = 1,0. En termes de la loi d'âge `r0 + k · t^α` (t en jours) : α = `DBH_AGE_EXPONENT` = 0,85 et k = 0,5 · c · `DBH_COEFFICIENT` / `DAYS_PER_YEAR`^α = 0,00398 cm·j^-0,85. Rayon de collet (hors r0) : 2,4 cm à 5 ans, 35,1 cm à 120 ans. k et α sont **calculés** à partir des constantes de `attributes.py` (pas saisis), pour qu'un changement d'allométrie par l'équipe 2 se répercute sur les racines.

**Pourquoi c'est le plus réaliste.**
1. **Cohérence de l'arbre.** Le DBH est une entrée de conditionnement du réseau ; un collet de 26 cm sous un DBH de 70 cm est impossible (souche ≥ DBH).
2. **Arbre urbain.** L'allométrie du projet (spécification, à remplacer par les mesures de l'équipe 2) décrit des arbres à croissance libre, plus gros que ceux des peuplements boréaux denses de Hyytiälä (1,1 à 1,7 fois les D0 de Kalliokoski à âge égal), et proche d'eux à 48-55 ans (+7 % pour Betula, +24 % pour Picea mature MT, planté et éclairci).
3. **Forme de la loi.** Les séries de Kalliokoski donnent α ≈ 1,0 (Betula 1,05 ; Picea MT ≈ 1,0) ; α = 0,85 en est proche et corrige le défaut de α = 0,6, qui surestime les jeunes arbres et sous-estime de 30 à 45 % les gros.
4. **Un seul fil conducteur** âge → DBH → collet pour l'affinage par tranches d'âge (2 à 120 ans).

**Écarts avec la littérature, assumés.**
- **Valeur absolue de D0** : à 15-28 ans, l'allométrie donne 1,5 à 1,7 fois les D0 de Picea (12,0 contre 7,9 cm ; 20,4 contre 11,7 cm), mesurés en peuplements denses. Les tranches jeunes seront donc plus épaisses que la littérature boréale ; elles sont cohérentes avec le DBH du projet.
- **α = 0,85 au lieu de 1,0** : choix de cohérence avec l'allométrie ; les ajustements de la littérature reposent sur 3 points de peuplements confondus (âge, densité, régénération).
- **c = 1,0 non sourcé** : borne basse (souche ≥ DBH). Aucune source ne donne D0 / DBH sur les mêmes arbres (dans le Tableau 1 de Kalliokoski, D1,3 est une moyenne de peuplement, pas celle des arbres échantillons). Un empattement du collet (c de 1,1 à 1,3) est plausible mais non sourcé : test de sensibilité ci-dessous.
- **Extrapolation à 120 ans** : aucune donnée racinaire au-delà de 55 ans.

**Résultats des tests (28 oct. 2026, c = 1,0).** Appliqué dans `tree/species.py` (`COLLAR_TO_DBH_RATIO`, k et α calculés). Détail au §13.
1. **T-B1** : le rayon de collet vaut DBH/2 + r0 à 5, 20, 50 et 120 ans. L'écart à DBH/2 est constant d'un âge à l'autre (0,20 cm Picea, 0,39 Quercus, 1,50 Aesculus), soit le `a` du XML.
2. **T-B2** : Σ D² des ST2 / D² du collet entre 0,96 et 1,03 (Picea, Quercus) et 0,97-0,98 (Aesculus à 50 et 120 ans) ; hors plage (0,86-1,87) pour Aesculus à 5 ans (0,65), à cause de r0 = 1,4 cm (§14.8), et en bas de plage à 20 ans (0,91).
3. **T-B3** : aucun ST2 plus épais que le collet (ST2 le plus épais / collet de 0,40 à 0,58) ; part major/total en forte hausse à 120 ans (Picea 49 %, Quercus 74 %, Aesculus 47 %, contre 18 / 31 / 21 % avant l'option B).
4. **T-B4** : masses en hausse de 17 à 27 % (Picea +17 %, Aesculus +20 %, Quercus +27 %) ; aucune saturation (20 à 28 voxels ≥ 0,99 sur 139 264, autour du collet) ; plafond de 40 cm jamais atteint (§10).
5. **T-B5** (c = 1,2) : pour Picea (collet de 42,3 cm), s est multiplié par 1,44, la masse monte de 4,7 % et la part major passe à 54 % ; pour Quercus et Aesculus le plafond de 40 cm est resté actif, donc ces deux essais ne sont exploitables qu'en qualitatif (§10, §13).
6. **Géométrie** identique (segments, profondeurs, tortuosités, hors grille).

Restent vrais : c = 1,0 non sourcé ; s = 12,6 / 85 / 59 à 120 ans (§8, §14.4).

Statut : **Choix** (cohérence avec l'allométrie du projet, forme appuyée sur Kalliokoski 2008), appliqué et testé.


## 3. Exposant de la section conservée (Δ = 2,0)

**Quoi.** Δ = 2,0 pour les 3 espèces : c'est la règle de Léonard (da Vinci), pas la loi de Murray (Δ = 3, hydraulique).

**Sources.**
- Kalliokoski et al. 2010, *Trees* 24:219-236, Éq. 6 : ajustement de `(D_dist parent)^Δ = c · Σ (D_prox enfant)^Δ` sur tous les nœuds. Δ moyen = 2,18 (*B. pendula*), 2,19 (*P. abies*), 2,01 (*P. sylvestris*) ; la valeur 2 est dans l'intervalle de confiance à 95 % des 3 espèces. **Sourcé** pour Picea et pour Betula (proxy des feuillus).
- Même article : la section distale du parent égale la somme des sections proximales des enfants (p_branch médian 0,99 / 1,02 / 1,02, Éq. 5). La conservation de section aux nœuds est donc vérifiée, et l'effilement se fait à l'intérieur des segments.
- Kalliokoski et al. 2008, Tableau 3 : RelSumD² (somme des D² des racines proximales / D² de la souche) : Picea 1,02 / 0,96 / 1,31 / 1,87 / 1,87 (stades sapling MT, pole MT, mature MT, pole OMT, pole VT) ; Betula 0,86 / 1,02 / 0,88 / 1,75 / 1,29 ; Pinus 1,11 / 1,21 / 1,05 / 1,68 / 1,35. Pas de différence significative entre stades. Mature MT : Picea 1,31 ± 0,50, Betula 0,88 ± 0,08.
- Oppelt, Kurth & Godbold 2001, *Tree Physiol.* 21:117-128 : la théorie « pipe-stem » (règle de Léonard) est conforme aux mesures « avec une précision raisonnable » (résumé seulement, espèces africaines). **À recontrôler.**

Dans le code : Σ D² des ST2 / D² du collet = 1,00 (Picea) et 0,97 (Quercus, Aesculus), dans la plage mesurée (0,86-1,87) mais en bas. Aucune mesure pour Quercus ni Aesculus.

## 4. Loi d'effilement par groupe d'axes

**Quoi.** `T(D) = 1 / (1 + a·D + b·D²)`, D en m depuis la base de l'axe. Trois groupes dans `SecondaryGrowthParameters` : `main_axis_taper` (ST2), `secondary_axis_taper` (ST4, ST6, ST7), `primary_axis_taper` (ST1, neutre, voir §5). Pour b < 0, D est plafonné à -a/2b (maximum du dénominateur).

**Source.** Kalliokoski et al. 2008, Éq. 2 et Tableau 7 (a, b par essence, stade et type de station ; RMSE donnés).

| Essence, stade | Axe principal (a ; b ; RMSE) | Axes secondaires (a ; b ; RMSE) |
|---|---|---|
| Picea mature MT | 1,739 ; -0,043 ; 0,074 | 1,409 ; -0,095 ; 0,154 |
| Betula mature MT | 1,112 ; -0,022 ; 0,067 | 1,801 ; -0,462 ; 0,145 |

Les deux lignes sont **confirmées** à la relecture de l'article.

**Vérifications.**
- **Unité de D** : non indiquée dans l'article, mais le mètre est confirmé par les exemples de racines isolées du Tableau 4 de Kalliokoski et al. 2010. Picea mature MT : diamètre 8,13 cm au début, 3,49 cm après 53 + 21 = 74 cm, soit 0,429 ; T(0,74 m) = 0,442. Betula mature MT : 6,30 → 3,52 cm après 69 cm, soit 0,559 ; T(0,69 m) = 0,569. Ces deux exemples lèvent aussi l'ambiguïté de définition (le texte de 2008 parle d'un rapport « début d'axe / avant le nœud », supérieur à 1, alors que l'Éq. 2 donne T ≤ 1) : T = d(D) / d(0).
- Les ZRT (zones d'effilement rapide) se limitent aux axes d'ordre 2 et 3 (Kalliokoski 2010) : cohérent avec deux groupes (principal, secondaire) ; l'article de 2008 sépare en réalité les axes secondaires en deux groupes (départ à moins de 1,5 m du collet ou non), mais le Tableau 7 n'en donne qu'un.
- **Réserves sur le Tableau 7** : la légende de la Fig. 4A donne a = 2,026 et b = 0,878 pour *P. sylvestris* OMT, alors que le tableau attribue ces valeurs à Picea pole OMT ; plusieurs b sont positifs (Picea pole MT +1,011, pole OMT +0,878 ; Pinus mature MT a = -0,170, b = 4,084). Les lignes utilisées ne sont pas concernées.
- **Dépendance au stade** : l'effilement de l'axe principal est plus lent dans les vieux peuplements (Picea a = 3,359 / 2,884 / 1,739 pour sapling / pole / mature MT ; Betula 2,860 / 2,332 / 1,112). Le code applique la loi du peuplement mature à tous les âges ; à regarder pour l'affinage par tranches d'âge. Le secondaire est irrégulier, sans tendance claire.

**Feuillus : proxy Betula pendula mature MT (appliqué le 27 oct. 2026).** Quercus et Aesculus utilisaient les valeurs de Picea (`BROADLEAF_PROVISIONAL`) ; ils utilisent maintenant (1,112 ; -0,022) pour ST2 et (1,801 ; -0,462) pour ST4/6/7. Statut : **Proxy**, provisoire (essence pionnière à pores diffus, mesurée dans les mêmes fouilles que Picea).

Valeurs de T à 1 / 2 / 4 m :

| | ST2 | ST4/6/7 |
|---|---|---|
| Picea | 0,37 / 0,23 / 0,14 | 0,43 / 0,29 / 0,20 |
| Betula | 0,48 / 0,32 / 0,20 | 0,43 / 0,363 (plateau) / 0,363 |

La loi secondaire de Betula atteint son maximum de dénominateur à D = 1,95 m : au-delà, T reste à 0,363, alors que celle de Picea continue de décroître.

**Pourquoi une loi par axe.** Sans effilement le long de la racine, une racine sans latérale garde un rayon constant et le major/total est trop haut. Essais d'origine (sol 1, Picea / Quercus / Aesculus) :

| Option | Major/total | Remarque |
|---|---|---|
| A : pointes au rayon primaire, sans effilement | 26 % / 84 % / 18 % | Quercus aberrant |
| B : `taper_per_cm` = 0,004 | 28 % / 36 % / 41 % | |
| B : `taper_per_cm` = 0,008 | 13 % / 16 % / 21 % | rayons médians ST4/6/7 de 0,04-0,09 cm |
| C : loi de Kalliokoski par axe | 12 % / 14 % / 17 % | retenue, puis affinée (§6) |

## 5. ST1 neutre

ST1 (tronçon de collet chez Picea et Aesculus, pivot chez Quercus) reste sur la récurrence par nœud, sans loi d'effilement. Aucune loi de pivot n'est sourcée. Chez Quercus : rayon 13,2 cm au collet, puis ST1 à 0,08 fois cela à 1 m (crayon) : sous la jonction des ST2, le pivot ne porte que ses sinkers. Impact sur les cibles : au plus une vingtaine de voxels dans la colonne centrale, moins de 7 % des voxels major (mesuré avant le proxy Betula).

Le point de départ était la loi principale appliquée à ST1 aussi : Σ D² des ST2 / D² du collet de 0,56 (Picea), 0,30 (Quercus), 0,62 (Aesculus), contre 0,86 à 1,87 mesuré. En sortant ST1 de cette loi, on passe à 1,00 / 1,05 / 1,12 (valeurs d'alors).

Observation indirecte : Di Iorio et al. 2005 (*Ann. Bot.* 95:351-361, *Quercus pubescens*) notent que le pivot s'efface devant les racines latérales supérieures chez les feuillus, et que « taproots and all horizontally orientated roots tapered quite rapidly ». Cela va dans le sens d'un pivot fin à 1 m, sans donner de loi. Statut : **Choix**.

## 6. Schéma par organe (schéma B)

Pour chaque organe ST2, ST4, ST6, ST7 : `r(D) = B · T(D)`, D en m depuis le premier nœud de l'organe. B est le plus petit rayon de base qui laisse, à chaque nœud, une section au moins égale à celle de la pointe et des latérales rattachées en aval :

`B = max sur les nœuds de (r_pointe^Δ + Σ c_k^Δ)^(1/Δ) / T(D)`, somme sur les latérales rattachées en D_k ≥ D,

avec c_k = B_k pour une latérale structurale et son rayon primaire pour une fine. Les organes sont traités du plus récent au plus ancien (les identifiants suivent l'ordre de création).

Avec la récurrence par nœud, l'effilement mesuré était trop raide par rapport à la loi (Aesculus avant le schéma B : ST4/6/7 à 1 m de 0,29 / 0,42 / 0,30, contre T de 0,43). Dans le schéma B, le profil de chaque organe est B·T(D) par construction et Σ D² reste de 0,97 à 1,00 (testé aussi sur arbres synthétiques). Statut : **Choix**, appuyé sur le §4.

## 7. Racines fines à leur rayon primaire

Dans la somme de section, les fines (ST3, ST5) entrent à leur rayon primaire. Un drapeau `fine_roots_in_sum` a été testé puis retiré : Quercus (a = 0,023) sans les fines dans la somme : s = 89, effilement ST4/6 de 0,20/0,27, major/total inchangé ; les exclure dégrade l'échelle de fusion sans régler le major/total. Statut : **Choix** (essai).

## 8. Fusion quadratique

`fused² = p² + s · (r_murray² − p²)` pour les structurales (p = rayon primaire), avec s choisi pour que le collet vaille la loi d'âge (§2). Exposant 2,0.

Mesure sur un Picea de 120 ans (rayon médian par ordre 0 à 3) : la loi d'âge donne 4,785 / 4,423 / 4,255 / 4,231 cm, plat, car elle ne dépend que du temps ; la section conservée donne 0,542 / 0,192 / 0,098 / 0,060 cm, bonne hiérarchie mais collet 6 fois trop fin, car bâtie sur les rayons primaires de CPlantBox. On garde le profil de la section conservée et on l'ancre sur le collet de la loi d'âge.

**s > 1 est structurel**, et dépend des lois d'effilement : à structure égale, un effilement moins raide réduit le rayon de base B demandé par la section, donc le collet de la section conservée, donc augmente s. Avec le proxy Betula, s passe de 5,36 à 11,73 (Quercus) et de 3,00 à 8,71 (Aesculus) ; Picea reste à 1,70. Avec l'option B (§2, §13), s à 120 ans vaut 12,6 (Picea), 85 (Quercus) et 59 (Aesculus), et il croît avec l'âge (Picea 0,73 à 5 ans, 1,12 à 20 ans, 3,16 à 50 ans) : le nombre de segments varie peu entre 50 et 120 ans (Picea 15 367 → 15 914 ; Quercus 35 572 → 36 139 ; Aesculus 29 013 → 33 976) alors que le collet suit le DBH.

**Alternative écartée : homothétie sur l'aire entière** (`fused² = s · r_murray²`). Elle donnerait un effilement exactement T, mais gonflerait les pointes de √s (×1,3 Picea, ×1,7 Aesculus, ×2,3 Quercus avant le proxy Betula ; ×3,4 et ×3,0 maintenant), éloignées du seuil de 2 mm, et ferait monter les masses.

**Argument à revoir.** Jusqu'ici l'écart d'effilement de ST4/6/7 (mesuré 0,27 / 0,32 / 0,37 contre 0,43 attendu) était jugé sans effet sur les cibles, parce que ces organes restaient sous le seuil major (rayon ≥ 1 cm, diamètre ≥ 2 cm). Avec le proxy Betula, l'écart est plus grand (Quercus 0,21 / 0,26 / 0,30 ; Aesculus 0,34 / 0,35 / 0,31) et les rayons montent : ST4 maximum 1,84 cm (Quercus) et 1,71 cm (Aesculus), p90 de 0,79 et 0,91 ; ST6 maximum 1,04 et 1,31 cm. L'argument ne tient plus pour ST4 ni ST6 des feuillus. L'écart vient de la forme additive sur l'excès d'aire : `r'(D)/r'(0) ≈ √((r(D)² − p²)/(r(0)² − p²))`, pire pour les organes sans latérale, les grands p et les grands s. Statut : **Choix**, **À recontrôler** pour les feuillus.

## 9. Paramètres XML et nombre de ST2

Le `a` de CPlantBox est le rayon primaire : plancher et pointe dans le schéma B.

| Espèce | ST1 | ST2 | ST4 | ST6 | ST7 |
|---|---|---|---|---|---|
| Quercus | 0,40 (pivot) | 0,10 (dev 0,01) | 0,10 (dev 0,01) | 0,10 (dev 0,01) | 0,05 (dev 0,01) |
| Aesculus | 1,40 | 0,10 | 0,10 | 0,10 | 0,05 |
| Picea | 0,20 | 0,25 | 0,08 | 0,09 | 0,05 |

Fines : Quercus ST3/ST5 0,0225, Aesculus 0,045 / 0,025, Picea 0,035 / 0,0145.

- **Structurales de Quercus et Aesculus à 0,10 cm** : le seuil de 2 mm de diamètre des racines grossières est **Sourcé** (Kalliokoski 2008 : excavation jusqu'à 2 mm, « lower limit for the coarse root system », et même seuil en 2010) ; son application aux feuillus est un **Choix**. Avant : Quercus 0,023, valeur du rapport de sourçage (Pagès 1995, jeunes chênes ; non revérifiée). À 0,023 : s = 36,7 ; avec 0,10 : s = 8,6, puis 5,36 avec 3 règles ST2 (avant le proxy Betula).
- **ST7 à 0,05** (3 espèces) : **Choix**, non sourcé.
- **Nombre de ST2 de Quercus** : 3 règles à 0,60 sur les 5 premiers points du pivot (`where="0,1,2,3,4"`, ruleId 0, 4, 5), soit 9,3 ST2 par arbre (5,3 avec 2 règles). Effet mesuré (avant le proxy Betula) : s de 8,6 à 5,36, major/total de 29 % à 21 %.

**Ce que disent les sources sur le nombre de racines proximales (statut : Proxy).**

| Source | Espèce | Nombre par arbre |
|---|---|---|
| Kalliokoski 2008, Tableau 3 (hors adventices) | Picea | 8 à 21 (10 / 11 / 21 / 12 / 8) |
| idem | Betula pendula | 11 à 28 (11 / 20 / 25 / 28 / 16) |
| idem | Pinus sylvestris | 9 à 22 |
| Kalliokoski 2010, Fig. 9 (simulations) | Picea sapling / pole / mature | 9 / 14 / 21 |
| Di Iorio 2005, Fig. 3 | *Quercus pubescens*, 10 arbres de 25-50 ans, DBH 7-18 cm | 17 à 36 racines de premier ordre (excavation jusqu'à 1 cm) |

La plage « 8 à 21 » est celle de **Picea seul** (l'ancien texte la disait mesurée sur Picea et Betula). Le nombre augmente avec le stade (Picea 10 → 11 → 21, Betula 11 → 20 → 25 de sapling à mature MT). Chez *Q. pubescens*, il n'est pas corrélé au DBH et il est plus élevé sur pente faible (P < 0,01). Dans le code : Picea 12,0 (dans la plage), Quercus 9,3 et Aesculus 7,7 (sous les plages de Betula et de *Q. pubescens*). Les définitions diffèrent (premier ordre ≥ 1 cm contre proximales > 2 mm, adventices exclues), donc ce n'est pas un test.

## 10. Plafonds de rayon

Plafond de **40 cm pour les 3 espèces** (avant l'option B : 20 cm pour Picea et 30 cm pour les feuillus, sans base). Simple garde-fou appliqué par `enforce_continuity`, **non sourcé**. Avec l'option B, le rayon de collet à 120 ans vaut 35,1 cm + r0 : 35,3 cm (Picea), 35,5 cm (Quercus) et 36,6 cm (Aesculus, r0 ≈ 1,5 cm). Il reste sous le plafond à tous les âges testés (5, 20, 50 et 120 ans) ; un plafond de 20 ou 30 cm aurait écrêté le collet. Avec c = 1,2, le collet vaudrait 42,3 cm : le plafond de 40 cm l'écrête (constaté sur Quercus et Aesculus, collet à 40,00 cm). Si c est relevé, le plafond doit l'être. Statut : **Choix**.

## 11. Tolérance du fond de grille

`FLOOR_TOLERANCE_CM = 1,0` dans `grid.py` : les points jusqu'à 1 cm sous le fond (306 cm) sont rangés dans la dernière couche au lieu d'être comptés hors grille. CPlantBox arrête une racine au plancher de la boîte de sol, mais son dernier segment le dépasse de 0,1 à 0,26 cm. Ces points étaient perdus : environ 36 % (Quercus) et 16 % (Aesculus) de la longueur de la couche du fond. Après correction : 0,0 échantillon hors grille par le fond pour les 3 espèces. `stamp_centreline`, `stamp_radius` et `accumulate_volume` passent par `locate_points`. Statut : **Choix**.

## 12. Architecture : sources

- **Quercus** : Drexhage, Chauvière, Colin & Nielsen 1999, *CJFR* 29:600-608, « Development of structural root architecture and allometry of *Quercus petraea* » : référence confirmée, mais l'étude porte sur *Q. petraea* (arbres jeunes de 20 et 28 ans), pas *Q. robur* : proxy congénère.
- **Di Iorio, Lasserre, Scippa & Chiatante 2005**, *Ann. Bot.* 95:351-361, doi 10.1093/aob/mci033, *Q. pubescens* adulte (10 arbres de 25 à 50 ans, excavés à la main sur 1,5-2 m de rayon, 1 m de profondeur, jusqu'à 1 cm) : taproot plus racines horizontales superficielles, comportement « intermédiaire entre système pivotant et superficiel » ; la plupart des racines à moins de 0,6 m (excavation limitée à 1 m) ; la racine la plus profonde mesurée a une section de 6 à 10 % de celle de la base du tronc ; le DBH prédit le volume racinaire mais pas la longueur ni le nombre de racines. Sol argileux compact, sur pente : à ne pas extrapoler sans réserve à *Q. robur* en sol urbain.
- **Aesculus** : proxy *Fagus sylvatica*, aucune source examinée : **À recontrôler**. Plant Soil 2005 (s11104-005-3503-x) et Danjon (3D) : non vérifiés.
- **Picea** : profondeur maximale simulée 155 ± 19 cm (120 ans) ; Kalliokoski 2008, Tableau 4, Picea mature MT (55 ans) : profondeur maximale 1,61 m, moyenne des maxima 0,56 ± 0,37 m ; étendue radiale moyenne 8,7 m (maximale 10,1 m). Ordre de grandeur cohérent.
- **Betula mature MT** (proxy des feuillus) : profondeur maximale 2,65 m, moyenne 0,74 m ; étendue radiale 11,6 m (max. 20,5 m). Les feuillus simulés atteignent tous le plancher de 306 cm (profondeur moyenne d'occupation 114 cm) : plus profond que Betula et que *Q. pubescens* (§14.7).

## 13. Résultats de validation

Conditions : sandbox sol 1, sans rue, graine 7, 50 arbres (mesures détaillées sur 3 arbres), option B (c = 1,0), proxy Betula pour les feuillus. La géométrie est celle d'avant l'option B (racines par sous-type, segments, profondeurs, tortuosités, hors grille : Picea 15, Quercus 4, Aesculus 0 sur 50 arbres).

**À 120 ans.**

| Indicateur | Picea | Quercus | Aesculus |
|---|---|---|---|
| Collet mesuré (cm) ; attendu DBH/2 = 35,11 + r0 | 35,31 | 35,54 (max) | 36,62 (max 36,67) |
| Échelle s au collet (médiane, min-max) | 12,59 (11,36-15,30) | 85,12 (68,39-88,40) | 58,96 (54,25-66,57) |
| Σ D² ST2 / D² collet | 0,99 | 0,97 | 0,98 |
| ST2 le plus épais / collet | 0,49 | ≤ 0,46 | 0,47 |
| Masse occupation | 0,01171 | 0,01387 | 0,01595 |
| Masse major (part) | 0,00577 (49 %) | 0,01020 (74 %) | 0,00743 (47 %) |
| Voxels ≥ 0,99 (sur 139 264) | 20 | ≈ 28 | 24 |
| ST2 effilement à 1 / 2 / 4 m | 0,36 / 0,21 / 0,11 | 0,47 / 0,31 / 0,18 | 0,48 / 0,31 / n.d. |
| ST4 / ST6 / ST7 à 1 m | 0,33 / 0,24 / 0,27 | 0,17 / 0,23 / 0,28 | 0,33 / 0,34 / 0,29 |
| ST1 à 1 m | n.d. | 0,08 | n.d. |
| Rayon max ST2 (cm) | 17,30 | 16,42 | 17,22 |
| Rayon max ST4 / ST6 / ST7 (cm) | 1,71 / 1,21 / 0,75 | 4,95 / 2,77 / 1,71 | 4,45 / 3,34 / 1,67 |
| Fond / suivante, longueur (occupation, major) | n.d. | 2,66 (1,75 ; 1,36) | 1,66 (1,12 ; 1,27) |

**Selon l'âge** (collet médian en cm ; s médian ; Σ D² ; masse d'occupation et part major).

| Âge | DBH/2 | Picea | Quercus | Aesculus |
|---|---|---|---|---|
| 5 ans | 2,36 | 2,55 ; s 0,73 ; 1,03 ; 0,00154 (6 %) | 2,74 ; s 0,95 ; 0,96 ; 0,00525 (4 %) | 3,86 ; s 19,2 ; 0,65 ; 0,00060 (38 %) |
| 20 ans | 7,66 | 7,86 ; s 1,12 ; 1,00 ; 0,00694 (11 %) | 8,05 ; s 4,63 ; 0,97 ; 0,00955 (16 %) | 9,17 ; s 16,8 ; 0,91 ; 0,00537 (29 %) |
| 50 ans | 16,68 | 16,88 ; s 3,16 ; 0,99 ; 0,00994 (26 %) | 17,07 ; s 20,0 ; 0,97 ; 0,01124 (43 %) | 18,19 ; s 19,6 ; 0,97 ; 0,01168 (28 %) |
| 120 ans | 35,11 | 35,31 ; s 12,6 ; 0,99 ; 0,01171 (49 %) | 35,54 ; s 85 ; 0,97 ; 0,01387 (74 %) | 36,62 ; s 59 ; 0,98 ; 0,01595 (47 %) |

Profondeur maximale (cm, moyenne sur 50 arbres) à 5 / 20 / 50 / 120 ans : Picea 65 / 134 / 154 / 155 ; Quercus 288 / 306 / 306 / 306 ; Aesculus 84 / 232 / 305 / 306. Aucune saturation à aucun âge (9 à 28 voxels ≥ 0,99 sur 139 264).

**Sensibilité à c = 1,2** (120 ans ; collet attendu 42,13 cm + r0). Picea : collet 42,33 cm, s 18,09 (× 1,44), Σ D² 0,99, masse 0,01226 (+ 4,7 %), major 54 %. Quercus et Aesculus : collet écrêté à 40,00 cm par le plafond (§10), donc Σ D² (1,10 ; 1,17) et parts major (79 % ; 59 %) faussés ; masses 0,01481 (+ 6,8 %) et 0,01682 (+ 5,5 %), à lire en qualitatif.

Avant l'option B (120 ans) : Picea s 1,70, masse 0,01000, major 0,00178 (18 %) ; Quercus s 11,73, masse 0,01091, major 0,00340 (31 %) ; Aesculus s 8,71, masse 0,01327, major 0,00277 (21 %). Avant le proxy Betula (feuillus) : Quercus s 5,36, masse 0,01055, major 0,00223 (21 %) ; Aesculus s 3,00, masse 0,01287, major 0,00218 (17 %). L'effilement de ST2 mesuré (0,47-0,48 / 0,31 / 0,18) colle à T (0,48 / 0,32 / 0,20).

**Contrôles indépendants** : s, masses, major/total, profil du pivot, nombre de racines proximales, rayons maximaux, T de Kalliokoski 2010 (Tableau 4). Σ D² ≈ 1, effilement ST2 = T et collet = DBH/2 + r0 sont vrais par construction : ce ne sont pas des tests de réalisme, mais des tests de la chaîne (loi d'âge, schéma B, fusion, continuité).

## 14. Limites connues et points à recontrôler

1. **Collet et DBH** : option B appliquée et validée (§2, §13) ; c = 1,0 reste non sourcé.
2. **α** : 0,6 n'est donné par aucune série de l'article ni soutenu par Thamm 2019 ; α = 0,85 (allométrie du projet) est proche de α ≈ 1,0 des séries (§2).
3. **Feuillus** : k, α et plafond communs aux 3 espèces (allométrie du projet, §2) ; effilement par proxy Betula ; Δ = 2 sourcé seulement pour Picea et Betula.
4. **s élevé à 120 ans** (12,6 / 85 / 59 avec l'option B) : l'excès de section au collet imposé par le DBH est s fois celui que donnent les rayons primaires de la simulation. L'architecture simulée ne s'étoffe plus guère après 50 ans (nombre de segments, §8) alors que le DBH continue de croître. Limite assumée, sans ajuster les proxys pour la réduire.
5. **Effilement de ST4/6/7 sous T** : l'argument « sous le seuil major » ne tient plus pour ST4/ST6 des feuillus (§8).
6. **Pivot de Quercus en crayon** (§5) et loi de pivot non sourcée.
7. **Fond de grille** : longueur du fond / suivante de 2,66 chez Quercus (fond issu de ST7 à 52 % et ST2 à 33 %), 1,66 chez Aesculus (ST6 72 %, ST7 28 %), rien chez Picea. En regard : profondeur moyenne de Betula mature 0,74 m (maximum 2,65 m) et *Q. pubescens* surtout à moins de 0,6 m ; les feuillus simulés sont plus profonds. À traiter avec l'affinage des XML (profondeur de ST7 et ST2 de Quercus, de ST6 et ST7 d'Aesculus), ou par un masque de la dernière couche à l'entraînement.
8. **Loi d'effilement unique pour tous les âges** (peuplement mature) alors que l'effilement est plus raide chez les jeunes (§4), et nombre de ST2 constant alors qu'il croît avec l'âge (§9) : Picea 12,0, Quercus 9,3 et Aesculus 7,3-7,7 à 5 ans comme à 120 ans. Aux jeunes âges : ST1 d'Aesculus (1,40 cm) donne un collet de 3,86 cm à 5 ans, soit 1,6 fois DBH/2, et Σ D² tombe à 0,65 (0,91 à 20 ans) ; Quercus atteint déjà 288 cm de profondeur à 5 ans et le plancher de 306 cm à 20 ans.
9. **Nombre de ST2** de Quercus (9,3) et d'Aesculus (7,7) sous les plages de Betula et de *Q. pubescens*.
10. **Petit échantillon** (3 arbres par espèce pour les mesures détaillées).
11. **Tableau 7 de Kalliokoski 2008** : incohérences internes (§4) ; **Trees 2010** : les p et q par ordre (Tableau 3) ne sont pas utilisés dans le code.
12. **Âge de simulation** : pour les essais à 5, 20 et 50 ans, le `simulationTime` du bloc `<seed>` des XML a été ajusté à la main à âge × 365 jours (43 800 pour 120 ans), ce qui explique les sha différents des `_summary.txt` ; le XML commité doit rester à 43 800. La façon dont l'âge d'un arbre du dataset arrive à CPlantBox (`--age`, `attributes.py`, XML) est à vérifier dans `build.py` avant l'étape 4.
13. **Essai c = 1,2** : le plafond de 40 cm est resté actif pour Quercus et Aesculus ; seul le résultat de Picea est exploitable (§10, §13).

## 15. Reste à faire

- Commiter la croissance secondaire (code, XML de Quercus et d'Aesculus, ce document), puis ne plus toucher à cette partie.
- Partie B, autre commit : affinage des XML par tranches d'âge (2, 5, 10, 20, 50, 120 ans), fond de grille, Quercus trop profond aux jeunes âges, ST1 d'Aesculus trop épais aux jeunes âges (§14.8), nombre de ST2 (option).
- Étape 4 (`build_dataset_v3.py`), puis contrôle avec rue. Vérifier comment l'âge arrive à CPlantBox (§14.12) ; tester qu'une scène lancée seule et la même scène lancée après une autre donnent le même résultat.
- Documentation : partie littérature (§16) ; de légers ajustements du code ou des XML sont possibles si des sources pertinentes apparaissent.
- Perspective (ancien Stage 3) : intégrer la croissance secondaire dans `Root::simulate(dt)` de CPlantBox pour que le diamètre rétroagisse sur la conductance axiale (Kx ∝ r⁴) et l'élongation, comme OpenSimRoot (Postma et al. 2017, *New Phytol.* 215(3):1274-1286).

## 16. Références (statut après vérification)

| Référence | Statut |
|---|---|
| Kalliokoski, Nygren & Sievänen 2008, *Silva Fennica* 42(2):189-210 (silvafennica.fi/pdf/252) | Texte relu : Éq. 2, Tableaux 1, 3, 4, 7 confirmés ; réserves §4 |
| Kalliokoski, Sievänen & Nygren 2010, *Trees* 24:219-236, doi 10.1007/s00468-009-0393-1 | PDF relu : Éq. 5-6, Tableaux 2-4 |
| Kalliokoski, thèse, *Dissertationes Forestales* (dissertationesforestales.fi/pdf/1907) | Lue en partie ; année et numéro du volume à confirmer |
| Di Iorio, Lasserre, Scippa & Chiatante 2005, *Ann. Bot.* 95:351-361 | PDF relu |
| Drexhage, Chauvière, Colin & Nielsen 1999, *CJFR* 29:600-608 | Référence confirmée (*Q. petraea*) ; texte non lu |
| Drexhage & Gruber 1998, *CJFR* 28:13-22, *Picea abies* de 40 ans (Harz) | Référence confirmée par la liste de Di Iorio 2005 ; texte non lu |
| Oppelt, Kurth & Godbold 2001, *Tree Physiol.* 21:117-128 | Référence confirmée ; résumé seulement |
| Thamm et al. 2019, *R. Soc. Open Sci.* 6:190126 | Existe, mais *Arabidopsis* : ne soutient pas α |
| Puhe 2003, *For. Ecol. Manag.* 175:253-273, « Growth and development of the root system of Norway spruce (*Picea abies*) in forest stands – a review » | Titre corrigé ; ne donne pas k ni α |
| Postma et al. 2017, *New Phytol.* 215(3):1274-1286 | Pages corrigées (l'ancien texte disait 214:1244-1254) |
| Grabosky et al. 2025, *Arboric. Urban For.* 51(1):14-28 | Titre et pages confirmés ; contenu non vérifié |
| Danjon, Fourcaud & Bert 2005, « Root architecture and windfirmness of mature *Pinus pinaster* » | Titre trouvé ; revue non confirmée (l'ancien « Ann. For. Sci. 62:69-82 » est introuvable) |
| Schnepf et al. 2018 ; Shinozaki 1964 ; McMahon & Kronauer 1976 ; Pagès 2014 ; Murray 1926 ; Eloy 2011 | Non revérifiées |

## 17. Contenu retiré de `secondary_root_growth_math.md`

- Table de priors par espèce (k de 0,015 à 0,04 pour α = 0,5) : ces k ne figurent dans aucune des publications citées (Drexhage 1999, Puhe 2003, proxy *Fagus*) ; ce sont des priors maison, non comparables à k = 0,021 / α = 0,6.
- Justification de α par Thamm 2019 et exemple « 0,1 + 0,03·t^0,5 = 3,7 cm à 40 ans, cohérent avec *Q. petraea* à 20-28 ans » : non soutenus (§2).
- Forme de Gompertz « recommandée pour les vieux arbres » et critère « ratio pointe/base < 0,5 » : jamais sourcés ni utilisés.
- Fourchettes de SGC (0,7-0,95) et de Δ par type racinaire (2,0-2,3 ; 2,5 ; 3,0) : non vérifiées ; Δ = 2 est maintenant sourcé (§3).
- Références erronées corrigées : Drexhage & Gruber (1998, pas 1999 ; l'ancien texte donnait en plus deux paginations différentes), Puhe (titre), Postma (pages), Danjon (titre).
- Conservés : le contexte (§0), la chaîne de post-traitement (§1), la perspective CPlantBox (§15). Le pipe model et la règle de da Vinci × SGC, d'abord gardés comme témoins, sont supprimés du code (§1).
