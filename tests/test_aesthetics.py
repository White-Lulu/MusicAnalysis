import copy
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

import numpy as np

from music_analysis.aesthetics import Aesthetic, SoundCue
from music_analysis.culture import VERSION, culture_evidence
from music_analysis.summary import profile_fields, summarize_tracks
from music_analysis.taxonomy import CATALOG, SCENES, STYLES


class AestheticEvidenceTests(unittest.TestCase):
    def setUp(self):
        cue = SoundCue("声音", "Sound", "specific sound", "ordinary sound")
        self.tags = [Aesthetic(str(i), str(i), str(i), str(i // 2), "解读", "Reading",
                               "ordinary music", ("Rock---",), (cue, cue), str(i)) for i in range(8)]
        self.audio = np.tile([1., 0., 0.], (8, 1))
        self.rms = np.ones(8)
        self.positive = np.tile([.8, .6, 0.], (8, 3, 1))
        self.reference = np.tile([.5, np.sqrt(.75), 0.], (8, 3, 1))
        self.genres = [{"full_label": "Rock---Indie Rock", "coverage": 80}]

    def evidence(self, **changes):
        args = dict(vectors=self.audio, rms=self.rms, tags=self.tags,
                    positive=self.positive, reference=self.reference, genres=self.genres)
        return culture_evidence(**(args | changes))

    def test_reading_and_two_evidence_descriptions_are_auditable(self):
        rows, metadata = self.evidence()
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({r["family"] for r in rows}), 3)
        self.assertEqual(metadata["version"], VERSION)
        for row in rows:
            self.assertEqual(row["interpretation_en"], "Reading")
            self.assertEqual(len(row["sound_evidence"]), 2)
            self.assertTrue(all(cue["support_windows"] == 8 for cue in row["sound_evidence"]))

    def test_silence_equal_references_and_reversed_evidence_abstain(self):
        self.assertFalse(self.evidence(rms=np.zeros(8))[0])
        self.assertFalse(self.evidence(reference=self.positive)[0])
        self.assertFalse(self.evidence(positive=self.reference, reference=self.positive)[0])
        self.assertFalse(self.evidence(genres=[])[0])

    def test_one_weak_sound_description_cannot_be_hidden_by_the_other(self):
        positive = self.positive.copy()
        positive[:, 2] = [.4, np.sqrt(.84), 0.]
        self.assertFalse(self.evidence(positive=positive)[0])

    def test_concept_and_sounds_must_agree_in_the_same_excerpts(self):
        vectors = np.array([[1., 0., 0.], [0., 1., 0.]] * 4)
        positive = np.tile([[np.sqrt(.9999), -.01, 0.], [-.01, np.sqrt(.9999), 0.],
                            [np.sqrt(.5), np.sqrt(.5), 0.]], (8, 1, 1))
        reference = np.tile([0., 0., 1.], (8, 3, 1))
        self.assertFalse(self.evidence(vectors=vectors, positive=positive, reference=reference)[0])

    def test_nonfinite_model_output_is_rejected(self):
        positive = self.positive.copy()
        positive[0] = np.nan
        self.assertEqual(self.evidence(positive=positive)[1]["status"], "invalid_model_features")

    def test_ambiguous_related_cultures_are_not_arbitrarily_ranked(self):
        tags = [replace(self.tags[0], branch="shared"), replace(self.tags[2], branch="shared")]
        rows, metadata = self.evidence(tags=tags, positive=self.positive[:2], reference=self.reference[:2])
        self.assertFalse(rows)
        self.assertEqual(metadata["ambiguous_concepts"], 2)

    def test_y2k_requires_compatible_genre_and_voice(self):
        y2k = next(tag for tag in SCENES if tag.id == "cue-y2k")
        args = dict(tags=[y2k], positive=self.positive[:1], reference=self.reference[:1],
                    genres=[{"full_label": "Hip Hop---Trap", "coverage": 80}])
        self.assertFalse(self.evidence(**args)[0])
        self.assertTrue(self.evidence(**args, vocal_margin=self.rms)[0])
        self.assertFalse(self.evidence(**args, vocal_margin=-self.rms)[0])
        args["genres"] = self.genres
        self.assertFalse(self.evidence(**args, vocal_margin=self.rms)[0])

    def test_single_excerpt_requires_extra_margin(self):
        _, meta = self.evidence(vectors=self.audio[:1], rms=self.rms[:1])
        self.assertEqual(meta["criteria"]["mean_margin"], .04)

    def test_summary_preserves_evidence_scores_and_ignores_old_schema(self):
        rows, metadata = self.evidence()
        report = {"semantic": {"culture": metadata, "candidates": rows}}
        track = {"id": "a", "title": "Example", "artist": "", "state": "done", "report": report}
        full = summarize_tracks([track])["culture_profile"]
        self.assertEqual(full, summarize_tracks([track], False)["culture_profile"])
        self.assertEqual(full, summarize_tracks([track | {"report": profile_fields(report)}])["culture_profile"])
        self.assertEqual(full["rows"][0]["score"], rows[0]["score"])
        report["semantic"]["culture"]["version"] = VERSION - 1
        self.assertFalse(summarize_tracks([track])["culture_profile"]["rows"])

    def test_catalog_has_distinct_concepts_readings_and_sound_views(self):
        self.assertEqual(len(CATALOG), len(STYLES) + len(SCENES))
        self.assertEqual(len({tag.id for tag in CATALOG.values()}), len(CATALOG))
        for tag in SCENES:
            self.assertTrue(tag.interpretation and tag.interpretation_en and tag.contexts)
            self.assertEqual(len(tag.cues), 2)
            self.assertNotEqual(tag.cues[0].description, tag.cues[1].description)


class MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.original_tempdir = tempfile.tempdir
        cls.environment = patch.dict(os.environ, {"MUSIC_ANALYSIS_DATA": cls.temporary.name, "USE_TF": "0"})
        cls.environment.start()
        cls.server = importlib.import_module("music_analysis.server")

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()
        tempfile.tempdir = cls.original_tempdir
        cls.temporary.cleanup()

    def fixture(self, version):
        return {"version": version, "duration": 10, "rhythm": {"source": "Beat This!", "bpm": 100},
                "genres": [], "instruments": [{"label": "piano", "score": .7}], "mood": {"tags": []},
                "semantic": {"candidates": [{"kind": "style", "label": "Indie Rock", "score": .4},
                                             {"kind": "scene", "label": "Old cue", "score": .1}]}, "issues": {}}

    def test_versions_11_and_12_update_only_culture(self):
        proposed = {"culture": {"version": VERSION}, "candidates": [{"kind": "scene", "label": "New concept", "score": .1}]}
        for version in (11, 12):
            previous = self.fixture(version)
            with patch.object(self.server.models, "semantics", return_value=copy.deepcopy(proposed)) as semantic, \
                 patch.object(self.server.models, "instruments_from_embeddings", side_effect=AssertionError), \
                 patch.object(self.server, "load_audio", side_effect=AssertionError), \
                 patch.object(self.server, "rhythm_and_harmony", side_effect=AssertionError):
                result = self.server.analyze("unused", previous)
            self.assertTrue(semantic.call_args.kwargs["culture_only"])
            self.assertEqual(result["version"], 13)
            self.assertEqual(result["semantic"]["candidates"][0], previous["semantic"]["candidates"][0])
            self.assertEqual({k: v for k, v in result.items() if k not in ("version", "semantic")},
                             {k: v for k, v in previous.items() if k not in ("version", "semantic")})

    def test_failed_culture_migration_keeps_the_previous_report(self):
        with patch.object(self.server.models, "semantics", side_effect=ValueError("model unavailable")), \
             self.assertLogs("music_analysis", level="ERROR"):
            with self.assertRaises(RuntimeError):
                self.server.analyze("unused", self.fixture(12))

    def test_silent_migration_does_not_infer_a_culture(self):
        previous = self.fixture(12)
        previous["rhythm"]["source"] = "静音"
        previous["semantic"]["candidates"] = []
        with patch.object(self.server.models, "semantics", side_effect=AssertionError):
            result = self.server.analyze("unused", previous)
        self.assertEqual(result["semantic"]["candidates"], [])

    def test_store_supplies_previous_version_12_to_the_worker(self):
        previous = self.fixture(12)
        with self.server.library.connect() as con:
            con.execute("INSERT INTO tracks(id,path,title,artist,lookup,added,state,report) VALUES(?,?,?,?,?,?,?,?)",
                        ("a" * 64, "unused.mp3", "Example", "", "example", 0, "done", json.dumps(previous)))
        self.server.library.upgrade_reports(13)
        claimed = self.server.library.claim_next()
        self.assertEqual(json.loads(claimed["previous"]), previous)

    def test_new_song_semantics_still_include_styles_and_migration_can_skip_them(self):
        for culture_only in (False, True):
            model = self.server.Models(Path(self.temporary.name) / "models")
            with patch.object(model, "clap_audio", return_value=(np.tile([1., 0., 0.], (8, 1)), np.ones(8))), \
                 patch.object(model, "clap_text", side_effect=lambda texts: np.tile([.8, .6, 0.], (len(texts), 1))):
                result = model.semantics("unused", 10, {}, [], culture_only=culture_only)
            styles = [row for row in result["candidates"] if row["kind"] == "style"]
            self.assertEqual(len(styles), 0 if culture_only else len(STYLES))
            self.assertEqual(result["culture"]["version"], VERSION)


if __name__ == "__main__":
    unittest.main()
