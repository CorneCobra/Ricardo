"""Alle organisatienamen en domeinen in deze tests zijn fictief."""

from runner.matching import (
    ExistingRecord,
    MatchIndex,
    RunDeduper,
    domain_fits_name,
    email_domain,
    name_keys,
    name_similarity,
    normalize_domain,
    normalize_kvk,
    normalize_name,
)


def test_normalize_domain_variants():
    assert normalize_domain("https://www.Voorbeeld.nl/over-ons?x=1") == "voorbeeld.nl"
    assert normalize_domain("www.leerhuis.nl/") == "leerhuis.nl"
    assert normalize_domain("http://duinhorstmbo.nl") == "duinhorstmbo.nl"
    assert normalize_domain("https://www.hsnoord.nl/faculteit/ft/over-techniek.html") == "hsnoord.nl"
    assert normalize_domain("werkenbij.voorbeeld.nl") == "voorbeeld.nl"
    assert normalize_domain("shop.example.co.uk") == "example.co.uk"
    assert normalize_domain("voorbeeld.nl:8080") == "voorbeeld.nl"


def test_normalize_domain_rejects_garbage_platforms_and_own_domain():
    assert normalize_domain("under construction") is None
    assert normalize_domain("") is None
    assert normalize_domain(None) is None
    assert normalize_domain("https://voorbeeld.homerun.co/") is None
    assert normalize_domain("https://www.linkedin.com/company/x") is None
    assert normalize_domain("www.cobracrm.nl") is None


def test_email_domain_strips_sandbox_suffix_and_generic_providers():
    assert email_domain("info@bandenfabriek.com.invalid") == "bandenfabriek.com"
    assert email_domain("iemand@gmail.com") is None
    assert email_domain("iemand@hotmail.nl.invalid") is None
    assert email_domain("support+test@cobracrm.nl.invalid") is None
    assert email_domain("geen-email") is None


def test_normalize_kvk():
    assert normalize_kvk("01234567") == "01234567"
    assert normalize_kvk("7654321") == "07654321"  # voorloopnul weggevallen
    assert normalize_kvk("4321 8765") == "43218765"
    assert normalize_kvk("123") is None
    assert normalize_kvk("N/A") is None
    assert normalize_kvk("12345678") is None  # bekende testwaarde
    assert normalize_kvk("HRB 105261 B") is None


def test_normalize_name_strips_legal_forms_and_accents():
    assert normalize_name("Stichting De Zilvermeeuw") == "zilvermeeuw"
    assert normalize_name("Voorbeeld B.V.") == "voorbeeld"
    assert normalize_name("A.B.C. Testbouw Constructies B.V.") == "abc testbouw constructies"
    assert normalize_name("Stichting Hélène Fonds") == "helene fonds"
    assert normalize_name("Duinhorst Groep") == normalize_name("Stichting Duinhorst")


def test_name_keys_aliases():
    assert name_keys("Stichting Kinderen Zonder Zorgen (KiZZ)") == {"kinderen zonder zorgen", "kizz"}
    assert {"regio leerhuis", "duinhorst"} <= name_keys("Regio Leerhuis / Duinhorst")
    assert name_keys("QZ") == {"qz"}  # korte, echte organisatienamen bestaan
    assert "oz" in name_keys("Stichting Omroep Zuid (OZ)")
    assert name_keys("x") == set() and name_keys("...") == set()


def test_name_similarity():
    assert name_similarity("zilvermeeuw", "zilvermeeuw") == 1.0
    assert name_similarity("duinhorst", "duinhorst vo") >= 0.82
    assert name_similarity("zilvermeuw", "zilvermeeuw") >= 0.82
    assert name_similarity("eo", "eo media") == 0.0  # te kort woord voor deelnaam
    assert name_similarity("kwartelkoning logistiek", "zilvermeeuw") < 0.82


def _index():
    return MatchIndex(
        [
            ExistingRecord("001A", "Account", "Stichting De Zilvermeeuw", owner_id="005X", type="Customer",
                           excluded=True, exclusion_reason="Account Type Customer", domains={"zilvermeeuw.nl"}),
            ExistingRecord("001B", "Account", "Vastgoedpartners Oost", owner_id="005Y", type="Prospect",
                           domains={"vastgoedpartnersoost.nl"}, kvks={"12312312"}),
            ExistingRecord("00QC", "Lead", "Marktbeeld international", owner_id="005Z", status="New",
                           email_domains={"marktbeeld.nl"}),
            ExistingRecord("00QD", "Lead", "Lumen", status="Unqualified", excluded=True,
                           exclusion_reason="recent Unqualified", email_domains={"hsrijnmond.nl"}),
            ExistingRecord("001E", "Account", "Regio Leerhuis / Duinhorst", type="Customer", excluded=True,
                           exclusion_reason="klant", email_domains={"regioleerhuis.nl", "hogeschoolnoord.nl"}),
            ExistingRecord("001D", "Account", "Stichting Kinderen Zonder Zorgen (KiZZ)", type="Customer",
                           excluded=True, exclusion_reason="Account Type Customer"),
        ]
    )


def test_check_layer1_on_domain_name_and_alias():
    idx = _index()
    assert idx.check("Iets Anders", "https://www.zilvermeeuw.nl/doneren").outcome == "blocked_l1"
    assert idx.check("De Zilvermeeuw", None).outcome == "blocked_l1"
    assert idx.check("KiZZ", None).outcome == "blocked_l1"


def test_check_layer2_existing_records_and_task_target():
    idx = _index()
    res = idx.check("Vastgoedpartners Oost B.V.", None)
    assert res.outcome == "blocked_l2"
    assert res.task_target().id == "001B"
    assert idx.check("Onbekend", None, kvk="12312312").outcome == "blocked_l2"
    lead = idx.check("Iets", "marktbeeld.nl")
    assert lead.outcome == "blocked_l2" and lead.task_target().object == "Lead"


def test_excluded_match_wins_over_existing_record():
    idx = MatchIndex(
        [
            ExistingRecord("00QL", "Lead", "Voorbeeld", domains={"voorbeeld.nl"}),
            ExistingRecord("001K", "Account", "Voorbeeld", excluded=True, exclusion_reason="klant",
                           domains={"voorbeeld.nl"}),
        ]
    )
    res = idx.check("Voorbeeld", "voorbeeld.nl")
    assert res.outcome == "blocked_l1"
    assert res.task_target() is None


def test_domain_fits_name():
    assert domain_fits_name("bandenfabriekveluwe.com", "Banden Fabriek Veluwe")
    assert domain_fits_name("regioleerhuis.nl", "Regio Leerhuis / Duinhorst")
    assert domain_fits_name("duinhorst.nl", "Regio Leerhuis / Duinhorst")
    assert domain_fits_name("hv.nl", "Hogeschool Veenstad")  # initialen
    assert domain_fits_name("zvf.nl", "ZVF Zeevogelfonds")
    assert domain_fits_name("marktbeeld.nl", "Marktbeeld international")
    assert not domain_fits_name("hogeschoolnoord.nl", "Regio Leerhuis / Duinhorst")
    assert not domain_fits_name("hsrijnmond.nl", "Lumen")
    assert not domain_fits_name("tunoord.nl", "tn")
    assert not domain_fits_name("hx.nl", "Hogeschool Veenstad")


def test_email_domain_counts_hard_only_when_it_fits_the_record_name():
    idx = _index()
    assert idx.check("Regio Leerhuis", "regioleerhuis.nl").outcome == "blocked_l1"
    other = idx.check("Hogeschool Noord", "hogeschoolnoord.nl")
    assert other.outcome == "doubt" and other.matches[0].key_type == "email_domain_unrelated"
    assert idx.check("Hogeschool Rijnmond", "hsrijnmond.nl").outcome == "doubt"


def test_check_doubt_and_clear():
    idx = _index()
    doubt = idx.check("Zilvermeuw", None)
    assert doubt.outcome == "doubt"
    assert doubt.matches[0].record.id == "001A"
    assert idx.check("Kwartelkoning Logistiek", "kwartelkoning.nl").outcome == "clear"


def test_run_deduper():
    d = RunDeduper()
    assert not d.seen("Voorbeeld B.V.", "voorbeeld.nl")
    assert d.seen("Stichting Voorbeeld", None)
    assert d.seen("Heel Anders", "https://www.voorbeeld.nl")
    assert not d.seen("Nieuw", "nieuw.nl")
