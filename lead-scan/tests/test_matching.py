from runner.matching import (
    ExistingRecord,
    MatchIndex,
    RunDeduper,
    email_domain,
    name_keys,
    name_similarity,
    normalize_domain,
    normalize_kvk,
    normalize_name,
)


def test_normalize_domain_variants():
    assert normalize_domain("https://www.Voorbeeld.nl/over-ons?x=1") == "voorbeeld.nl"
    assert normalize_domain("www.albeda.nl/") == "albeda.nl"
    assert normalize_domain("http://landstedembo.nl") == "landstedembo.nl"
    assert normalize_domain("https://www.hva.nl/faculteit/ft/over-techniek.html") == "hva.nl"
    assert normalize_domain("werkenbij.voorbeeld.nl") == "voorbeeld.nl"
    assert normalize_domain("shop.example.co.uk") == "example.co.uk"
    assert normalize_domain("voorbeeld.nl:8080") == "voorbeeld.nl"


def test_normalize_domain_rejects_garbage_platforms_and_own_domain():
    assert normalize_domain("under construction") is None
    assert normalize_domain("") is None
    assert normalize_domain(None) is None
    assert normalize_domain("https://schoonderwolf.homerun.co/") is None
    assert normalize_domain("https://www.linkedin.com/company/x") is None
    assert normalize_domain("www.cobracrm.nl") is None


def test_email_domain_strips_sandbox_suffix_and_generic_providers():
    assert email_domain("henri@apollovredestein.com.invalid") == "apollovredestein.com"
    assert email_domain("iemand@gmail.com") is None
    assert email_domain("iemand@hotmail.nl.invalid") is None
    assert email_domain("support+apollo@cobracrm.nl.invalid") is None
    assert email_domain("geen-email") is None


def test_normalize_kvk():
    assert normalize_kvk("01169476") == "01169476"
    assert normalize_kvk("5047024") == "05047024"  # voorloopnul weggevallen
    assert normalize_kvk("4147 6190") == "41476190"
    assert normalize_kvk("123") is None
    assert normalize_kvk("N/A") is None
    assert normalize_kvk("12345678") is None  # bekende testwaarde
    assert normalize_kvk("HRB 105261 B") is None


def test_normalize_name_strips_legal_forms_and_accents():
    assert normalize_name("Stichting De Zonnebloem") == "zonnebloem"
    assert normalize_name("Bynder B.V.") == "bynder"
    assert normalize_name("C.S.C. Ceelen Sport Constructies B.V.") == "csc ceelen sport constructies"
    assert normalize_name("Bartiméus Fonds") == "bartimeus fonds"
    assert normalize_name("Landstede Groep") == normalize_name("Stichting Landstede")


def test_name_keys_aliases():
    assert name_keys("Stichting Kinderen Kankervrij (KiKa)") == {"kinderen kankervrij", "kika"}
    assert {"regio college", "talland"} <= name_keys("Regio College / Talland")


def test_name_similarity():
    assert name_similarity("zonnebloem", "zonnebloem") == 1.0
    assert name_similarity("landstede", "landstede vo") >= 0.82
    assert name_similarity("zonnebleom", "zonnebloem") >= 0.82
    assert name_similarity("eo", "eo media") == 0.0  # te kort woord voor deelnaam
    assert name_similarity("kwartelkoning logistiek", "zonnebloem") < 0.82


def _index():
    return MatchIndex(
        [
            ExistingRecord("001A", "Account", "Stichting De Zonnebloem", owner_id="005X", type="Customer",
                           excluded=True, exclusion_reason="Account Type Customer", domains={"zonnebloem.nl"}),
            ExistingRecord("001B", "Account", "Realiance", owner_id="005Y", type="Prospect",
                           domains={"realiance.nl"}, kvks={"12312312"}),
            ExistingRecord("00QC", "Lead", "Motivaction international", owner_id="005Z", status="New",
                           domains={"motivaction.nl"}),
            ExistingRecord("001D", "Account", "Stichting Kinderen Kankervrij (KiKa)", type="Customer",
                           excluded=True, exclusion_reason="Account Type Customer"),
        ]
    )


def test_check_layer1_on_domain_name_and_alias():
    idx = _index()
    assert idx.check("Iets Anders", "https://www.zonnebloem.nl/doneren").outcome == "blocked_l1"
    assert idx.check("De Zonnebloem", None).outcome == "blocked_l1"
    assert idx.check("KiKa", None).outcome == "blocked_l1"


def test_check_layer2_existing_records_and_task_target():
    idx = _index()
    res = idx.check("Realiance B.V.", None)
    assert res.outcome == "blocked_l2"
    assert res.task_target().id == "001B"
    assert idx.check("Onbekend", None, kvk="12312312").outcome == "blocked_l2"
    lead = idx.check("Iets", "motivaction.nl")
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


def test_check_doubt_and_clear():
    idx = _index()
    doubt = idx.check("Zonnebleom", None)
    assert doubt.outcome == "doubt"
    assert doubt.matches[0].record.id == "001A"
    assert idx.check("Kwartelkoning Logistiek", "kwartelkoning.nl").outcome == "clear"


def test_run_deduper():
    d = RunDeduper()
    assert not d.seen("Voorbeeld B.V.", "voorbeeld.nl")
    assert d.seen("Stichting Voorbeeld", None)
    assert d.seen("Heel Anders", "https://www.voorbeeld.nl")
    assert not d.seen("Nieuw", "nieuw.nl")
