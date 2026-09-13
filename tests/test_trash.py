import unittest
from unittest.mock import patch
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routers.trash import router
from services.trash import DEMO_BIN_ID

SESSION_ID = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'


class TrashTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.url = f'/trash/{SESSION_ID}/raw-data'
        self.payload = dict(raw_weight=184392, image_url=None,
                            ai_raw_result={'plastic': 0.82}, sensor_data={'test': 123})
        self.patcher = patch('services.trash.request_supabase')
        self.db = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_complete_flow(self):
        self.db.side_effect = [[{'id': SESSION_ID}], [{'id': 'raw-id'}], [{'id': SESSION_ID}], [{'id': SESSION_ID}]]
        response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), dict(success=True, session_id=SESSION_ID, status='completed',
                         result=dict(weight=184392, trash_type='unknown', carbon=0.0)))
        calls = self.db.call_args_list
        self.assertEqual([c.args for c in calls], [('GET', 'trash_sessions'), ('POST', 'trash_raw_data'),
                                                  ('PATCH', 'trash_sessions'), ('PATCH', 'trash_sessions')])
        self.assertEqual(calls[1].kwargs['json'], dict(self.payload, session_id=SESSION_ID))
        self.assertEqual(calls[2].kwargs['json']['status'], 'processing')
        final = calls[3].kwargs['json']
        self.assertEqual(final['status'], 'completed')
        self.assertIsNotNone(datetime.fromisoformat(final['completed_at']).tzinfo)
        for call in (calls[0], calls[2], calls[3]):
            self.assertEqual(call.kwargs['params']['id'], f'eq.{SESSION_ID}')

    def test_missing_session(self):
        self.db.return_value = []
        self.assertEqual(self.client.post(self.url, json={}).status_code, 404)
        self.assertEqual(self.db.call_count, 1)

    def test_processing_error_marks_failed(self):
        self.db.return_value = [{'id': SESSION_ID}]
        with patch('services.trash.process_trash_data', side_effect=RuntimeError('private detail')):
            response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('private detail', response.text)
        self.assertEqual(self.db.call_args.kwargs['json']['status'], 'failed')

    def test_database_failures(self):
        for failure_index in range(4):
            with self.subTest(failure_index=failure_index):
                self.db.reset_mock()
                self.db.side_effect = [[{'id': SESSION_ID}]] * failure_index + [HTTPException(503, 'private')] + [[{'id': SESSION_ID}]]
                response = self.client.post(self.url, json=self.payload)
                self.assertEqual(response.status_code, 500)
                self.assertNotIn('private', response.text)
                if failure_index:
                    self.assertEqual(self.db.call_args.kwargs['json']['status'], 'failed')

    def test_failed_status_write_failure(self):
        self.db.side_effect = [[{'id': SESSION_ID}], RuntimeError('insert'), RuntimeError('offline')]
        self.assertEqual(self.client.post(self.url, json={}).status_code, 500)

    def test_empty_insert_or_update(self):
        for index in (1, 2, 3):
            self.db.side_effect = [[{'id': SESSION_ID}]] * index + [[]] + [[{'id': SESSION_ID}]]
            self.assertEqual(self.client.post(self.url, json={}).status_code, 500)
            self.assertEqual(self.db.call_args.kwargs['json']['status'], 'failed')

    def test_optional_fields(self):
        self.db.return_value = [{'id': SESSION_ID}]
        response = self.client.post(self.url, json={})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['result']['weight'])

    def test_invalid_requests(self):
        for url, payload in ((self.url, {'raw_weight': 'invalid'}), (self.url, {'sensor_data': []}),
                             ('/trash/not-a-uuid/raw-data', {})):
            self.assertEqual(self.client.post(url, json=payload).status_code, 422)
        self.db.assert_not_called()

    def test_create_session_unchanged(self):
        self.db.side_effect = [[{'id': DEMO_BIN_ID}], [{'id': SESSION_ID, 'bin_id': DEMO_BIN_ID, 'status': 'waiting'}]]
        response = self.client.post('/trash/session')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'waiting')
        self.assertEqual(self.db.call_args.kwargs['json'], {'bin_id': DEMO_BIN_ID, 'status': 'waiting'})


if __name__ == '__main__':
    unittest.main()
