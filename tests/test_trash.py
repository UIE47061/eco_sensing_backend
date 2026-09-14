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
        self.payload = dict(raw_weight=-4771.5, image_url=None,
                            ai_raw_result={'plastic': 0.82}, sensor_data={'test': 123})
        self.patcher = patch('services.trash.request_supabase')
        self.db = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_complete_flow(self):
        self.db.side_effect = [[{'id': SESSION_ID, 'status': 'uploading'}], [{'id': 'raw-id'}], [{'id': SESSION_ID, 'status': 'uploading'}], [{'id': SESSION_ID, 'status': 'uploading'}]]
        response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), dict(success=True, session_id=SESSION_ID, status='completed',
                         result=dict(weight=10.0, trash_type='unknown', carbon=0.0)))
        calls = self.db.call_args_list
        self.assertEqual([c.args for c in calls], [('GET', 'trash_sessions'), ('POST', 'trash_raw_data'),
                                                  ('PATCH', 'trash_sessions'), ('PATCH', 'trash_sessions')])
        self.assertEqual(calls[1].kwargs['json'], dict(self.payload, session_id=SESSION_ID))
        self.assertEqual(calls[2].kwargs['json']['status'], 'calculating')
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
        self.db.return_value = [{'id': SESSION_ID, 'status': 'uploading'}]
        with patch('services.trash.process_trash_data', side_effect=RuntimeError('private detail')):
            response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('private detail', response.text)
        self.assertEqual(self.db.call_args.kwargs['json']['status'], 'failed')

    def test_database_failures(self):
        for failure_index in range(4):
            with self.subTest(failure_index=failure_index):
                self.db.reset_mock()
                self.db.side_effect = [[{'id': SESSION_ID, 'status': 'uploading'}]] * failure_index + [HTTPException(503, 'private')] + [[{'id': SESSION_ID, 'status': 'uploading'}]]
                response = self.client.post(self.url, json=self.payload)
                self.assertEqual(response.status_code, 500)
                self.assertNotIn('private', response.text)
                if failure_index:
                    self.assertEqual(self.db.call_args.kwargs['json']['status'], 'failed')

    def test_failed_status_write_failure(self):
        self.db.side_effect = [[{'id': SESSION_ID, 'status': 'uploading'}], RuntimeError('insert'), RuntimeError('offline')]
        self.assertEqual(self.client.post(self.url, json={}).status_code, 500)

    def test_empty_insert_or_update(self):
        for index in (1, 2, 3):
            self.db.side_effect = [[{'id': SESSION_ID, 'status': 'uploading'}]] * index + [[]] + [[{'id': SESSION_ID, 'status': 'uploading'}]]
            self.assertEqual(self.client.post(self.url, json={}).status_code, 500 if index == 1 else 409)
            if index == 1:
                self.assertEqual(self.db.call_args.kwargs['json']['status'], 'failed')
            else:
                self.assertEqual(self.db.call_count, index + 1)
            self.db.reset_mock()

    def test_optional_fields(self):
        self.db.return_value = [{'id': SESSION_ID, 'status': 'uploading'}]
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

    def test_pi_transitions(self):
        edges = [('waiting', 'preparing'), ('preparing', 'ready'),
                 ('ready', 'recognizing'), ('recognizing', 'uploading')]
        edges += [(state, 'failed') for state in
                  ('waiting', 'preparing', 'ready', 'recognizing', 'uploading', 'calculating')]
        for current, target in edges:
            with self.subTest(current=current, target=target):
                self.db.side_effect = [[{'id': SESSION_ID, 'status': current}],
                                       [{'id': SESSION_ID, 'status': target}]]
                response = self.client.patch(f'/trash/{SESSION_ID}/status', json={'status': target})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['status'], target)
                self.assertEqual(self.db.call_args.kwargs['params']['status'], f'eq.{current}')

    def test_status_rejections(self):
        for current in ('completed', 'failed', 'waiting'):
            self.db.return_value = [{'id': SESSION_ID, 'status': current}]
            self.db.reset_mock()
            response = self.client.patch(f'/trash/{SESSION_ID}/status', json={'status': 'uploading'})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(self.db.call_count, 1)
        for target in ('waiting', 'calculating', 'completed', 'processing', 'invalid'):
            self.db.reset_mock()
            self.assertEqual(self.client.patch(f'/trash/{SESSION_ID}/status', json={'status': target}).status_code, 422)
            self.db.assert_not_called()

    def test_status_missing_and_race(self):
        self.db.return_value = []
        self.assertEqual(self.client.patch(f'/trash/{SESSION_ID}/status', json={'status': 'ready'}).status_code, 404)
        self.db.side_effect = [[{'id': SESSION_ID, 'status': 'preparing'}], []]
        self.assertEqual(self.client.patch(f'/trash/{SESSION_ID}/status', json={'status': 'ready'}).status_code, 409)

    def test_raw_requires_uploading(self):
        for current in ('waiting', 'preparing', 'ready', 'recognizing', 'calculating', 'completed', 'failed'):
            self.db.reset_mock()
            self.db.return_value = [{'id': SESSION_ID, 'status': current}]
            self.assertEqual(self.client.post(self.url, json={}).status_code, 409)
            self.assertEqual(self.db.call_count, 1)

    def test_sequential_flow_and_terminal_retry(self):
        state = {'id': SESSION_ID, 'status': 'waiting'}
        raw_rows = []
        def database(method, table, **kwargs):
            if method == 'GET':
                return [dict(state)]
            if method == 'POST':
                raw_rows.append(kwargs['json'])
                return [{'id': 'raw-id'}]
            if kwargs['params']['status'] != 'eq.' + state['status']:
                return []
            state.update(kwargs['json'])
            return [dict(state)]
        self.db.side_effect = database
        for target in ('preparing', 'ready', 'recognizing', 'uploading'):
            self.assertEqual(self.client.patch(f'/trash/{SESSION_ID}/status', json={'status': target}).status_code, 200)
        self.assertEqual(self.client.post(self.url, json=self.payload).status_code, 200)
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(self.client.post(self.url, json=self.payload).status_code, 409)
        self.assertEqual(len(raw_rows), 1)
        for target in ('preparing', 'recognizing', 'uploading', 'failed'):
            self.assertEqual(self.client.patch(f'/trash/{SESSION_ID}/status', json={'status': target}).status_code, 409)
        self.assertEqual(state['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
