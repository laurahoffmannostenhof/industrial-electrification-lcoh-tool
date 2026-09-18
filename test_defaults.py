"""Checks on the sourced defaults.

These are not tests of the maths. They guard the documentation contract: every
figure either carries a source id that exists, or is explicitly unsourced; the
price components add up to the published totals they were derived from; and
the relief mechanisms produce the values the schemes actually pay.
"""

from math import isclose

import defaults
from defaults import COUNTRIES, SOURCES, TECHNOLOGIES, UNSOURCED


def test_every_source_id_resolves():
    def check(sid, where):
        assert sid == UNSOURCED or sid in SOURCES, f"{where} cites unknown source {sid!r}"

    for cname, c in COUNTRIES.items():
        for key in ("elec_commodity", "elec_network", "gas_commodity", "carbon_price",
                    "capex_grant", "fx"):
            check(c[key].source, f"{cname}.{key}")
        for lv in c["elec_levies"]:
            check(lv.source, f"{cname}.{lv.name}")
        for r in c["reliefs"]:
            check(r.source, f"{cname}.{r.id}")
    for tname, t in TECHNOLOGIES.items():
        for key in ("capex", "opex_per_mwh", "eff", "life", "util"):
            check(t[key].source, f"{tname}.{key}")
    for key in ("capex", "opex_per_mwh", "eff", "life", "util"):
        check(defaults.BASELINE[key].source, f"baseline.{key}")


def test_every_source_has_a_url_and_a_period():
    for sid, s in SOURCES.items():
        assert s.url.startswith("https://"), sid
        assert s.period, sid
        assert s.publisher, sid


def test_german_components_reconcile_to_bdew():
    """9.50 commodity + 6.10 network + 1.597 levies = 17.2 ct/kWh, the BDEW
    total for the 160 MWh to 20 GWh medium-voltage band."""
    total = defaults.market_delivered_elec("Germany")
    assert isclose(total, 17.2, abs_tol=0.05), total


def test_uk_components_reconcile_to_desnz():
    """Components sum to the DESNZ Medium-band delivered price of 24.458 p/kWh
    excluding CCL. The CCL itself is carried as a separate levy line, so the
    sum here includes it and lands slightly above."""
    c = COUNTRIES["UK"]
    ccl = next(l.value for l in c["elec_levies"] if l.name == "Climate Change Levy")
    excl_ccl = defaults.market_delivered_elec("UK") - ccl
    assert isclose(excl_ccl, 24.458, abs_tol=0.05), excl_ccl


def test_industriestrompreis_pays_the_published_amount():
    """(reference - target) on 50% of volume. At the 2026 reference price of
    8.744 ct/kWh that is 1.87 ct/kWh, not the 2.90 an earlier version produced
    by using the user's own commodity price as the reference."""
    r = next(x for x in COUNTRIES["Germany"]["reliefs"] if x.id == "industriestrompreis")
    value = (r.params["reference"] - r.params["target"]) * r.params["coverage"]
    assert isclose(value, 1.872, abs_tol=0.005), value
    assert not r.default_on, "eligibility is sectoral; this must not default on"


def test_eii_exemption_removes_the_named_levies():
    r = next(x for x in COUNTRIES["UK"]["reliefs"] if x.id == "eii_supercharger")
    names = {l.name for l in COUNTRIES["UK"]["elec_levies"]}
    for n in r.params["levies"]:
        assert n in names, f"{n} is not a levy line, so it cannot be exempted"
    removed = sum(l.value for l in COUNTRIES["UK"]["elec_levies"] if l.name in r.params["levies"])
    network = COUNTRIES["UK"]["elec_network"].value * r.params["network_share"]
    total = removed + network
    # Government states GBP 65-87/MWh for the combined package.
    assert 6.0 < total < 9.5, total
    assert not r.default_on


def test_all_reliefs_default_off():
    for cname, c in COUNTRIES.items():
        for r in c["reliefs"]:
            assert not r.default_on, f"{cname}.{r.id} defaults on"


def test_relief_kinds_are_implemented():
    for c in COUNTRIES.values():
        for r in c["reliefs"]:
            assert r.kind in {"reference_topup", "exemption", "flat"}, r.kind


def test_uk_carbon_price_defaults_to_zero():
    """Most sites in this consumption band are below the 20 MW UK ETS
    threshold, so a non-zero default would tax them wrongly."""
    assert COUNTRIES["UK"]["carbon_price"].value == 0.0


def test_uk_capex_grant_defaults_to_zero():
    """The IETF closed with no successor."""
    assert COUNTRIES["UK"]["capex_grant"].value == 0.0


def test_german_carbon_price_is_the_cleared_auction_price():
    assert COUNTRIES["Germany"]["carbon_price"].value == 65.0


def test_heat_pump_capex_and_cop_come_from_the_same_source_row():
    """The earlier defaults paired a medium-heat CAPEX with a high-heat COP."""
    med = TECHNOLOGIES["Heat Pump (medium heat, to 150 °C)"]
    hot = TECHNOLOGIES["Booster Heat Pump (steam, above 150 °C)"]
    assert med["capex"].value < hot["capex"].value
    assert med["eff"].value > hot["eff"].value
    for t in (med, hot):
        assert t["capex"].source == t["eff"].source == "ecco"


def test_us_jurisdictions_are_flagged_unsourced():
    for name in ("USA - California", "USA - Texas"):
        assert COUNTRIES[name]["sourced"] is False
        assert COUNTRIES[name]["elec_commodity"].source == UNSOURCED


def test_unsourced_report_is_not_empty_and_lists_the_us():
    rows = defaults.unsourced_figures()
    assert rows
    assert any(c.startswith("USA") for c, _ in rows)


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            passed += 1
            print(f"  ok  {name}")
    print(f"\n{passed} tests passed")
