import json

from meeting import connaissances as K
from meeting.cli import main


def transcription(tmp_path):
    p = tmp_path / "v.txt"
    p.write_text("[00:00:08 → 00:00:12] La base arrière conditionne les objectifs de la nuit.\n"
                 "[00:01:40 → 00:01:45] Le chantier consiste en du renouvellement voie-ballast sur 7 kilomètres.\n"
                 "ligne parasite\n", encoding="utf-8")
    return p


def test_schema_et_import_transcription(tmp_path):
    con = K.ouvrir(str(tmp_path / "kb.sqlite"))
    n = K.importer_transcription(con, str(transcription(tmp_path)), "Chantier RVB", url="https://ex/v1",
                                 organisme="ETF", pays="FR", langue="fr")
    assert n == 2
    r = K.chercher(con, "ballast")                       # « voie-ballast » trouvé, accents et casse ignorés
    assert len(r["passages"]) == 1 and r["passages"][0]["debut_s"] == 100
    assert K.chercher(con, "ARRIERE")["passages"][0]["titre"] == "Chantier RVB"


def test_reimport_idempotent(tmp_path):
    con = K.ouvrir(str(tmp_path / "kb.sqlite"))
    t = str(transcription(tmp_path))
    K.importer_transcription(con, t, "A", url="https://ex/v1")
    K.importer_transcription(con, t, "A", url="https://ex/v1")
    assert K.statistiques(con)["passages"] == 2 and K.statistiques(con)["sources"] == 1
    assert len(K.chercher(con, "ballast")["passages"]) == 1      # index FTS nettoyé aussi


def test_lexique_et_recherche_multilingue(tmp_path):
    con = K.ouvrir(str(tmp_path / "kb.sqlite"))
    assert K.importer_lexique(con) > 300
    langues = {t["langue"] for t in K.chercher(con, "bourrage", 50)["termes"]}
    assert "fr" in langues
    assert any(t["langue"] == "es" for t in K.chercher(con, "bateadora")["termes"])


def test_methodes_et_export(tmp_path):
    con = K.ouvrir(str(tmp_path / "kb.sqlite"))
    K.importer_transcription(con, str(transcription(tmp_path)), "Chantier RVB", url="https://ex/v1")
    f = tmp_path / "m.json"
    f.write_text(json.dumps([{"nom": "Renouvellement voie-ballast", "categorie": "Renouvellement", "pays": "FR",
                              "description": "Remplacement rails, traverses et ballast.",
                              "etapes": ["Dégarnissage", "Pose", "Bourrage"], "engins": ["Suite rapide"],
                              "source_url": "https://ex/v1", "horodatage": "01:40"}]), encoding="utf-8")
    assert K.importer_methodes(con, str(f)) == 1
    assert K.importer_methodes(con, str(f)) == 1                  # pas de doublon
    assert K.statistiques(con)["methodes"] == 1
    m = K.chercher(con, "degarnissage")["methodes"]
    assert m and m[0]["titre"] == "Chantier RVB"
    out = tmp_path / "m.md"
    assert K.exporter_markdown(con, str(out)) == 1
    md = out.read_text(encoding="utf-8")
    assert "## Renouvellement" in md and "- Bourrage" in md and "(https://ex/v1) (à 01:40)" in md


def test_cli_kb(tmp_path, capsys):
    base = str(tmp_path / "kb.sqlite")
    assert main(["kb", "--base", base, "importer-transcription", str(transcription(tmp_path)), "--titre", "T"]) == 0
    assert main(["kb", "--base", base, "chercher", "kilomètres"]) == 0
    assert "[extrait] T @01:40" in capsys.readouterr().out
    assert main(["kb", "--base", base, "stats"]) == 0
