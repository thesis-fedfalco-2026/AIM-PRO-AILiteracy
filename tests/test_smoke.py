from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch

import smoke
from document_search.backend import build_backend
from tests.learning_runtime import demo_orchestrator


class SmokeTest(unittest.TestCase):
    def test_smoke_rejects_profile_redirected_to_another_provider(self):
        catalog=smoke.load_model_catalog(smoke.BASE_DIR/'model.properties')
        catalog.profiles['openrouter']=catalog.profiles['openrouter'].model_copy(update={'base_url':'https://api.openai.com/v1','model':'gpt-4.1-mini'})
        with patch('smoke.load_model_catalog',return_value=catalog), patch('smoke.load_dotenv'), patch('smoke.build_orchestrator') as build, redirect_stdout(StringIO()):
            self.assertEqual(smoke.main([]),2)
            build.assert_not_called()

    def test_smoke_rejects_models_without_free_suffix_or_with_paid_opt_in(self):
        for model, allow_paid in (
            ('nvidia/nemotron-3-super-120b-a12b', True),
            ('openrouter/free', False),
            ('nvidia/nemotron-3-super-120b-a12b:free', True),
        ):
            with self.subTest(model=model, allow_paid=allow_paid):
                catalog=smoke.load_model_catalog(smoke.BASE_DIR/'model.properties')
                catalog.profiles['openrouter']=catalog.profiles['openrouter'].model_copy(
                    update={'model':model,'allow_paid':allow_paid})
                with patch('smoke.load_model_catalog',return_value=catalog), \
                        patch('smoke.build_orchestrator') as build, \
                        patch('smoke.load_dotenv'),redirect_stdout(StringIO()) as output:
                    self.assertEqual(smoke.main([]),2,output.getvalue())
                    build.assert_not_called()

    def test_smoke_checks_actual_gate_and_citation(self):
        for mode,status in [('complete',0),('empty-retrieval',1),('rejected-worker',1),('rejected-final',1)]:
            with self.subTest(mode=mode):
                backend=build_backend({'SEARCH_BACKEND':'mock'})
                self.addCleanup(backend.close)
                search=backend.search_documents if mode != 'empty-retrieval' else lambda *a,**k:{'documents':[]}
                orchestrator=demo_orchestrator(search,reject_stage={'rejected-worker':'WORKER','rejected-final':'FINAL'}.get(mode))
                with patch('smoke.build_orchestrator',return_value=orchestrator),patch('smoke.load_dotenv'),redirect_stdout(StringIO()) as output:
                    self.assertEqual(smoke.main([]),status,output.getvalue())
                    if mode == 'empty-retrieval':
                        self.assertIn('scoped_source',output.getvalue())

    def test_smoke_runs_with_the_catalog_it_validated(self):
        catalog=smoke.load_model_catalog(smoke.BASE_DIR/'model.properties')
        backend=build_backend({'SEARCH_BACKEND':'mock'})
        self.addCleanup(backend.close)
        orchestrator=demo_orchestrator(backend.search_documents)
        with patch('smoke.load_model_catalog',return_value=catalog), \
                patch('smoke.build_orchestrator',return_value=orchestrator) as build, \
                patch('smoke.load_dotenv'),redirect_stdout(StringIO()) as output:
            self.assertEqual(smoke.main([]),0,output.getvalue())
            self.assertIs(build.call_args.kwargs['model_catalog'],catalog)
