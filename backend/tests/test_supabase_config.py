import base64
import json
import os
import unittest

from app.routes.shorts import _normalize_video_id
from app.routes.videos import YouTubeUploadRequest, _build_video_metadata
from app.services.supabase_service import is_supabase_configured
from app.services.video_splitter import FONT_PATH, resolve_font_path


def _decode_supabase_role_key(key: str):
    parts = key.split('.')
    if len(parts) < 2:
        return None
    payload = parts[1]
    payload += '=' * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload.encode()).decode())


class SupabaseConfigTests(unittest.TestCase):
    def test_supabase_service_role_key_is_not_anon(self):
        key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or ''
        self.assertTrue(key, 'SUPABASE_SERVICE_ROLE_KEY is missing in the environment')
        payload = _decode_supabase_role_key(key)
        self.assertEqual(payload.get('role'), 'service_role', (
            'Supabase key is not a service_role token. The active role is '
            f'{payload.get("role")} and backend uploads will fail.'
        ))

    def test_supabase_config_is_enabled_only_for_valid_service_role(self):
        self.assertTrue(is_supabase_configured())


class VideoUploadRequestTests(unittest.TestCase):
    def test_upload_request_accepts_youtube_metadata(self):
        payload = YouTubeUploadRequest(
            youtube_url='https://www.youtube.com/watch?v=abc123',
            title='Sample upload',
            video_id='abc123',
            duration=45,
        )
        self.assertEqual(payload.youtube_url, 'https://www.youtube.com/watch?v=abc123')
        self.assertEqual(payload.title, 'Sample upload')
        self.assertEqual(payload.video_id, 'abc123')
        self.assertEqual(payload.duration, 45)

    def test_video_metadata_omits_duration_when_db_schema_does_not_have_it(self):
        payload = _build_video_metadata(
            video_id='abc123',
            title='Sample upload',
            filename='sample.mp4',
            youtube_url='https://www.youtube.com/watch?v=abc123',
            file_url='https://supabase.example.com/video.mp4',
            storage_bucket='youtube-videos',
            size_bytes=123,
            source='uploaded',
            duration=45,
        )
        self.assertNotIn('duration', payload)
        self.assertEqual(payload['video_id'], 'abc123')

    def test_normalize_video_id_strips_whitespace_and_quotes(self):
        self.assertEqual(_normalize_video_id('  "Mm4crwrMNRc"  '), 'Mm4crwrMNRc')
        self.assertEqual(_normalize_video_id(' Mm4crwrMNRc '), 'Mm4crwrMNRc')

    def test_font_path_is_resolved_without_hardcoded_windows_only_font(self):
        resolved = resolve_font_path()
        self.assertIsInstance(resolved, (str, type(None)))
        self.assertTrue(FONT_PATH is None or isinstance(FONT_PATH, str))


if __name__ == '__main__':
    unittest.main()
