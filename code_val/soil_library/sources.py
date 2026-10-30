"""Every reference the library cites. An ESTIMATE names the data meant to replace it."""
from soil_library.values import Provenance, Source

SOILGRIDS_BRUSSELS = Source(
    Provenance.PRIOR, "SoilGrids 2.0 (Poggio et al. 2021): Sonian Forest and Bois de la Cambre points")
SOILGRIDS_HELSINKI = Source(
    Provenance.PRIOR, "SoilGrids 2.0 (Poggio et al. 2021), Helsinki: clay 27-36 %")
NEHLS_2013 = Source(
    Provenance.PRIOR,
    "Nehls et al. 2013, Mekiffer 2010 (Berlin): fragments > 2 mm, median 25 %, bricks up to 45 %")
GRABOSKY_2009 = Source(
    Provenance.PRIOR, "Grabosky et al. 2009 (CU-Soil): clay loam soil in the stone voids")
GRABOSKY_2009_DERIVED = Source(
    Provenance.DERIVED,
    "from Grabosky et al. 2009: 80/20 stone/soil by mass, whole-soil density 1.87-2.04 g/cm3")
TREE_SAND_SHEETS = Source(
    Provenance.PRIOR, "bomenzand producer sheets, Amsterdam: organic matter 3.5-5.5 %, clay 1-4 %")
FLL_SHEETS = Source(Provenance.PRIOR, "FLL-compliant product sheets: organic matter 1-4 %")
FAWB_2015 = Source(Provenance.PRIOR, "FAWB 2015, appendix C: clay + silt < 3 %")
DESIGN_DOCUMENT = Source(Provenance.PRIOR, "bibliotheque_sols_urbains.md, section 2.2")

TO_SOILGRIDS = Source(
    Provenance.ESTIMATE, "replace with SoilGrids 2.0 at natural points near the cities")
TO_GEOLOGICAL_SURVEYS = Source(
    Provenance.ESTIMATE, "replace with GTK (Finland) and Estonian geological maps")
TO_PLANTING_SPECIFICATIONS = Source(
    Provenance.ESTIMATE, "replace with the planting specifications of the cities (Brussels CCT 2015)")
TO_URBAN_SURVEYS = Source(
    Provenance.ESTIMATE,
    "replace with measured urban fills (Brussels soil health survey, NRCS New York survey)")
TO_PRODUCT_SHEETS = Source(
    Provenance.ESTIMATE, "replace with product sheets and standards of the material")
TO_SCENARIO_SURVEYS = Source(
    Provenance.ESTIMATE, "replace with field descriptions of the urban scenarios")
TO_GROUNDWATER_MAPS = Source(
    Provenance.ESTIMATE, "replace with groundwater depth maps of the cities")
TO_ERA5_LAND = Source(
    Provenance.ESTIMATE, "replace with a 1-D water balance on ERA5-Land")
