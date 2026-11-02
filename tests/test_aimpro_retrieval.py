import copy
import unittest

from aimpro.didactic import CorpusCitation, checked_draft
from aimpro.lead import prepare_input
from aimpro.retrieval import evidence_from_response
from document_search.contracts import resource_key
from tests.aimpro_fixtures import draft


KEY = resource_key('wp3:test', 'v1')


def response():
    return {'documents': [{'id': 'chunk-1', 'text': 'Synthetic source: specify task, audience and tone in a business prompt.',
        'score': 1.0, 'metadata': {'source': 'wp3:test', 'source_scope': 'wp3', 'resource_key': KEY,
        'title': 'Synthetic prompting guide', 'uri': 'https://example.org/guide', 'licence': 'CC-BY-4.0', 'synthetic': True}}],
        'truncated': False}


def grounded(data=None):
    data = data or prepare_input()
    evidence = evidence_from_response('prompting', 'wp3', 3, response())
    data = data.model_copy(update={'corpus_evidence': evidence})
    value = draft(data)
    first, second = value.units[0].activities
    first = first.model_copy(update={'corpus_citations': (CorpusCitation(resource_id='wp3:test', resource_version='v1',
        document_ids=('chunk-1',), supported_claim='The prompt states task, audience and tone.'),)})
    value = value.model_copy(update={'units': (value.units[0].model_copy(update={'activities': (first, second)}),)})
    return data, value


class CorpusEvidenceTest(unittest.TestCase):
    def test_chunks_are_grouped_without_losing_metadata(self):
        r = response()
        second = copy.deepcopy(r['documents'][0]); second['id'] = 'chunk-2'; second['text'] = 'Another synthetic excerpt'
        r['documents'].append(second)
        evidence = evidence_from_response('prompting', 'wp3', 3, r)
        self.assertEqual(len(evidence.resources), 1)
        self.assertEqual(len(evidence.resources[0].documents), 2)
        self.assertEqual(evidence.resources[0].key, KEY)
        self.assertTrue(evidence.resources[0].documents[0].metadata['synthetic'])

    def test_truncation_wrong_scope_missing_metadata_and_latest_are_rejected(self):
        for change in (
            lambda r: r.update(truncated=True),
            lambda r: r['documents'][0]['metadata'].update(source_scope='other'),
            lambda r: r['documents'][0]['metadata'].pop('licence'),
            lambda r: r['documents'][0]['metadata'].update(resource_key=resource_key('wp3:test','latest')),
            lambda r: r['documents'][0]['metadata'].update(resource_key=resource_key('wp3:test ','v1')),
        ):
            r = response(); change(r)
            with self.assertRaises(ValueError):
                evidence_from_response('prompting', 'wp3', 3, r)

    def test_grounded_unit_requires_a_citation_to_exact_retrieved_segments(self):
        data, value = grounded()
        checked_draft(data, value)
        with self.assertRaises(ValueError):
            checked_draft(data, draft(data))
        first = value.units[0].activities[0]
        for change in ({'resource_version': 'wrong-version'}, {'document_ids': ('invented',)}):
            citation = first.corpus_citations[0].model_copy(update=change)
            activity = first.model_copy(update={'corpus_citations': (citation,)})
            unit = value.units[0].model_copy(update={'activities': (activity,)})
            with self.assertRaises(ValueError):
                checked_draft(data, value.model_copy(update={'units': (unit,)}))
        with self.assertRaises(ValueError):
            checked_draft(prepare_input(), value)
