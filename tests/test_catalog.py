from app.catalog import COUNTRIES, country_rows
from app.cli import catalogue

def test_all_required_countries_present_once():
    codes=[row[0] for row in COUNTRIES]
    assert len(codes)==25
    assert len(set(codes))==25

def test_placeholders_are_not_researched_or_integrated():
    rows=country_rows()
    assert len(rows)==25
    assert all(r["verification_status"]=="Undiscovered" and r["integration_status"]=="Not Started" for r in rows)

def test_researched_catalogue_covers_each_country_with_unique_source_id():
    rows=catalogue()
    assert {r["country_code"] for r in rows}=={c[0] for c in COUNTRIES}
    ids=[r["source_id"] for r in rows]
    assert len(ids)>24 and len(set(ids))==len(ids)
